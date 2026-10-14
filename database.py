import sqlite3
import os
import json
from datetime import datetime
from werkzeug.security import generate_password_hash
from config import Config

def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('citizen', 'worker', 'admin')),
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 6. Departments table (create before municipal_wards for FK)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            department_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            contact_details TEXT,
            email TEXT,
            phone TEXT
        )
    ''')

    # 5. Municipal_Wards table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS municipal_wards (
            ward_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ward_name TEXT NOT NULL,
            ward_code TEXT NOT NULL UNIQUE,
            boundary_information TEXT,
            department_id INTEGER,
            lat_center REAL NOT NULL,
            lng_center REAL NOT NULL,
            description TEXT,
            FOREIGN KEY (department_id) REFERENCES departments(department_id)
        )
    ''')

    # 7. Workers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workers (
            worker_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            department_id INTEGER NOT NULL,
            availability TEXT NOT NULL DEFAULT 'available' CHECK(availability IN ('available', 'busy', 'offline')),
            vehicle_no TEXT,
            phone TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(department_id)
        )
    ''')

    # 2. Complaints table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            complaint_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            ward_id INTEGER,
            department_id INTEGER,
            status TEXT NOT NULL DEFAULT 'Submitted',
            priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High', 'Critical')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (ward_id) REFERENCES municipal_wards(ward_id),
            FOREIGN KEY (department_id) REFERENCES departments(department_id)
        )
    ''')

    # 4. Images table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            image_id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT NOT NULL,
            image_type TEXT NOT NULL CHECK(image_type IN ('before', 'after')),
            file_path TEXT NOT NULL,
            annotated_path TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id) ON DELETE CASCADE
        )
    ''')

    # 3. Waste_Detections table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS waste_detections (
            detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT NOT NULL,
            image_id INTEGER,
            model_name TEXT NOT NULL,
            class_label TEXT NOT NULL,
            confidence REAL NOT NULL,
            object_count INTEGER NOT NULL DEFAULT 1,
            bounding_boxes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id) ON DELETE CASCADE,
            FOREIGN KEY (image_id) REFERENCES images(image_id)
        )
    ''')

    # 8. Assignments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT NOT NULL,
            worker_id INTEGER NOT NULL,
            assigned_by INTEGER,
            assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deadline TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'Assigned' CHECK(status IN ('Assigned', 'In Progress', 'Completed', 'Reassigned')),
            notes TEXT,
            FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id) ON DELETE CASCADE,
            FOREIGN KEY (worker_id) REFERENCES workers(worker_id),
            FOREIGN KEY (assigned_by) REFERENCES users(user_id)
        )
    ''')

    # 9. Verification_Results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_results (
            verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT NOT NULL,
            before_count INTEGER NOT NULL,
            after_count INTEGER NOT NULL,
            reduction_percentage REAL NOT NULL,
            verification_status TEXT NOT NULL CHECK(verification_status IN ('Passed', 'Needs Review', 'Failed')),
            review_notes TEXT,
            similarity_score REAL DEFAULT 0.0,
            clutter_reduction REAL DEFAULT 0.0,
            verified_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id) ON DELETE CASCADE,
            FOREIGN KEY (verified_by) REFERENCES users(user_id)
        )
    ''')

    # 10. Status_History table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS status_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            updated_by INTEGER,
            remarks TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id) ON DELETE CASCADE,
            FOREIGN KEY (updated_by) REFERENCES users(user_id)
        )
    ''')

    # 11. Notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            complaint_id TEXT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            read_status INTEGER NOT NULL DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id) ON DELETE SET NULL
        )
    ''')

    conn.commit()
    conn.close()
    print("[Database] All 11 tables verified and initialized.")

