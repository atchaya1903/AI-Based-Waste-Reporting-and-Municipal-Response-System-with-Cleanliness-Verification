# AI-Based Waste Reporting and Municipal Response System with Cleanliness Verification Using YOLO and OpenCV

An intelligent, responsive web platform empowering citizens and municipal authorities with real-time **YOLOv8 object detection**, **OpenCV computer vision processing**, **automated spatial ward and department allotment**, and **photographic before-and-after cleanliness verification**.

---

## 🌟 Key Features

1. **Citizen Waste Reporting Module:**
   - Dual photographic input: Upload image file or capture live with device webcam via HTML5 Canvas.
   - Interactive OpenStreetMap location picker with draggable pin and GPS geolocation.
   - 8 municipal complaint categories (Garbage on roads, Overflowing dustbins, Plastic accumulation, Food/organic waste, Construction debris, Waterways/drainage waste, Illegal dumping, Unclean public spaces).
   - Real-time auto-ward and department detection based on coordinates.
   - Unique Complaint ID generation (e.g. `CMP-2026-X101`).

2. **Real YOLOv8 & OpenCV AI Waste Detection:**
   - Real-time YOLO inference using trained neural network weights (`models/yolov8n.pt`).
   - OpenCV image preprocessing, sharpness validation (Laplacian variance), and custom color-coded bounding boxes.
   - Head-Up Display (HUD) banner overlaid on annotated output showing count, dominant class, and inference timestamp.
   - Structured inventory table displaying object names, waste categories, confidence scores, quantities, and recommended municipal disposal methods.

3. **Intelligent Municipality Allotment Engine:**
   - Spatial distance calculation (Haversine formula) matching latitude and longitude to municipal ward geofence centers.
   - Deterministic category-to-department routing (Sanitation, Organic Composting, Resource Recovery, Eco-Squad Waterways, Hazardous Materials).
   - Priority policy assignment (Critical, High, Medium, Low).

4. **AI-Based Cleanliness Verification Engine (Flagship Feature):**
   - Automatically compares the original citizen complaint photograph (Before) against the sanitation worker's cleanup photograph (After).
   - Runs YOLOv8 object detection on both images.
   - Calculates **Waste Reduction Percentage**:
     $$\text{Waste Reduction \%} = \left(\frac{\text{Before Count} - \text{After Count}}{\text{Before Count}}\right) \times 100$$
   - Measures structural clutter reduction using OpenCV Canny edge density.
   - Measures camera scene consistency using OpenCV ORB feature matching and color histogram correlation.
   - Generates side-by-side composite comparison evidence for administrative audit.
   - Decision matrix: **Passed** ($\ge 80\%$), **Needs Review** ($50\% - 79\%$), or **Failed / Rework Required** ($< 50\%$).

5. **Field Worker Portal:**
   - Active job queue with priority levels, supervisor dispatch notes, and navigation links.
   - One-click "Start Cleanup On-Site" status transition.
   - Cleanup photo submission via file upload or live camera.
   - Rework request handling when verification fails.

6. **Municipality Admin Command Center:**
   - High-level KPI widgets (Total, Pending, In Progress, Verification Queue, Cleanliness Pass Rate).
   - Interactive Leaflet City Map displaying active complaints with color-coded status circles and ward zones.
   - Filterable complaint triage table (by Ward, Status, Priority, Category).
   - Specialist dispatch modal with target resolution deadline.
   - Side-by-side verification review screen with one-click officer approval or rework dispatch.
   - Ward and sanitation department management.
   - Chart.js analytics & downloadable CSV reports.

7. **Citizen Complaint Tracking & In-App Notifications:**
   - Visual 6-step progress stepper:
     `Submitted` &rarr; `AI Analysis Completed` &rarr; `Worker Assigned` &rarr; `Cleanup In Progress` &rarr; `AI Verification` &rarr; `Verified and Closed`
   - Complete audit trail of status transitions with updater names and remarks.
   - Notification center with unread badges.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, FontAwesome 6, Leaflet.js, Chart.js |
