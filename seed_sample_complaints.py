import os
import cv2
import numpy as np
import json
from datetime import datetime
from database import get_db, init_db, seed_db
from config import Config
from ai_detector import get_detector
from cleanliness_verifier import get_cleanliness_verifier

def create_waste_image(filename, has_items=True, item_types=None):
    """Generates an image with simulated waste items and textures for YOLO/OpenCV testing."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Concrete pavement background
    img[:] = (210, 215, 220)
    # Add subtle asphalt texture noise
    noise = np.random.randint(-15, 15, (480, 640, 3), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Road curb / line
    cv2.line(img, (0, 320), (640, 320), (140, 145, 150), 3)

    if has_items:
        # Draw items (bottles, containers, organic scraps)
        # Bottle 1 (blue plastic)
        cv2.rectangle(img, (140, 240), (190, 360), (220, 100, 30), -1)
        cv2.circle(img, (165, 235), 12, (250, 150, 50), -1)
        # Bottle 2 (green soda bottle)
        cv2.rectangle(img, (220, 280), (265, 390), (40, 180, 50), -1)
        # Cup / carton
        cv2.rectangle(img, (310, 270), (370, 350), (240, 240, 240), -1)
        cv2.putText(img, "COFFEE", (315, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (20, 20, 20), 1)
        # Apple / organic peel
        cv2.circle(img, (420, 310), 25, (30, 30, 220), -1)
        cv2.ellipse(img, (480, 330), (35, 15), 30, 0, 360, (20, 210, 240), -1)

    filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    cv2.imwrite(filepath, img)
    return filepath

def populate_samples():
    init_db()
    seed_db()
    detector = get_detector()
    verifier = get_cleanliness_verifier()

    conn = get_db()
    cursor = conn.cursor()

    # Check if complaints already exist
    cursor.execute("SELECT COUNT(*) as cnt FROM complaints")
    if cursor.fetchone()['cnt'] > 0:
        print("[Seed] Complaints already present in DB.")
        conn.close()
        return

    print("[Seed] Generating realistic sample complaints with AI detections...")

    # Citizen ID is 4 from seed_db
    user_id = 4

    # 1. Complaint 1: Active In Progress (Plastic bottle accumulation)
    cid_1 = "CMP-2026-X101"
    b1_path = create_waste_image("complaints/CMP-2026-X101_before.jpg", has_items=True)
    a1_path = os.path.join(Config.ANNOTATED_UPLOADS, "CMP-2026-X101_annotated.jpg")
    det1 = detector.detect_waste(b1_path, a1_path)

    cursor.execute('''
        INSERT INTO complaints (complaint_id, user_id, title, description, category, location, latitude, longitude, ward_id, department_id, status, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        cid_1, user_id, "Plastic bottle accumulation along lake walkway",
        "Multiple discarded beverage bottles and plastic food wrappers scattered along the pedestrian pavement.",
        "Plastic waste accumulation", "Lake Promenade, Near North Gate, Ward 2",
        13.0035, 77.5750, 2, 3, "Worker Assigned", "Medium"
    ))

    cursor.execute('''
        INSERT INTO images (complaint_id, image_type, file_path, annotated_path)
        VALUES (?, 'before', ?, ?)
    ''', (cid_1, "uploads/complaints/CMP-2026-X101_before.jpg", "uploads/annotated/CMP-2026-X101_annotated.jpg"))
    img_id_1 = cursor.lastrowid

    # Add simulated waste detections
    cursor.execute('''
        INSERT INTO waste_detections (complaint_id, image_id, model_name, class_label, confidence, object_count, bounding_boxes)
        VALUES (?, ?, 'YOLOv8-Nano', 'Bottle', 91.5, 2, ?)
    ''', (cid_1, img_id_1, json.dumps([[140, 240, 190, 360], [220, 280, 265, 390]])))
    cursor.execute('''
        INSERT INTO waste_detections (complaint_id, image_id, model_name, class_label, confidence, object_count, bounding_boxes)
        VALUES (?, ?, 'YOLOv8-Nano', 'Cup', 85.2, 1, ?)
    ''', (cid_1, img_id_1, json.dumps([[310, 270, 370, 350]])))

    # Assign to worker Ramesh Kumar (worker_id 1)
    cursor.execute('''
        INSERT INTO assignments (complaint_id, worker_id, assigned_by, deadline, notes, status)
        VALUES (?, 1, 1, '2026-10-15 18:00:00', 'Clear plastic accumulation before evening park visitors arrive.', 'Assigned')
    ''', (cid_1,))

    cursor.execute('''
        INSERT INTO status_history (complaint_id, previous_status, new_status, updated_by, remarks)
        VALUES (?, 'Submitted', 'Worker Assigned', 1, 'Dispatched Sanitation Specialist Ramesh Kumar with vehicle KA-01-EA-4412.')
    ''', (cid_1,))

    # 2. Complaint 2: Fully Cleaned and Verified (Food and organic waste)
    cid_2 = "CMP-2026-Z303"
    b2_path = create_waste_image("complaints/CMP-2026-Z303_before.jpg", has_items=True)
    a2_path = create_waste_image("cleanups/CMP-2026-Z303_after.jpg", has_items=False)

    cursor.execute('''
        INSERT INTO complaints (complaint_id, user_id, title, description, category, location, latitude, longitude, ward_id, department_id, status, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        cid_2, user_id, "Food waste and organic scraps dumped at commercial corner",
        "Vegetable peels and food waste overflowing from restaurant rear alley.",
        "Food and organic waste", "Corner 4th Cross, Brigade Road, Ward 1",
        12.9716, 77.5946, 1, 2, "Verified and Closed", "High"
    ))

    cursor.execute('''
        INSERT INTO images (complaint_id, image_type, file_path, annotated_path)
        VALUES (?, 'before', ?, ?)
    ''', (cid_2, "uploads/complaints/CMP-2026-Z303_before.jpg", "uploads/annotated/CMP-2026-Z303_before_annotated.jpg"))
    cursor.execute('''
        INSERT INTO images (complaint_id, image_type, file_path, annotated_path)
        VALUES (?, 'after', ?, ?)
    ''', (cid_2, "uploads/cleanups/CMP-2026-Z303_after.jpg", "uploads/annotated/CMP-2026-Z303_after_annotated.jpg"))

    # Run real verifier
    v_res = verifier.verify_cleanup(b2_path, a2_path, cid_2)
    cursor.execute('''
        INSERT INTO verification_results (
            complaint_id, before_count, after_count, reduction_percentage,
            verification_status, review_notes, similarity_score, clutter_reduction, verified_by
        ) VALUES (?, 6, 0, 100.0, 'Passed', 'AI verification confirmed 100% waste clearance. Officer closed complaint.', 0.88, 72.4, 1)
    ''', (cid_2,))

    cursor.execute('''
        INSERT INTO assignments (complaint_id, worker_id, assigned_by, deadline, notes, status)
        VALUES (?, 2, 1, '2026-10-14 12:00:00', 'Priority organic collection.', 'Completed')
    ''', (cid_2,))

    cursor.execute('''
        INSERT INTO status_history (complaint_id, previous_status, new_status, updated_by, remarks)
        VALUES (?, 'Cleanup In Progress', 'Verified and Closed', 1, 'AI Cleanliness Verification passed with 100% reduction. Closed by Municipal Officer Sharma.')
    ''', (cid_2,))

    # 3. Complaint 3: Drainage obstruction (High Priority)
    cid_3 = "CMP-2026-W404"
    b3_path = create_waste_image("complaints/CMP-2026-W404_before.jpg", has_items=True)
    cursor.execute('''
        INSERT INTO complaints (complaint_id, user_id, title, description, category, location, latitude, longitude, ward_id, department_id, status, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        cid_3, user_id, "Severe waste accumulation blocking stormwater drainage canal",
        "Plastic bags, broken crates, and silt obstructing natural rainwater outflow.",
        "Waste near lakes, rivers, or drainage areas", "Storm Drain Culver 12, Ward 3",
        12.9250, 77.5850, 3, 4, "AI Analysis Completed", "Critical"
    ))
    cursor.execute('''
        INSERT INTO images (complaint_id, image_type, file_path, annotated_path)
        VALUES (?, 'before', ?, ?)
    ''', (cid_3, "uploads/complaints/CMP-2026-W404_before.jpg", "uploads/annotated/CMP-2026-W404_before_annotated.jpg"))
    cursor.execute('''
        INSERT INTO status_history (complaint_id, previous_status, new_status, updated_by, remarks)
        VALUES (?, 'Submitted', 'AI Analysis Completed', ?, 'Complaint logged and flagged as Critical Priority by AI routing engine.')
    ''', (cid_3, user_id))

    conn.commit()
    conn.close()
    print("[Seed] Successfully generated realistic sample complaints with AI detections and verification reports!")

if __name__ == '__main__':
    populate_samples()
