import os
import time
import json
import cv2
import numpy as np
from datetime import datetime
from config import Config

# Attempt to load Ultralytics YOLO
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False

# Mapping of standard objects (from COCO dataset & common custom waste classes) to Municipal Waste Categories
WASTE_CATEGORY_MAP = {
    # Recyclable / Plastic / Glass / Metal
    'bottle': ('Recyclable Waste', 'Plastic & Glass: Segregate for washing and municipal shredding/recycling.'),
    'wine glass': ('Recyclable Waste', 'Glass: Segregate for glass recycling bin; handle with care.'),
    'cup': ('Recyclable Waste', 'Plastic/Paper Cup: Empty liquid, compress, and place in recyclables.'),
    'fork': ('Recyclable Waste', 'Plastic/Metal Cutlery: Recycle with metal or rigid plastics.'),
    'knife': ('Recyclable Waste', 'Cutlery: Place in dry metal/plastic recycling container.'),
    'spoon': ('Recyclable Waste', 'Cutlery: Place in dry metal/plastic recycling container.'),
    'bowl': ('Recyclable Waste', 'Rigid container: Clean residual food and place in dry recyclables.'),
    'can': ('Recyclable Waste', 'Aluminum/Tin Can: Rinse, crush, and place in metal recycling bin.'),
    'box': ('Recyclable Waste', 'Cardboard Box: Flatten and place in paper/cardboard recycling.'),
    'paper': ('Recyclable Waste', 'Paper Waste: Keep dry and bundle for recycling plant.'),
    'plastic_bag': ('Recyclable Waste', 'Soft Plastic: Segregate for plastic film recycling.'),

    # Biodegradable / Organic Waste
    'banana': ('Biodegradable Waste', 'Organic: Divert to municipal wet waste compost plant or biogas unit.'),
    'apple': ('Biodegradable Waste', 'Organic: Place in green bin for municipal compost processing.'),
    'sandwich': ('Biodegradable Waste', 'Food Scrap: Place in wet waste collection bin for composting.'),
    'orange': ('Biodegradable Waste', 'Fruit Peel: Highly compostable wet organic waste.'),
    'broccoli': ('Biodegradable Waste', 'Vegetable Waste: Green bin organic composting.'),
    'carrot': ('Biodegradable Waste', 'Vegetable Waste: Green bin organic composting.'),
    'hot dog': ('Biodegradable Waste', 'Food Waste: Wet collection bin for bio-methanation.'),
    'pizza': ('Biodegradable Waste', 'Food Waste: Dispose of food in green bin; clean box in cardboard bin.'),
    'donut': ('Biodegradable Waste', 'Food Waste: Composting wet waste stream.'),
    'cake': ('Biodegradable Waste', 'Food Waste: Composting wet waste stream.'),
    'potted plant': ('Biodegradable Waste', 'Garden Waste: Municipal leaf & plant pruning compost.'),

    # Hazardous & Electronic Waste
    'cell phone': ('Hazardous Waste', 'E-Waste: Contain in battery safe box; transfer to authorized e-cycler.'),
    'laptop': ('Hazardous Waste', 'E-Waste: Contains lithium cells & metals; do not crush, send to e-waste center.'),
    'mouse': ('Hazardous Waste', 'E-Waste: Plastic & circuitry; segregate for e-waste processing.'),
    'keyboard': ('Hazardous Waste', 'E-Waste: Disassemble for precious metal & plastic recovery.'),
    'tv': ('Hazardous Waste', 'E-Waste: Contains cathode/lead/electronic boards; hazardous handling required.'),
    'remote': ('Hazardous Waste', 'E-Waste: Remove alkaline batteries; segregate electronics.'),
    'microwave': ('Hazardous Waste', 'E-Waste / Metal: Heavy electronic appliance disposal.'),
    'oven': ('Hazardous Waste', 'Bulky E-Waste: Industrial recycling facility required.'),
    'toaster': ('Hazardous Waste', 'Small Appliance: E-waste collection queue.'),
    'hair drier': ('Hazardous Waste', 'Electronic Appliance: E-waste collection queue.'),
    'battery': ('Hazardous Waste', 'Toxic Hazmat: Contains heavy metals; deposit in designated hazmat drop box.'),

    # Non-recyclable / Bulky / Debris
    'backpack': ('Non-recyclable Waste', 'Textile/Mixed Material: If unusable, route to sanitary landfill/refuse.'),
    'handbag': ('Non-recyclable Waste', 'Leather/Mixed: Non-recyclable dry waste.'),
    'suitcase': ('Non-recyclable Waste', 'Bulky Waste: Schedule special municipal bulk pickup.'),
    'umbrella': ('Non-recyclable Waste', 'Composite Waste: Separate metal ribs from nylon fabric.'),
    'book': ('Recyclable Waste', 'Paper Waste: Bundle for library donation or paper pulp recycling.'),
    'vase': ('Non-recyclable Waste', 'Ceramic: Inert mineral waste; do not mix with glass recycling.'),
    'scissors': ('Recyclable Waste', 'Metal scrap: Place in scrap metal bin.'),
    'teddy bear': ('Non-recyclable Waste', 'Textile/Mixed synthetic stuffing.'),
    'toothbrush': ('Non-recyclable Waste', 'Composite plastic & nylon: Red/black bin waste.')
}

