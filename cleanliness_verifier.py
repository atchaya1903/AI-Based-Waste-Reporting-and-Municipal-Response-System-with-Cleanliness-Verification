import os
import cv2
import numpy as np
from datetime import datetime
from config import Config
from ai_detector import get_detector

def compute_scene_similarity(img1, img2):
    """
    Computes visual and structural similarity between before and after images
    using ORB feature matching and color histogram correlation.
    Returns a score between 0.0 and 1.0.
    """
    try:
        # Resize both to standard dimensions for comparison
        target_size = (640, 480)
        im1_std = cv2.resize(img1, target_size)
        im2_std = cv2.resize(img2, target_size)

        # 1. Color Histogram Correlation
        hsv1 = cv2.cvtColor(im1_std, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(im2_std, cv2.COLOR_BGR2HSV)
        
        hist1 = cv2.calcHist([hsv1], [0, 1], None, [50, 60], [0, 180, 0, 256])
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)
        
        hist_corr = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        hist_score = max(0.0, min(1.0, (hist_corr + 1.0) / 2.0))

        # 2. ORB Feature Matching
        orb = cv2.ORB_create(nfeatures=500)
        gray1 = cv2.cvtColor(im1_std, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(im2_std, cv2.COLOR_BGR2GRAY)
        
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)

        feature_score = 0.5
        if des1 is not None and des2 is not None and len(des1) > 10 and len(des2) > 10:
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)
            if matches:
                good_matches = [m for m in matches if m.distance < 60]
                feature_score = min(1.0, len(good_matches) / 50.0)

        # Weighted combination
        combined_score = round(0.6 * hist_score + 0.4 * feature_score, 3)
        return combined_score
    except Exception as e:
        print(f"[CleanlinessVerifier] Similarity error: {e}")
        return 0.5

def compute_clutter_density(image):
    """
    Computes high-frequency edge density to measure visible debris and surface clutter.
    """
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        edge_pixel_ratio = np.count_nonzero(edges) / (edges.shape[0] * edges.shape[1])
        return edge_pixel_ratio
    except Exception:
        return 0.0