def seed_db():
    conn = get_db()
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()['count'] > 0:
        conn.close()
        return

    print("[Database] Seeding initial departments, wards, users, and workers...")

    # Departments
    departments = [
        ("Ward Sanitation & Street Cleaning Division", "SAN-01", "Central Municipal Office, Block A", "sanitation@clean.gov", "+91 80 2266 0001"),
        ("Organic & Food Waste Management Wing", "ORG-02", "Compost Processing Facility 3", "organic@clean.gov", "+91 80 2266 0002"),
        ("Plastic & Recycling Collection Unit", "REC-03", "Resource Recovery Center East", "recycling@clean.gov", "+91 80 2266 0003"),
        ("River, Lake & Drainage Eco-Squad", "ECO-04", "Waterfront Preservation Bureau", "ecosquad@clean.gov", "+91 80 2266 0004"),
        ("Construction & Debris Clearance Taskforce", "CDB-05", "Heavy Machinery Yard 2", "debris@clean.gov", "+91 80 2266 0005"),
        ("Hazardous & Electronic Waste Wing", "HAZ-06", "Special Materials Facility", "hazmat@clean.gov", "+91 80 2266 0006")
    ]
    cursor.executemany('''
        INSERT INTO departments (name, code, contact_details, email, phone)
        VALUES (?, ?, ?, ?, ?)
    ''', departments)

    # Municipal Wards (Sample coordinates around city center: 12.9716, 77.5946)
    wards = [
        ("Ward 1 - Central Commercial", "WARD-01", "Central Metro Plaza, Brigade Road, MG Road", 1, 12.9716, 77.5946, "High footfall commercial district with heavy daily waste generation."),
        ("Ward 2 - North Lake & Green Belt", "WARD-02", "Sankey Lake, Sadashivanagar, Malleshwaram", 4, 13.0035, 77.5750, "Eco-sensitive zone containing lakes, parks, and protected green tree covers."),
        ("Ward 3 - South Residential Colony", "WARD-03", "Jayanagar, JP Nagar, Banashankari", 2, 12.9250, 77.5850, "High density residential area with extensive kitchen and dry waste."),
        ("Ward 4 - East IT Corridor & Markets", "WARD-04", "Indiranagar, Koramangala, Old Airport Road", 3, 12.9352, 77.6245, "Rapidly developing tech corridor with commercial packaging and plastic waste."),
        ("Ward 5 - West Industrial & Freight Estate", "WARD-05", "Peenya, Rajajinagar, Yeshwanthpur", 5, 13.0285, 77.5180, "Heavy industrial area requiring specialized debris and bulk waste logistics.")
    ]
    cursor.executemany('''
        INSERT INTO municipal_wards (ward_name, ward_code, boundary_information, department_id, lat_center, lng_center, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', wards)

    # Users: Admin, Worker, Citizen
    pwd_admin = generate_password_hash("admin123")
    pwd_worker = generate_password_hash("worker123")
    pwd_worker2 = generate_password_hash("worker123")
    pwd_citizen = generate_password_hash("citizen123")

    users = [
        ("Chief Municipal Officer Sharma", "admin@clean.gov", pwd_admin, "admin", "+91 98450 11001"),
        ("Sanitation Worker Ramesh Kumar", "worker@clean.gov", pwd_worker, "worker", "+91 98450 22002"),
        ("Field Specialist Priya Nair", "worker2@clean.gov", pwd_worker2, "worker", "+91 98450 22003"),
        ("Citizen Ananya Verma", "citizen@clean.gov", pwd_citizen, "citizen", "+91 98450 33003")
    ]
    cursor.executemany('''
        INSERT INTO users (name, email, password_hash, role, phone)
        VALUES (?, ?, ?, ?, ?)
    ''', users)

    # Workers entries
    # Ramesh Kumar (user_id 2) -> Dept 1 (Sanitation)
    # Priya Nair (user_id 3) -> Dept 2 (Organic)
    workers_data = [
        (2, 1, 'available', 'KA-01-EA-4412', '+91 98450 22002'),
        (3, 2, 'available', 'KA-01-EA-8890', '+91 98450 22003')
    ]
    cursor.executemany('''
        INSERT INTO workers (user_id, department_id, availability, vehicle_no, phone)
        VALUES (?, ?, ?, ?, ?)
    ''', workers_data)

    conn.commit()
    conn.close()
    print("[Database] Seed data successfully applied.")

if __name__ == '__main__':
    init_db()
    seed_db()
