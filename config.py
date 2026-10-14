import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'anti-gravity-clean-city-secret-key-2026')
    DATABASE_PATH = os.path.join(BASE_DIR, 'waste_system.db')
    
    # Upload folders
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    COMPLAINT_UPLOADS = os.path.join(UPLOAD_FOLDER, 'complaints')
    CLEANUP_UPLOADS = os.path.join(UPLOAD_FOLDER, 'cleanups')
    ANNOTATED_UPLOADS = os.path.join(UPLOAD_FOLDER, 'annotated')
    
    # Allowed extensions
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max
    
    # AI Models
    YOLO_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'yolov8n.pt')
    YOLO_CONFIDENCE_THRESHOLD = 0.25
    
    # Cleanliness Verification Policy
    VERIFICATION_PASS_THRESHOLD = 80.0   # >= 80% waste reduction passes
    VERIFICATION_REVIEW_THRESHOLD = 50.0 # 50% - 79% requires officer review
    
    # Default Map Coordinates (City Center - e.g. Metropolis Municipal Corp)
    DEFAULT_MAP_LAT = 12.9716
    DEFAULT_MAP_LNG = 77.5946
    DEFAULT_MAP_ZOOM = 13

    # Complaint Categories
    COMPLAINT_CATEGORIES = [
        "Garbage dumped on roads",
        "Overflowing dustbins",
        "Plastic waste accumulation",
        "Food and organic waste",
        "Construction debris",
        "Waste near lakes, rivers, or drainage areas",
        "Illegal dumping",
        "Unclean streets and public places"
    ]
