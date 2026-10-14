import os
import csv
import json
import io
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, send_from_directory, Response
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from database import get_db, init_db, seed_db
from ai_detector import get_detector
from cleanliness_verifier import get_cleanliness_verifier
from ward_router import route_complaint, generate_complaint_id

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload directories exist
for folder in [Config.COMPLAINT_UPLOADS, Config.CLEANUP_UPLOADS, Config.ANNOTATED_UPLOADS]:
    os.makedirs(folder, exist_ok=True)

# ----------------- Decorators & Helpers -----------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('login'))
            if session.get('role') not in allowed_roles:
                flash("Access denied: You do not have permissions for this section.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def create_notification(user_id, title, message, complaint_id=None):
    """Utility to log notification for a user."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO notifications (user_id, complaint_id, title, message)
        VALUES (?, ?, ?, ?)
    ''', (user_id, complaint_id, title, message))
    conn.commit()
    conn.close()

def log_status_change(complaint_id, previous_status, new_status, updated_by, remarks=None):
    """Utility to log audit history for a complaint."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO status_history (complaint_id, previous_status, new_status, updated_by, remarks)
        VALUES (?, ?, ?, ?, ?)
    ''', (complaint_id, previous_status, new_status, updated_by, remarks))
    cursor.execute('''
        UPDATE complaints SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE complaint_id = ?
    ''', (new_status, complaint_id))
    conn.commit()
    conn.close()

@app.context_processor
def inject_global_data():
    unread_notifications = 0
    if 'user_id' in session:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND read_status = 0", (session['user_id'],))
        row = cursor.fetchone()
        if row:
            unread_notifications = row['count']
        conn.close()
    return {
        'unread_notifications': unread_notifications,
        'current_user': session
    }

# ----------------- File Serving -----------------

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(Config.UPLOAD_FOLDER, filename)

# ----------------- Public & Home Routes -----------------

@app.route('/')
def home():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM complaints")
    total_complaints = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as completed FROM complaints WHERE status IN ('Verified and Closed', 'Cleanup Completed')")
    completed_complaints = cursor.fetchone()['completed']

    cursor.execute("SELECT COUNT(*) as total_verif, SUM(CASE WHEN verification_status = 'Passed' THEN 1 ELSE 0 END) as passed_verif FROM verification_results")
    v_row = cursor.fetchone()
    total_verif = v_row['total_verif'] or 0
    passed_verif = v_row['passed_verif'] or 0
    cleanliness_rate = round((passed_verif / total_verif) * 100, 1) if total_verif > 0 else 94.2

    cursor.execute("SELECT COUNT(*) as active_workers FROM workers WHERE availability != 'offline'")
    active_workers = cursor.fetchone()['active_workers']

    # Recent complaints for showcase
    cursor.execute('''
        SELECT c.*, w.ward_name, d.name as dept_name,
               (SELECT file_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as before_image
        FROM complaints c
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        ORDER BY c.created_at DESC LIMIT 4
    ''')
    recent_complaints = cursor.fetchall()
    conn.close()

    stats = {
        'total': total_complaints,
        'completed': completed_complaints,
        'rate': cleanliness_rate,
        'workers': active_workers
    }
    return render_template('index.html', stats=stats, recent_complaints=recent_complaints)

@app.route('/about')
def about():
    return render_template('common/about.html')

# ----------------- Authentication Routes -----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']
            session['phone'] = user['phone']

            flash(f"Welcome back, {user['name']}! Logged in as {user['role'].capitalize()}.", "success")
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'worker':
                return redirect(url_for('worker_dashboard'))
            else:
                return redirect(url_for('citizen_dashboard'))
        else:
            flash("Invalid email or password. Please try again.", "danger")

    return render_template('auth/login.html')

@app.route('/demo-login/<role>')
def demo_login(role):
    """Convenient 1-click login for testing."""
    role_email_map = {
        'admin': 'admin@clean.gov',
        'worker': 'worker@clean.gov',
        'citizen': 'citizen@clean.gov'
    }
    email = role_email_map.get(role.lower(), 'citizen@clean.gov')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if user:
        session['user_id'] = user['user_id']
        session['name'] = user['name']
        session['email'] = user['email']
        session['role'] = user['role']
        session['phone'] = user['phone']

        flash(f"Demo Login successful as {user['role'].capitalize()} ({user['name']}).", "info")
        if user['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user['role'] == 'worker':
            return redirect(url_for('worker_dashboard'))
        else:
            return redirect(url_for('citizen_dashboard'))

    flash("Demo account not found.", "danger")
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()

        if not name or not email or not password:
            flash("Name, email, and password are required.", "danger")
            return render_template('auth/register.html')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for('login'))

        pwd_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, role, phone)
            VALUES (?, ?, ?, 'citizen', ?)
        ''', (name, email, pwd_hash, phone))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        create_notification(
            user_id,
            "Welcome to Smart Clean Municipality System",
            "Thank you for joining our smart civic initiative. You can now report waste, track cleanups, and verify municipal action."
        )

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for('login'))

    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been securely logged out.", "info")
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        new_password = request.form.get('new_password', '').strip()

        if name:
            cursor.execute("UPDATE users SET name = ?, phone = ? WHERE user_id = ?", (name, phone, user_id))
            session['name'] = name
            session['phone'] = phone

        if new_password:
            pwd_hash = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (pwd_hash, user_id))

        conn.commit()
        flash("Profile updated successfully.", "success")

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    # User's recent notifications
    cursor.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY timestamp DESC LIMIT 15", (user_id,))
    notifications = cursor.fetchall()

    conn.close()
    return render_template('common/profile.html', user=user, notifications=notifications)