def create_comparison_composite(before_img, after_img, before_count, after_count, reduction_pct, status, output_path):
    """
    Creates a side-by-side composite comparison image with header, metrics banner,
    and color-coded verification badge.
    """
    target_h, target_w = 480, 640
    b_resized = cv2.resize(before_img, (target_w, target_h))
    a_resized = cv2.resize(after_img, (target_w, target_h))

    # Add labels on individual images
    cv2.putText(b_resized, f"BEFORE CLEANING: {before_count} Items", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2, cv2.LINE_AA)
    cv2.putText(a_resized, f"AFTER CLEANING: {after_count} Items", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)

    # Combine side-by-side
    composite = np.hstack((b_resized, a_resized))
    comp_h, comp_w, _ = composite.shape

    # Add top banner
    banner_h = 70
    banner = np.zeros((banner_h, comp_w, 3), dtype=np.uint8)
    banner[:] = (15, 23, 42)  # Dark slate

    status_color = (46, 184, 92) if status == "Passed" else ((30, 144, 255) if status == "Needs Review" else (40, 40, 230))
    cv2.putText(banner, "AI CLEANLINESS VERIFICATION REPORT", (25, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    
    badge_text = f"STATUS: {status.upper()} ({reduction_pct:.1f}% WASTE REDUCTION)"
    (bw, bh), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    cv2.rectangle(banner, (comp_w - bw - 40, 15), (comp_w - 20, 55), status_color, -1)
    cv2.putText(banner, badge_text, (comp_w - bw - 30, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

    # Vertical divider
    cv2.line(composite, (target_w, 0), (target_w, comp_h), (255, 255, 255), 3)

    final_composite = np.vstack((banner, composite))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, final_composite)
    return output_path

class CleanlinessVerifier:
    def __init__(self):
        self.detector = get_detector()

    def verify_cleanup(self, before_image_path, after_image_path, complaint_id):
        """
        Runs comprehensive before-and-after cleanliness verification:
        1. YOLO inference on Before photo
        2. YOLO inference on After photo
        3. Waste reduction percentage calculation
        4. Scene similarity & clutter reduction analysis
        5. Recommendation and status evaluation
        6. Side-by-side composite comparison generation
        """
        if not os.path.exists(before_image_path):
            return {"success": False, "error": f"Before image not found: {before_image_path}"}
        if not os.path.exists(after_image_path):
            return {"success": False, "error": f"After image not found: {after_image_path}"}

        # Paths for annotated outputs
        before_annotated_name = f"{complaint_id}_before_annotated.jpg"
        after_annotated_name = f"{complaint_id}_after_annotated.jpg"
        composite_name = f"{complaint_id}_comparison_composite.jpg"

        before_annotated_path = os.path.join(Config.ANNOTATED_UPLOADS, before_annotated_name)
        after_annotated_path = os.path.join(Config.ANNOTATED_UPLOADS, after_annotated_name)
        composite_path = os.path.join(Config.ANNOTATED_UPLOADS, composite_name)

        # 1. Run detection on Before image
        before_result = self.detector.detect_waste(
            before_image_path,
            output_annotated_path=before_annotated_path,
            conf_thresh=Config.YOLO_CONFIDENCE_THRESHOLD
        )
        if not before_result.get("success"):
            return {"success": False, "error": f"Before image inference failed: {before_result.get('error')}"}

        # 2. Run detection on After image
        after_result = self.detector.detect_waste(
            after_image_path,
            output_annotated_path=after_annotated_path,
            conf_thresh=Config.YOLO_CONFIDENCE_THRESHOLD
        )
        if not after_result.get("success"):
            return {"success": False, "error": f"After image inference failed: {after_result.get('error')}"}

        before_count = before_result["object_count"]
        after_count = after_result["object_count"]

        # 3. Calculate Waste Reduction Percentage
        # Formula: ((Before Waste Count − After Waste Count) / Before Waste Count) × 100
        if before_count > 0:
            reduction_percentage = ((before_count - after_count) / float(before_count)) * 100.0
            reduction_percentage = max(0.0, min(100.0, reduction_percentage))
        else:
            # Handle case where initial count is zero
            if after_count == 0:
                reduction_percentage = 100.0
            else:
                reduction_percentage = 0.0

        reduction_percentage = round(reduction_percentage, 1)

        # 4. OpenCV Visual & Clutter Analysis
        b_img = cv2.imread(before_image_path)
        a_img = cv2.imread(after_image_path)

        similarity_score = compute_scene_similarity(b_img, a_img)
        
        b_clutter = compute_clutter_density(b_img)
        a_clutter = compute_clutter_density(a_img)
        clutter_reduction = 0.0
        if b_clutter > 0:
            clutter_reduction = round(max(0.0, ((b_clutter - a_clutter) / b_clutter) * 100.0), 1)

        # 5. Determine Verification Status & Recommendation
        # Policy rules:
        # Pass: Reduction >= 80% and after_count <= 2
        # Needs Review: Reduction 50-79% or low scene similarity
        # Failed: Reduction < 50% or waste items increased
        if reduction_percentage >= Config.VERIFICATION_PASS_THRESHOLD and after_count <= 2:
            verification_status = "Passed"
            recommendation = (
                f"Significant cleanliness improvement verified ({reduction_percentage}% reduction). "
                f"Remaining waste objects: {after_count}. "
                "Recommendation: Officer approval for verified closure."
            )
        elif reduction_percentage >= Config.VERIFICATION_REVIEW_THRESHOLD:
            verification_status = "Needs Review"
            recommendation = (
                f"Moderate cleanliness improvement detected ({reduction_percentage}% reduction). "
                f"Remaining waste objects: {after_count}. "
                "Recommendation: Officer manual review required before complaint resolution."
            )
        else:
            verification_status = "Failed"
            recommendation = (
                f"Insufficient cleaning verified. Waste reduction is only {reduction_percentage}%. "
                f"Remaining waste objects: {after_count}. "
                "Recommendation: Reject completion and reassign to worker for thorough cleaning."
            )

        if similarity_score < 0.35:
            recommendation += " Notice: Camera angle or lighting differs noticeably from the complaint image. Verify site location."

        # 6. Generate Composite Comparison Image
        b_disp = cv2.imread(before_annotated_path)
        if b_disp is None:
            b_disp = b_img
        a_disp = cv2.imread(after_annotated_path)
        if a_disp is None:
            a_disp = a_img

        create_comparison_composite(
            b_disp,
            a_disp,
            before_count,
            after_count,
            reduction_percentage,
            verification_status,
            composite_path
        )

        return {
            "success": True,
            "complaint_id": complaint_id,
            "before_count": before_count,
            "after_count": after_count,
            "reduction_percentage": reduction_percentage,
            "verification_status": verification_status,
            "similarity_score": similarity_score,
            "clutter_reduction": clutter_reduction,
            "recommendation": recommendation,
            "before_annotated_url": f"/uploads/annotated/{before_annotated_name}",
            "after_annotated_url": f"/uploads/annotated/{after_annotated_name}",
            "composite_url": f"/uploads/annotated/{composite_name}",
            "before_result": before_result,
            "after_result": after_result
        }

# Global singleton
_verifier = None
def get_cleanliness_verifier():
    global _verifier
    if _verifier is None:
        _verifier = CleanlinessVerifier()
    return _verifier