| **Backend** | Python Flask, RESTful architecture, Werkzeug Security |
| **AI / Computer Vision** | YOLOv8 (`ultralytics`), OpenCV (`cv2`), NumPy, Pillow |
| **Database** | SQLite (11 normalized tables with foreign keys and cascade rules) |
| **Mapping & GIS** | Leaflet.js with OpenStreetMap tiles, Haversine spatial routing |

---

## 📂 Project Directory Structure

```text
ai_waste_reporting_system/
├── app.py                      # Flask Application factory & routing orchestrator
├── config.py                   # System configuration, paths, thresholds, and routing rules
├── database.py                 # SQLite schema (11 tables), init helper, and seed logic
├── ai_detector.py              # Real YOLOv8 + OpenCV waste detection, HUD banner & classification
├── cleanliness_verifier.py     # Cleanliness verification engine (reduction %, ORB similarity, composite image)
├── ward_router.py              # Spatial ward & department routing engine
├── seed_sample_complaints.py   # Populates test complaints with AI detections & verification reports
├── test_app.py                 # Automated unit and integration test suite
├── requirements.txt            # Python dependencies
├── .env.example                # Sample environment variables
├── README.md                   # Full documentation
├── models/
│   └── yolov8n.pt              # YOLOv8 nano neural network weights
├── uploads/
│   ├── complaints/             # Citizen uploaded Before images
│   ├── cleanups/               # Worker uploaded After images
│   └── annotated/              # OpenCV annotated images & side-by-side composites
├── static/
│   ├── css/
│   │   ├── style.css           # Eco-tech theme, stepper, badges, comparison slider
│   │   └── dashboard.css       # Responsive sidebar, KPI cards, tables
│   ├── js/
│   │   ├── main.js             # Notification management, alerts auto-dismiss
│   │   ├── camera.js           # HTML5 getUserMedia live webcam capture
│   │   ├── map_picker.js       # Leaflet draggable pin location picker & ward lookup
│   │   ├── admin_map.js        # Leaflet city map with complaint markers and ward zones
│   │   └── verification_slider.js # Interactive Before/After image comparison slider
│   └── sample_images/          # Benchmark images for testing
└── templates/
    ├── base.html               # Master layout with navbar, notifications, and footer
    ├── index.html              # Home page with hero, live stats, workflow, and demo logins
    ├── auth/
    │   ├── login.html          # Login page with 1-click test role logins
    │   └── register.html       # Citizen account registration
    ├── citizen/
    │   ├── dashboard.html      # Citizen dashboard with stats and recent reports
    │   ├── report_waste.html   # Report waste (upload/webcam + Leaflet map pin)
    │   ├── detection_result.html # Annotated image, bounding box table & disposal recommendations
    │   ├── my_complaints.html  # Citizen complaint history with status filters
    │   └── track.html          # Live complaint tracking with 6-step progress stepper
    ├── worker/
    │   ├── dashboard.html      # Sanitation worker active task queue
    │   ├── task_detail.html    # Task specifications, GPS navigation link & Start Cleanup
    │   └── upload_cleanup.html # Upload after-cleaning photo & trigger AI verification
    ├── admin/
    │   ├── dashboard.html      # Admin dashboard with city map and Chart.js charts
    │   ├── complaints.html     # Complaint triage, worker dispatch modal & status updates
    │   ├── verification_review.html # Side-by-side comparison & officer approval actions
    │   ├── wards.html          # Ward and department management
    │   └── analytics.html      # Detailed analytics, ward performance & CSV export
    └── common/
        ├── profile.html        # Profile settings and in-app notification center
        └── about.html          # Technical architecture, verification policy & FAQ
```

---

## 🚀 Step-by-Step Setup Instructions (Run Locally in VS Code)

### Prerequisites
- Python 3.9 to 3.13 installed on your system.
- VS Code (or any preferred code editor).

### Step 1: Open the Project Directory in VS Code
Open VS Code, press `Ctrl + K, Ctrl + O` (or `File -> Open Folder...`), and select:
```text
C:\Users\hp\.gemini\antigravity\scratch\ai_waste_reporting_system
```