@app.route('/notifications/mark-read/<int:nid>', methods=['POST'])
@login_required
def mark_notification_read(nid):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET read_status = 1 WHERE notification_id = ? AND user_id = ?", (nid, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# ----------------- Universal Dashboard Redirect -----------------

@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'worker':
        return redirect(url_for('worker_dashboard'))
    else:
        return redirect(url_for('citizen_dashboard'))

# ----------------- Citizen Portal Routes -----------------

@app.route('/citizen/dashboard')
@login_required
def citizen_dashboard():
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM complaints WHERE user_id = ?", (user_id,))
    total_complaints = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as pending FROM complaints WHERE user_id = ? AND status NOT IN ('Verified and Closed', 'Rejected')", (user_id,))
    pending_complaints = cursor.fetchone()['pending']

    cursor.execute("SELECT COUNT(*) as closed FROM complaints WHERE user_id = ? AND status = 'Verified and Closed'", (user_id,))
    closed_complaints = cursor.fetchone()['closed']

    # Recent complaints
    cursor.execute('''
        SELECT c.*, w.ward_name, d.name as dept_name,
               (SELECT file_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as before_image,
               (SELECT annotated_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as annotated_image
        FROM complaints c
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE c.user_id = ?
        ORDER BY c.created_at DESC LIMIT 6
    ''', (user_id,))
    complaints = cursor.fetchall()

    # Category distribution for this citizen
    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM complaints
        WHERE user_id = ?
        GROUP BY category
    ''', (user_id,))
    category_rows = cursor.fetchall()
    categories_data = {row['category']: row['count'] for row in category_rows}

    conn.close()

    return render_template(
        'citizen/dashboard.html',
        total_complaints=total_complaints,
        pending_complaints=pending_complaints,
        closed_complaints=closed_complaints,
        complaints=complaints,
        categories_data=categories_data
    )

@app.route('/report', methods=['GET', 'POST'])
@login_required
def report_waste():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM municipal_wards ORDER BY ward_id ASC")
    wards = cursor.fetchall()
    conn.close()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        address = request.form.get('address', '').strip()
        lat = request.form.get('latitude')
        lng = request.form.get('longitude')
        manual_ward_id = request.form.get('ward_id')

        # Handle image upload: file input OR camera capture data URL
        image_file = request.files.get('waste_image')
        captured_data = request.form.get('captured_image_data')

        if not description or not category:
            flash("Description and waste category are required.", "danger")
            return render_template('citizen/report_waste.html', wards=wards, categories=Config.COMPLAINT_CATEGORIES)

        complaint_id = generate_complaint_id()
        saved_before_path = None
        saved_relative_path = None

        if image_file and image_file.filename != '':
            if not allowed_file(image_file.filename):
                flash("Invalid file format. Supported formats: JPG, PNG, WEBP.", "danger")
                return render_template('citizen/report_waste.html', wards=wards, categories=Config.COMPLAINT_CATEGORIES)
            
            ext = image_file.filename.rsplit('.', 1)[1].lower()
            filename = f"{complaint_id}_before.{ext}"
            saved_before_path = os.path.join(Config.COMPLAINT_UPLOADS, filename)
            image_file.save(saved_before_path)
            saved_relative_path = f"uploads/complaints/{filename}"
        elif captured_data and captured_data.startswith('data:image'):
            import base64
            header, encoded = captured_data.split(',', 1)
            ext = 'jpg' if 'jpeg' in header else 'png'
            filename = f"{complaint_id}_before.{ext}"
            saved_before_path = os.path.join(Config.COMPLAINT_UPLOADS, filename)
            with open(saved_before_path, 'wb') as f:
                f.write(base64.b64decode(encoded))
            saved_relative_path = f"uploads/complaints/{filename}"
        else:
            flash("Please upload a photograph or capture an image using the webcam.", "warning")
            return render_template('citizen/report_waste.html', wards=wards, categories=Config.COMPLAINT_CATEGORIES)

        # 1. Automatic Municipality & Department Routing
        route_info = route_complaint(lat, lng, category, ward_id=manual_ward_id if manual_ward_id else None)
        assigned_ward_id = route_info['ward_id']
        assigned_dept_id = route_info['department_id']
        priority = route_info['priority']

        # 2. Run Real YOLO & OpenCV Waste Detection
        detector = get_detector()
        annotated_filename = f"{complaint_id}_annotated.jpg"
        annotated_abs_path = os.path.join(Config.ANNOTATED_UPLOADS, annotated_filename)
        annotated_rel_path = f"uploads/annotated/{annotated_filename}"

        detection_result = detector.detect_waste(
            saved_before_path,
            output_annotated_path=annotated_abs_path,
            conf_thresh=Config.YOLO_CONFIDENCE_THRESHOLD
        )

        initial_status = "AI Analysis Completed" if detection_result.get("success") else "Submitted"

        # 3. Store Complaint in Database
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO complaints (
                complaint_id, user_id, title, description, category,
                location, latitude, longitude, ward_id, department_id,
                status, priority
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            complaint_id, session['user_id'], title or f"{category} report",
            description, category, address or f"Lat: {lat}, Lng: {lng}",
            float(lat) if lat else Config.DEFAULT_MAP_LAT,
            float(lng) if lng else Config.DEFAULT_MAP_LNG,
            assigned_ward_id, assigned_dept_id, initial_status, priority
        ))

        # Store Image record
        cursor.execute('''
            INSERT INTO images (complaint_id, image_type, file_path, annotated_path)
            VALUES (?, 'before', ?, ?)
        ''', (complaint_id, saved_relative_path, annotated_rel_path))
        image_id = cursor.lastrowid

        # Store Waste Detections records
        if detection_result.get("success"):
            for det in detection_result.get("detections", []):
                cursor.execute('''
                    INSERT INTO waste_detections (
                        complaint_id, image_id, model_name, class_label,
                        confidence, object_count, bounding_boxes
                    ) VALUES (?, ?, 'YOLOv8-Nano', ?, ?, 1, ?)
                ''', (
                    complaint_id, image_id, det['class_name'],
                    det['confidence'], json.dumps(det['bbox'])
                ))

        # Log Status History
        cursor.execute('''
            INSERT INTO status_history (complaint_id, previous_status, new_status, updated_by, remarks)
            VALUES (?, 'Submitted', ?, ?, ?)
        ''', (
            complaint_id, initial_status, session['user_id'],
            f"AI detection processed {detection_result.get('object_count', 0)} waste objects. Auto-routed to {route_info['ward_name']} - {route_info['department_name']}."
        ))

        # Send in-app notification to Citizen
        cursor.execute('''
            INSERT INTO notifications (user_id, complaint_id, title, message)
            VALUES (?, ?, 'Complaint Registered Successfully', ?)
        ''', (
            session['user_id'], complaint_id,
            f"Your complaint {complaint_id} has been registered and auto-assigned to {route_info['ward_name']} ({route_info['department_name']})."
        ))

        conn.commit()
        conn.close()

        flash(f"Complaint {complaint_id} submitted! AI analysis complete.", "success")
        return redirect(url_for('view_detection_result', complaint_id=complaint_id))

    return render_template('citizen/report_waste.html', wards=wards, categories=Config.COMPLAINT_CATEGORIES)

@app.route('/detection/<complaint_id>')
@login_required
def view_detection_result(complaint_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT c.*, w.ward_name, d.name as dept_name,
               (SELECT file_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as before_image,
               (SELECT annotated_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as annotated_image
        FROM complaints c
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE c.complaint_id = ?
    ''', (complaint_id,))
    complaint = cursor.fetchone()

    if not complaint:
        conn.close()
        flash("Complaint not found.", "warning")
        return redirect(url_for('dashboard'))

    # Retrieve all detected objects
    cursor.execute('''
        SELECT * FROM waste_detections WHERE complaint_id = ? ORDER BY confidence DESC
    ''', (complaint_id,))
    detections = cursor.fetchall()
    conn.close()

    return render_template('citizen/detection_result.html', complaint=complaint, detections=detections)