# Category BGR Colors for OpenCV rendering
CATEGORY_COLORS = {
    'Recyclable Waste': (220, 150, 20),      # Vivid Blue/Cyan
    'Biodegradable Waste': (46, 184, 92),     # Fresh Green
    'Hazardous Waste': (40, 40, 230),         # Alert Red
    'Non-recyclable Waste': (30, 144, 255),   # Safety Orange
    'General Waste': (160, 160, 160)          # Slate Gray
}

class WasteDetector:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WasteDetector, cls).__new__(cls)
            cls._instance.model_path = Config.YOLO_MODEL_PATH
            cls._instance.load_model()
        return cls._instance

    def load_model(self):
        """Loads YOLOv8 model from disk."""
        if not ULTRALYTICS_AVAILABLE:
            print("[WasteDetector] Ultralytics not installed, using OpenCV fallback.")
            self.model = None
            return

        if os.path.exists(self.model_path):
            try:
                print(f"[WasteDetector] Loading YOLO model from {self.model_path}...")
                self.model = YOLO(self.model_path)
                print(f"[WasteDetector] Model loaded successfully. Class count: {len(self.model.names)}")
            except Exception as e:
                print(f"[WasteDetector] Error loading model: {e}")
                self.model = None
        else:
            print(f"[WasteDetector] Warning: Model file {self.model_path} not found. Attempting auto-load...")
            try:
                self.model = YOLO("yolov8n.pt")
            except Exception as e:
                print(f"[WasteDetector] Could not auto-load yolov8n.pt: {e}")
                self.model = None

    def assess_image_quality(self, image):
        """Assesses image clarity using Laplacian variance."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        is_blurry = variance < 80.0
        return float(round(variance, 2)), is_blurry

    def detect_waste(self, image_path, output_annotated_path=None, conf_thresh=0.25):
        """
        Runs YOLO object detection on the input image.
        Uses OpenCV to annotate bounding boxes, labels, HUD counters, and saves the result.
        Returns a rich structured dictionary.
        """
        start_time = time.time()
        
        if not os.path.exists(image_path):
            return {"success": False, "error": f"Image file not found: {image_path}"}

        # Read image with OpenCV
        image = cv2.imread(image_path)
        if image is None:
            return {"success": False, "error": "Invalid or corrupt image format."}

        h, w, _ = image.shape
        sharpness, is_blurry = self.assess_image_quality(image)

        detections = []
        category_counts = {
            'Biodegradable Waste': 0,
            'Recyclable Waste': 0,
            'Hazardous Waste': 0,
            'Non-recyclable Waste': 0
        }

        if self.model is not None:
            # Run real YOLO inference
            results = self.model.predict(source=image, conf=conf_thresh, verbose=False)
            
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    cls_name = self.model.names.get(cls_id, f"obj_{cls_id}").lower()
                    conf = float(box.conf[0].item())
                    xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                    
                    x1, y1, x2, y2 = [int(v) for v in xyxy]
                    # Clamp coordinates
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w - 1, x2), min(h - 1, y2)

                    # Lookup category & recommended disposal
                    if cls_name in WASTE_CATEGORY_MAP:
                        cat_name, disposal = WASTE_CATEGORY_MAP[cls_name]
                    else:
                        # Fallback heuristic for waste context
                        cat_name = 'Non-recyclable Waste'
                        disposal = 'Mixed Municipal Solid Waste: Transfer to sorting station.'

                    category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

                    detections.append({
                        "class_name": cls_name.capitalize(),
                        "category": cat_name,
                        "confidence": round(conf * 100, 1),
                        "bbox": [x1, y1, x2, y2],
                        "disposal_method": disposal
                    })
        else:
            return {"success": False, "error": "YOLO model is unavailable. Please verify model weights."}

        # Draw OpenCV annotations
        annotated_img = image.copy()
        
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            cat = det["category"]
            color = CATEGORY_COLORS.get(cat, (0, 255, 0))
            label = f"{det['class_name']} {det['confidence']}%"

            # Draw outer rectangle with corner accents
            cv2.rectangle(annotated_img, (x1, y1), (x2, y2), color, 2)
            
            # Corner accents for a modern AI aesthetic
            corner_len = min(20, (x2 - x1) // 3, (y2 - y1) // 3)
            if corner_len > 3:
                # Top-left
                cv2.line(annotated_img, (x1, y1), (x1 + corner_len, y1), color, 4)
                cv2.line(annotated_img, (x1, y1), (x1, y1 + corner_len), color, 4)
                # Bottom-right
                cv2.line(annotated_img, (x2, y2), (x2 - corner_len, y2), color, 4)
                cv2.line(annotated_img, (x2, y2), (x2, y2 - corner_len), color, 4)

            # Label banner
            (lbl_w, lbl_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated_img, (x1, max(0, y1 - lbl_h - 8)), (x1 + lbl_w + 10, y1), color, -1)
            cv2.putText(annotated_img, label, (x1 + 5, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        # Top HUD Dashboard Bar
        total_items = len(detections)
        hud_height = 42
        hud_overlay = annotated_img.copy()
        cv2.rectangle(hud_overlay, (0, 0), (w, hud_height), (15, 23, 42), -1)  # Dark slate background
        cv2.addWeighted(hud_overlay, 0.85, annotated_img, 0.15, 0, annotated_img)

        # HUD Text
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        hud_text = f"AI DETECTION: {total_items} Waste Items Detected | Conf: >= {int(conf_thresh*100)}% | {timestamp_str}"
        cv2.putText(annotated_img, hud_text, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)

        # Save annotated image
        if output_annotated_path:
            os.makedirs(os.path.dirname(output_annotated_path), exist_ok=True)
            cv2.imwrite(output_annotated_path, annotated_img)

        inference_time = round((time.time() - start_time) * 1000, 1)

        # Determine dominant category
        dominant_cat = max(category_counts, key=category_counts.get) if total_items > 0 else "None"

        return {
            "success": True,
            "object_count": total_items,
            "category_counts": category_counts,
            "dominant_category": dominant_cat,
            "detections": detections,
            "sharpness_score": sharpness,
            "is_blurry": is_blurry,
            "inference_time_ms": inference_time,
            "annotated_path": output_annotated_path
        }

# Global singleton helper
_detector = None
def get_detector():
    global _detector
    if _detector is None:
        _detector = WasteDetector()
    return _detector