### Step 2: Open Terminal in VS Code
Open the integrated terminal in VS Code (`Ctrl + ~` or `Terminal -> New Terminal`).

### Step 3: Install Required Dependencies
Run:
```bash
pip install -r requirements.txt
```
*(Dependencies include: `flask`, `werkzeug`, `ultralytics`, `opencv-python`, `numpy`, `Pillow`)*

### Step 4: Initialize and Seed the Database
Initialize the 11 database tables and generate realistic sample complaints, AI detections, and verification records:
```bash
python seed_sample_complaints.py
```

### Step 5: Start the Flask Application
Run:
```bash
python app.py
```
The terminal will display:
```text
======================================================================
   AI-Based Waste Reporting & Municipality Response System
   Status: Running on http://127.0.0.1:5000
======================================================================
```

### Step 6: Open in Browser
Open your browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## 🔑 Pre-Seeded Test Credentials

For fast demonstration and testing, you can click the **Demo Login** buttons on the login page or enter these credentials:

| Role | Email | Password | Access & Responsibilities |
| :--- | :--- | :--- | :--- |
| **Citizen** | `citizen@clean.gov` | `citizen123` | Report waste, capture webcam photos, pick location on Leaflet map, track status. |
| **Sanitation Worker** | `worker@clean.gov` | `worker123` | View assigned tasks, GPS directions, start cleanup, upload after-cleaning photo. |
| **Municipal Officer / Admin** | `admin@clean.gov` | `admin123` | Access city map, dispatch workers, review Before/After verifications, export CSV. |

---

## 🧪 Running Automated Tests

Run the complete test suite to verify database tables, spatial routing, YOLO detection, cleanliness math, and role-based access control:
```bash
python test_app.py
```
Expected output:
```text
........
----------------------------------------------------------------------
Ran 8 tests in ~4.5s

OK
```

---

## 🧠 Training or Configuring Custom YOLO Weights

The application comes pre-packaged with `models/yolov8n.pt`. To deploy custom waste detection weights (e.g. trained on TrashNet, TACO, or municipal datasets):

1. Train your YOLOv8 model using Ultralytics:
   ```python
   from ultralytics import YOLO
   model = YOLO('yolov8n.pt')
   model.train(data='waste_dataset.yaml', epochs=50, imgsz=640)
   ```
2. Copy your best checkpoint `best.pt` into the `models/` directory:
   ```text
   models/custom_waste.pt
   ```
3. Update `config.py` or `.env`:
   ```python
   YOLO_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'custom_waste.pt')
   ```
4. If your model includes custom class labels (e.g. `cardboard`, `glass_bottle`, `e_waste`), update `WASTE_CATEGORY_MAP` in `ai_detector.py` to map them directly to municipal streams.

---

## 📊 Cleanliness Verification Decision Policy

| Status | Reduction % | OpenCV Visual Clutter & Similarity | Action Required |
| :--- | :--- | :--- | :--- |
| **Passed** | $\ge 80.0\%$ | Low edge density, authentic scene match | Recommended for immediate officer approval and closure. |
| **Needs Review** | $50.0\% - 79.9\%$ | Moderate clutter or slight angle variance | Mandatory officer side-by-side inspection before decision. |
| **Failed** | $< 50.0\%$ | High residual clutter or items remaining | Automatically rejected; returned to worker for rework. |

---

## 🛡️ Security & Reliability Implementations
- **Password Hashing:** Uses `werkzeug.security.generate_password_hash` with secure salting.
- **Role-Based Access Control:** Dedicated `@role_required(['admin', 'worker', 'citizen'])` decorators prevent unauthorized route access.
- **File Validation:** Filenames sanitized with `secure_filename`, extension whitelist checked (`png`, `jpg`, `jpeg`, `webp`), max upload limit of 16 MB.
- **Fail-Safe AI Inference:** If model weights are missing or corrupt, the system issues descriptive errors without faking AI data.
- **Audit Trails:** All status transitions, worker assignments, and officer remarks are recorded in `status_history`.