@app.route('/complaints')
@login_required
def citizen_complaints():
    user_id = session['user_id']
    status_filter = request.args.get('status', 'all')
    
    conn = get_db()
    cursor = conn.cursor()

    query = '''
        SELECT c.*, w.ward_name, d.name as dept_name,
               (SELECT file_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as before_image,
               (SELECT annotated_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as annotated_image
        FROM complaints c
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE c.user_id = ?
    '''
    params = [user_id]

    if status_filter != 'all':
        query += " AND c.status = ?"
        params.append(status_filter)

    query += " ORDER BY c.created_at DESC"
    cursor.execute(query, tuple(params))
    complaints = cursor.fetchall()
    conn.close()

    return render_template('citizen/my_complaints.html', complaints=complaints, status_filter=status_filter)

@app.route('/track')
@app.route('/track/<complaint_id>')
def track_complaint(complaint_id=None):
    cid = complaint_id or request.args.get('cid', '').strip()
    complaint = None
    images = []
    history = []
    verification = None
    assignment = None

    if cid:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT c.*, w.ward_name, d.name as dept_name
            FROM complaints c
            LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
            LEFT JOIN departments d ON c.department_id = d.department_id
            WHERE c.complaint_id = ?
        ''', (cid,))
        complaint = cursor.fetchone()

        if complaint:
            cursor.execute("SELECT * FROM images WHERE complaint_id = ? ORDER BY image_id ASC", (cid,))
            images = cursor.fetchall()

            cursor.execute('''
                SELECT sh.*, u.name as updater_name, u.role as updater_role
                FROM status_history sh
                LEFT JOIN users u ON sh.updated_by = u.user_id
                WHERE sh.complaint_id = ?
                ORDER BY sh.timestamp ASC
            ''', (cid,))
            history = cursor.fetchall()

            cursor.execute("SELECT * FROM verification_results WHERE complaint_id = ? ORDER BY created_at DESC LIMIT 1", (cid,))
            verification = cursor.fetchone()

            cursor.execute('''
                SELECT a.*, u.name as worker_name, w.vehicle_no, w.phone as worker_phone
                FROM assignments a
                LEFT JOIN workers w ON a.worker_id = w.worker_id
                LEFT JOIN users u ON w.user_id = u.user_id
                WHERE a.complaint_id = ? ORDER BY a.assignment_id DESC LIMIT 1
            ''', (cid,))
            assignment = cursor.fetchone()

        conn.close()

        if not complaint and complaint_id:
            flash(f"Complaint ID '{cid}' was not found in the municipal records.", "warning")

    return render_template(
        'citizen/track.html',
        complaint=complaint,
        images=images,
        history=history,
        verification=verification,
        assignment=assignment,
        searched_id=cid
    )

# ----------------- Worker Portal Routes -----------------

@app.route('/worker/dashboard')
@role_required(['worker', 'admin'])
def worker_dashboard():
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()

    # Find worker record
    cursor.execute("SELECT * FROM workers WHERE user_id = ?", (user_id,))
    worker = cursor.fetchone()

    worker_id = worker['worker_id'] if worker else None

    # Fetch assigned complaints
    cursor.execute('''
        SELECT c.*, w.ward_name, a.assignment_id, a.deadline, a.status as assign_status,
               (SELECT file_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as before_image
        FROM complaints c
        JOIN assignments a ON c.complaint_id = a.complaint_id
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        WHERE a.worker_id = ? AND a.status IN ('Assigned', 'In Progress')
        ORDER BY a.deadline ASC, c.priority DESC
    ''', (worker_id,))
    active_tasks = cursor.fetchall()

    cursor.execute('''
        SELECT c.*, w.ward_name, a.assignment_id, vr.verification_status, vr.reduction_percentage
        FROM complaints c
        JOIN assignments a ON c.complaint_id = a.complaint_id
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        LEFT JOIN verification_results vr ON c.complaint_id = vr.complaint_id
        WHERE a.worker_id = ? AND a.status = 'Completed'
        ORDER BY a.assignment_id DESC LIMIT 6
    ''', (worker_id,))
    completed_tasks = cursor.fetchall()

    conn.close()

    return render_template(
        'worker/dashboard.html',
        worker=worker,
        active_tasks=active_tasks,
        completed_tasks=completed_tasks
    )

@app.route('/worker/task/<complaint_id>')
@role_required(['worker', 'admin'])
def worker_task_detail(complaint_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT c.*, w.ward_name, d.name as dept_name, a.assignment_id, a.deadline, a.notes as assign_notes, a.status as assign_status,
               (SELECT file_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as before_image,
               (SELECT annotated_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as annotated_image
        FROM complaints c
        LEFT JOIN assignments a ON c.complaint_id = a.complaint_id
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE c.complaint_id = ?
    ''', (complaint_id,))
    task = cursor.fetchone()

    cursor.execute("SELECT * FROM waste_detections WHERE complaint_id = ?", (complaint_id,))
    detections = cursor.fetchall()

    cursor.execute("SELECT * FROM verification_results WHERE complaint_id = ? ORDER BY created_at DESC LIMIT 1", (complaint_id,))
    verification = cursor.fetchone()

    conn.close()

    if not task:
        flash("Task not found.", "warning")
        return redirect(url_for('worker_dashboard'))

    return render_template('worker/task_detail.html', task=task, detections=detections, verification=verification)

