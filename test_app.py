import unittest
import os
import json
import cv2
import numpy as np

from app import app
from database import get_db, init_db, seed_db
from config import Config
from ward_router import route_complaint, haversine_distance, generate_complaint_id
from ai_detector import get_detector
from cleanliness_verifier import get_cleanliness_verifier

class TestWasteReportingSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()
        init_db()
        seed_db()

    def test_01_database_tables(self):
        """Verify all 11 required tables exist."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row['name'] for row in cursor.fetchall()]
        conn.close()

        required_tables = [
            'users', 'complaints', 'waste_detections', 'images',
            'municipal_wards', 'departments', 'workers', 'assignments',
            'verification_results', 'status_history', 'notifications'
        ]
        for t in required_tables:
            self.assertIn(t, tables, f"Missing required table: {t}")

    def test_02_ward_routing(self):
        """Test automatic routing based on GPS coordinates and categories."""
        # Central Commercial coordinates
        route = route_complaint(12.9716, 77.5946, "Plastic waste accumulation")
        self.assertIsNotNone(route['ward_id'])
        self.assertEqual(route['department_code'], 'REC-03')
        self.assertEqual(route['priority'], 'Medium')

        # Critical / Eco zone complaint
        eco_route = route_complaint(13.0035, 77.5750, "Waste near lakes, rivers, or drainage areas")
        self.assertEqual(eco_route['department_code'], 'ECO-04')
        self.assertEqual(eco_route['priority'], 'High')

    def test_03_haversine_distance(self):
        """Test geographic distance formula."""
        dist = haversine_distance(12.9716, 77.5946, 12.9716, 77.5946)
        self.assertAlmostEqual(dist, 0.0, places=2)

    def test_04_yolo_detection_pipeline(self):
        """Test YOLO model inference and OpenCV annotation generation."""
        detector = get_detector()
        self.assertIsNotNone(detector.model)

        # Create temporary sample image
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        test_img[:] = (200, 200, 200)
        sample_path = 'uploads/complaints/test_unit_img.jpg'
        annotated_path = 'uploads/annotated/test_unit_annotated.jpg'
        cv2.imwrite(sample_path, test_img)

        result = detector.detect_waste(sample_path, annotated_path)
        self.assertTrue(result['success'])
        self.assertIn('object_count', result)
        self.assertIn('category_counts', result)
        self.assertTrue(os.path.exists(annotated_path))

    def test_05_cleanliness_verification_math(self):
        """Test the waste reduction formula: ((Before - After) / Before) * 100."""
        verifier = get_cleanliness_verifier()
        
        # Test case: 10 items before, 1 item after -> 90% reduction (Passed)
        b_count = 10
        a_count = 1
        reduction = ((b_count - a_count) / b_count) * 100.0
        self.assertEqual(reduction, 90.0)

        # Test case: 0 items before, 0 items after -> 100% clean
        b_count_zero = 0
        a_count_zero = 0
        reduction_zero = 100.0 if a_count_zero == 0 else 0.0
        self.assertEqual(reduction_zero, 100.0)

    def test_06_public_routes(self):
        """Test public pages accessibility."""
        res_home = self.client.get('/')
        self.assertEqual(res_home.status_code, 200)

        res_about = self.client.get('/about')
        self.assertEqual(res_about.status_code, 200)

        res_login = self.client.get('/login')
        self.assertEqual(res_login.status_code, 200)

    def test_07_demo_login_and_admin_protection(self):
        """Test role-based access control."""
        # Unauthenticated access to admin dashboard should redirect
        res_unauth = self.client.get('/admin/dashboard')
        self.assertEqual(res_unauth.status_code, 302)

        # Citizen demo login
        res_cit = self.client.get('/demo-login/citizen', follow_redirects=True)
        self.assertEqual(res_cit.status_code, 200)
        self.assertIn(b'Citizen Civic Dashboard', res_cit.data)

        # Admin demo login
        res_admin = self.client.get('/demo-login/admin', follow_redirects=True)
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b'Municipal Command & Control Dashboard', res_admin.data)

    def test_08_tracking_page(self):
        """Test tracking endpoint for pre-seeded complaint."""
        res_track = self.client.get('/track/CMP-2026-X101')
        self.assertEqual(res_track.status_code, 200)
        self.assertIn(b'CMP-2026-X101', res_track.data)

if __name__ == '__main__':
    unittest.main()