@app.route('/worker/start/<complaint_id>', methods=['POST'])
@role_required(['worker', 'admin'])
def worker_start_cleanup(complaint_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT status FROM complaints WHERE complaint_id = ?", (complaint_id,))
    curr = cursor.fetchone()
    prev_status = curr['status'] if curr else 'Assigned'

    log_status_change(complaint_id, prev_status, 'Cleanup In Progress', session['user_id'], "Worker arrived on site and initiated cleanup.")
    cursor.execute("UPDATE assignments SET status = 'In Progress' WHERE complaint_id = ?", (complaint_id,))
    conn.commit()

    # Notify Citizen
    cursor.execute("SELECT user_id FROM complaints WHERE complaint_id = ?", (complaint_id,))
    comp = cursor.fetchone()
    if comp:
        create_notification(comp['user_id'], "Cleanup Started", f"Sanitation team has commenced cleanup operations for {complaint_id}.", complaint_id)

    conn.close()
    flash("Status updated: Cleanup In Progress.", "info")
    return redirect(url_for('worker_task_detail', complaint_id=complaint_id))

@app.route('/worker/cleanup/<complaint_id>', methods=['GET', 'POST'])
@role_required(['worker', 'admin'])
def worker_upload_cleanup(complaint_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT c.*, 
               (SELECT file_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as before_image
        FROM complaints c WHERE c.complaint_id = ?
    ''', (complaint_id,))
    complaint = cursor.fetchone()

    if not complaint:
        conn.close()
        flash("Complaint not found.", "warning")
        return redirect(url_for('worker_dashboard'))

    if request.method == 'POST':
        after_file = request.files.get('cleanup_image')
        captured_data = request.form.get('captured_cleanup_data')
        worker_notes = request.form.get('notes', '').strip()

        saved_after_path = None
        saved_relative_path = None

        if after_file and after_file.filename != '':
            if not allowed_file(after_file.filename):
                flash("Invalid format. Use JPG, PNG or WEBP.", "danger")
                return render_template('worker/upload_cleanup.html', complaint=complaint)
            ext = after_file.filename.rsplit('.', 1)[1].lower()
            filename = f"{complaint_id}_after.{ext}"
            saved_after_path = os.path.join(Config.CLEANUP_UPLOADS, filename)
            after_file.save(saved_after_path)
            saved_relative_path = f"uploads/cleanups/{filename}"
        elif captured_data and captured_data.startswith('data:image'):
            import base64
            header, encoded = captured_data.split(',', 1)
            ext = 'jpg' if 'jpeg' in header else 'png'
            filename = f"{complaint_id}_after.{ext}"
            saved_after_path = os.path.join(Config.CLEANUP_UPLOADS, filename)
            with open(saved_after_path, 'wb') as f:
                f.write(base64.b64decode(encoded))
            saved_relative_path = f"uploads/cleanups/{filename}"
        else:
            flash("Please provide an after-cleaning photograph.", "warning")
            return render_template('worker/upload_cleanup.html', complaint=complaint)

        # Retrieve Before Image file path
        before_file_rel = complaint['before_image']
        before_file_abs = os.path.join(Config.BASE_DIR, before_file_rel.replace('/', os.sep))

        # Save After Image record
        cursor.execute('''
            INSERT INTO images (complaint_id, image_type, file_path, annotated_path)
            VALUES (?, 'after', ?, ?)
        ''', (complaint_id, saved_relative_path, f"uploads/annotated/{complaint_id}_after_annotated.jpg"))

        # Run AI Cleanliness Verification
        verifier = get_cleanliness_verifier()
        v_result = verifier.verify_cleanup(before_file_abs, saved_after_path, complaint_id)

        if not v_result.get("success"):
            flash(f"Verification execution error: {v_result.get('error')}", "danger")
            conn.close()
            return redirect(url_for('worker_task_detail', complaint_id=complaint_id))

        # Insert Verification Results into DB
        cursor.execute('''
            INSERT INTO verification_results (
                complaint_id, before_count, after_count, reduction_percentage,
                verification_status, review_notes, similarity_score, clutter_reduction
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            complaint_id,
            v_result['before_count'],
            v_result['after_count'],
            v_result['reduction_percentage'],
            v_result['verification_status'],
            f"{v_result['recommendation']} Worker Remarks: {worker_notes}",
            v_result['similarity_score'],
            v_result['clutter_reduction']
        ))

        # Update Complaint Status
        new_status = "AI Verification"
        log_status_change(complaint_id, complaint['status'], new_status, session['user_id'], f"Cleanup submitted. AI verified reduction of {v_result['reduction_percentage']}%. Status: {v_result['verification_status']}.")
        
        cursor.execute("UPDATE assignments SET status = 'Completed' WHERE complaint_id = ?", (complaint_id,))

        # Notify Citizen and Admin
        create_notification(
            complaint['user_id'],
            "Cleanup Completed - Under Verification",
            f"The sanitation team has submitted cleanup evidence for complaint {complaint_id}. AI verified {v_result['reduction_percentage']}% waste reduction.",
            complaint_id
        )

        conn.commit()
        conn.close()

        flash(f"After-cleaning photo uploaded! AI Verification: {v_result['verification_status']} ({v_result['reduction_percentage']}% reduction).", "success")
        return redirect(url_for('worker_task_detail', complaint_id=complaint_id))

    conn.close()
    return render_template('worker/upload_cleanup.html', complaint=complaint)

# ----------------- Municipality Admin Portal Routes -----------------

@app.route('/admin/dashboard')
@role_required(['admin'])
def admin_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # KPI counts
    cursor.execute("SELECT COUNT(*) as total FROM complaints")
    total_complaints = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as pending FROM complaints WHERE status IN ('Submitted', 'AI Analysis Completed', 'Municipality Assigned')")
    pending_complaints = cursor.fetchone()['pending']

    cursor.execute("SELECT COUNT(*) as in_progress FROM complaints WHERE status IN ('Worker Assigned', 'Cleanup In Progress')")
    in_progress = cursor.fetchone()['in_progress']

    cursor.execute("SELECT COUNT(*) as verification_queue FROM complaints WHERE status = 'AI Verification'")
    verification_queue = cursor.fetchone()['verification_queue']

    cursor.execute("SELECT COUNT(*) as closed FROM complaints WHERE status = 'Verified and Closed'")
    closed_complaints = cursor.fetchone()['closed']

    # Cleanliness metrics
    cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN verification_status = 'Passed' THEN 1 ELSE 0 END) as passed FROM verification_results")
    v_stats = cursor.fetchone()
    total_v = v_stats['total'] or 0
    passed_v = v_stats['passed'] or 0
    pass_rate = round((passed_v / total_v) * 100, 1) if total_v > 0 else 0

    # Ward-wise breakdown
    cursor.execute('''
        SELECT w.ward_name, COUNT(c.complaint_id) as count
        FROM municipal_wards w
        LEFT JOIN complaints c ON w.ward_id = c.ward_id
        GROUP BY w.ward_id, w.ward_name
    ''')
    ward_counts = cursor.fetchall()

    # Category distribution
    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM complaints GROUP BY category
    ''')
    cat_counts = cursor.fetchall()

    # All active complaints for Leaflet interactive map
    cursor.execute('''
        SELECT c.complaint_id, c.title, c.category, c.status, c.priority, c.latitude, c.longitude, c.location,
               w.ward_name, d.name as dept_name,
               (SELECT file_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as before_image
        FROM complaints c
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
        ORDER BY c.created_at DESC
    ''')
    map_complaints = [dict(row) for row in cursor.fetchall()]

    # Wards geometry for map display
    cursor.execute("SELECT * FROM municipal_wards")
    wards_list = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return render_template(
        'admin/dashboard.html',
        total=total_complaints,
        pending=pending_complaints,
        in_progress=in_progress,
        verification_queue=verification_queue,
        closed=closed_complaints,
        pass_rate=pass_rate,
        ward_counts=ward_counts,
        cat_counts=cat_counts,
        map_complaints=json.dumps(map_complaints),
        wards_list=json.dumps(wards_list)
    )

@app.route('/admin/complaints')
@role_required(['admin'])
def admin_complaints():
    ward_filter = request.args.get('ward', 'all')
    status_filter = request.args.get('status', 'all')
    priority_filter = request.args.get('priority', 'all')
    category_filter = request.args.get('category', 'all')

    conn = get_db()
    cursor = conn.cursor()

    query = '''
        SELECT c.*, w.ward_name, d.name as dept_name, u.name as citizen_name,
               (SELECT file_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'before' LIMIT 1) as before_image,
               (SELECT file_path FROM images WHERE complaint_id = c.complaint_id AND image_type = 'after' LIMIT 1) as after_image,
               (SELECT vr.verification_status FROM verification_results vr WHERE vr.complaint_id = c.complaint_id ORDER BY vr.created_at DESC LIMIT 1) as verif_status
        FROM complaints c
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        LEFT JOIN users u ON c.user_id = u.user_id
        WHERE 1=1
    '''
    params = []

    if ward_filter != 'all':
        query += " AND c.ward_id = ?"
        params.append(ward_filter)
    if status_filter != 'all':
        query += " AND c.status = ?"
        params.append(status_filter)
    if priority_filter != 'all':
        query += " AND c.priority = ?"
        params.append(priority_filter)
    if category_filter != 'all':
        query += " AND c.category = ?"
        params.append(category_filter)

    query += " ORDER BY c.created_at DESC"
    cursor.execute(query, tuple(params))
    complaints = cursor.fetchall()

    cursor.execute("SELECT * FROM municipal_wards")
    wards = cursor.fetchall()

    # Available workers for assignment modal
    cursor.execute('''
        SELECT w.worker_id, u.name, d.name as dept_name, w.vehicle_no, w.availability
        FROM workers w
        JOIN users u ON w.user_id = u.user_id
        JOIN departments d ON w.department_id = d.department_id
    ''')
    workers = cursor.fetchall()

    conn.close()

    return render_template(
        'admin/complaints.html',
        complaints=complaints,
        wards=wards,
        workers=workers,
        ward_filter=ward_filter,
        status_filter=status_filter,
        priority_filter=priority_filter,
        category_filter=category_filter,
        categories=Config.COMPLAINT_CATEGORIES
    )

@app.route('/admin/assign/<complaint_id>', methods=['POST'])
@role_required(['admin'])
def admin_assign_worker(complaint_id):
    worker_id = request.form.get('worker_id')
    deadline = request.form.get('deadline')
    notes = request.form.get('notes', '').strip()

    if not worker_id:
        flash("Please select a sanitation worker.", "warning")
        return redirect(url_for('admin_complaints'))

    conn = get_db()
    cursor = conn.cursor()

    # Create Assignment
    cursor.execute('''
        INSERT INTO assignments (complaint_id, worker_id, assigned_by, deadline, notes, status)
        VALUES (?, ?, ?, ?, ?, 'Assigned')
    ''', (complaint_id, worker_id, session['user_id'], deadline, notes))

    # Update complaint status
    log_status_change(complaint_id, 'Municipality Assigned', 'Worker Assigned', session['user_id'], f"Assigned to worker ID #{worker_id}. Deadline: {deadline or 'Standard 24h'}")

    # Notify Citizen
    cursor.execute("SELECT user_id FROM complaints WHERE complaint_id = ?", (complaint_id,))
    c_row = cursor.fetchone()
    if c_row:
        create_notification(c_row['user_id'], "Sanitation Worker Dispatched", f"A municipal collection specialist has been assigned to your complaint {complaint_id}.", complaint_id)

    # Notify Worker
    cursor.execute("SELECT user_id FROM workers WHERE worker_id = ?", (worker_id,))
    w_row = cursor.fetchone()
    if w_row:
        create_notification(w_row['user_id'], "New Task Assigned", f"You have been assigned cleanup duty for complaint {complaint_id}.", complaint_id)

    conn.commit()
    conn.close()

    flash(f"Complaint {complaint_id} assigned successfully.", "success")
    return redirect(url_for('admin_complaints'))

@app.route('/admin/status/<complaint_id>', methods=['POST'])
@role_required(['admin'])
def admin_update_status(complaint_id):
    new_status = request.form.get('status')
    remarks = request.form.get('remarks', '').strip()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT status, user_id FROM complaints WHERE complaint_id = ?", (complaint_id,))
    comp = cursor.fetchone()
    if comp:
        log_status_change(complaint_id, comp['status'], new_status, session['user_id'], remarks)
        create_notification(
            comp['user_id'],
            f"Complaint Status: {new_status}",
            f"Status updated to '{new_status}'. Municipal notes: {remarks or 'No additional notes.'}",
            complaint_id
        )

    conn.commit()
    conn.close()

    flash(f"Complaint {complaint_id} status updated to '{new_status}'.", "success")
    return redirect(request.referrer or url_for('admin_complaints'))

@app.route('/admin/verification/<complaint_id>')
@role_required(['admin'])
def admin_verification_review(complaint_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT c.*, w.ward_name, d.name as dept_name, u.name as citizen_name
        FROM complaints c
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        LEFT JOIN users u ON c.user_id = u.user_id
        WHERE c.complaint_id = ?
    ''', (complaint_id,))
    complaint = cursor.fetchone()

    cursor.execute("SELECT * FROM images WHERE complaint_id = ?", (complaint_id,))
    images = cursor.fetchall()

    cursor.execute('''
        SELECT vr.*, u.name as verifier_name
        FROM verification_results vr
        LEFT JOIN users u ON vr.verified_by = u.user_id
        WHERE vr.complaint_id = ?
        ORDER BY vr.created_at DESC LIMIT 1
    ''', (complaint_id,))
    verification = cursor.fetchone()

    # Assignment details
    cursor.execute('''
        SELECT a.*, u.name as worker_name, w.phone, w.vehicle_no
        FROM assignments a
        JOIN workers w ON a.worker_id = w.worker_id
        JOIN users u ON w.user_id = u.user_id
        WHERE a.complaint_id = ?
        ORDER BY a.assignment_id DESC LIMIT 1
    ''', (complaint_id,))
    assignment = cursor.fetchone()

    conn.close()

    if not complaint:
        flash("Complaint not found.", "warning")
        return redirect(url_for('admin_complaints'))

    before_img = None
    after_img = None
    annotated_before = None
    annotated_after = None
    composite_img = f"uploads/annotated/{complaint_id}_comparison_composite.jpg"

    for img in images:
        if img['image_type'] == 'before':
            before_img = img['file_path']
            annotated_before = img['annotated_path']
        elif img['image_type'] == 'after':
            after_img = img['file_path']
            annotated_after = img['annotated_path']

    return render_template(
        'admin/verification_review.html',
        complaint=complaint,
        verification=verification,
        assignment=assignment,
        before_img=before_img,
        after_img=after_img,
        annotated_before=annotated_before,
        annotated_after=annotated_after,
        composite_img=composite_img
    )

@app.route('/admin/verification/action/<complaint_id>', methods=['POST'])
@role_required(['admin'])
def admin_verification_action(complaint_id):
    action = request.form.get('action')  # 'approve', 'rework', 'reject'
    officer_remarks = request.form.get('officer_remarks', '').strip()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT status, user_id FROM complaints WHERE complaint_id = ?", (complaint_id,))
    comp = cursor.fetchone()

    if not comp:
        conn.close()
        flash("Complaint not found.", "danger")
        return redirect(url_for('admin_complaints'))

    if action == 'approve':
        new_status = 'Verified and Closed'
        remarks = f"Officer Approved Closure: {officer_remarks or 'Cleanliness verification criteria satisfied.'}"
        cursor.execute("UPDATE verification_results SET verified_by = ? WHERE complaint_id = ?", (session['user_id'], complaint_id))
    elif action == 'rework':
        new_status = 'Worker Assigned'
        remarks = f"Cleanliness Verification Rejected by Officer - Rework Ordered: {officer_remarks or 'Debris remains visible. Please re-clean area.'}"
        cursor.execute("UPDATE assignments SET status = 'Assigned' WHERE complaint_id = ?", (complaint_id,))
    elif action == 'reject':
        new_status = 'Rejected'
        remarks = f"Complaint Dismissed by Officer: {officer_remarks or 'Invalid submission or unable to verify.'}"
    else:
        new_status = comp['status']
        remarks = officer_remarks

    log_status_change(complaint_id, comp['status'], new_status, session['user_id'], remarks)

    # Notify Citizen
    create_notification(
        comp['user_id'],
        f"Complaint Status: {new_status}",
        f"Officer decision: {remarks}",
        complaint_id
    )

    conn.commit()
    conn.close()

    flash(f"Decision recorded: Complaint marked as '{new_status}'.", "success")
    return redirect(url_for('admin_complaints'))

@app.route('/admin/wards')
@role_required(['admin'])
def admin_wards():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT w.*, d.name as dept_name, d.code as dept_code,
               (SELECT COUNT(*) FROM complaints WHERE ward_id = w.ward_id) as complaint_count
        FROM municipal_wards w
        LEFT JOIN departments d ON w.department_id = d.department_id
    ''')
    wards = cursor.fetchall()

    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    conn.close()

    return render_template('admin/wards.html', wards=wards, departments=departments)

@app.route('/admin/wards/add', methods=['POST'])
@role_required(['admin'])
def admin_add_ward():
    ward_name = request.form.get('ward_name', '').strip()
    ward_code = request.form.get('ward_code', '').strip()
    dept_id = request.form.get('department_id')
    lat = request.form.get('lat_center')
    lng = request.form.get('lng_center')
    boundary_info = request.form.get('boundary_information', '').strip()
    description = request.form.get('description', '').strip()

    if not ward_name or not ward_code or not lat or not lng:
        flash("Ward name, code, latitude, and longitude are required.", "danger")
        return redirect(url_for('admin_wards'))

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO municipal_wards (ward_name, ward_code, department_id, lat_center, lng_center, boundary_information, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ward_name, ward_code, dept_id, float(lat), float(lng), boundary_info, description))
        conn.commit()
        flash(f"Ward '{ward_name}' created successfully.", "success")
    except Exception as e:
        flash(f"Error adding ward: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for('admin_wards'))

@app.route('/admin/analytics')
@role_required(['admin'])
def admin_analytics():
    conn = get_db()
    cursor = conn.cursor()

    # Category distribution
    cursor.execute("SELECT category, COUNT(*) as count FROM complaints GROUP BY category")
    cat_data = cursor.fetchall()

    # Status distribution
    cursor.execute("SELECT status, COUNT(*) as count FROM complaints GROUP BY status")
    status_data = cursor.fetchall()

    # Ward-wise complaints and resolutions
    cursor.execute('''
        SELECT w.ward_name,
               COUNT(c.complaint_id) as total,
               SUM(CASE WHEN c.status = 'Verified and Closed' THEN 1 ELSE 0 END) as closed
        FROM municipal_wards w
        LEFT JOIN complaints c ON w.ward_id = c.ward_id
        GROUP BY w.ward_id, w.ward_name
    ''')
    ward_performance = cursor.fetchall()

    # Average reduction percentage in verified cleanups
    cursor.execute("SELECT AVG(reduction_percentage) as avg_reduction, AVG(similarity_score) as avg_sim FROM verification_results")
    ai_metrics = cursor.fetchone()

    conn.close()

    return render_template(
        'admin/analytics.html',
        cat_data=cat_data,
        status_data=status_data,
        ward_performance=ward_performance,
        avg_reduction=round(ai_metrics['avg_reduction'] or 0.0, 1),
        avg_sim=round(ai_metrics['avg_sim'] or 0.0, 2)
    )

@app.route('/admin/export/csv')
@role_required(['admin'])
def export_csv():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.complaint_id, c.title, c.category, c.status, c.priority, c.location,
               w.ward_name, d.name as department_name, u.name as citizen_name,
               c.created_at, c.updated_at
        FROM complaints c
        LEFT JOIN municipal_wards w ON c.ward_id = w.ward_id
        LEFT JOIN departments d ON c.department_id = d.department_id
        LEFT JOIN users u ON c.user_id = u.user_id
        ORDER BY c.created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Complaint ID', 'Title', 'Category', 'Status', 'Priority',
        'Location', 'Ward', 'Department', 'Citizen', 'Created At', 'Updated At'
    ])
    for row in rows:
        writer.writerow([
            row['complaint_id'], row['title'], row['category'], row['status'],
            row['priority'], row['location'], row['ward_name'],
            row['department_name'], row['citizen_name'], row['created_at'], row['updated_at']
        ])

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=municipal_waste_report_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
    return response

# ----------------- Real-Time JSON API -----------------

@app.route('/api/ward-lookup')
def api_ward_lookup():
    lat = request.args.get('lat')
    lng = request.args.get('lng')
    category = request.args.get('category', 'Garbage dumped on roads')
    if not lat or not lng:
        return jsonify({"error": "Latitude and longitude required"}), 400

    route_info = route_complaint(lat, lng, category)
    return jsonify(route_info)

@app.route('/api/stats')
def api_stats():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM complaints")
    total = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as closed FROM complaints WHERE status = 'Verified and Closed'")
    closed = cursor.fetchone()['closed']
    conn.close()
    return jsonify({"total": total, "closed": closed})

# ----------------- Application Entrypoint -----------------

if __name__ == '__main__':
    init_db()
    seed_db()
    print("\n" + "="*70)
    print("   AI-Based Waste Reporting & Municipality Response System")
    print("   Status: Running on http://127.0.0.1:5000")
    print("="*70 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
