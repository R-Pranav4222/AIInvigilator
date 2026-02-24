"""
Front.py Integration Module - Add Hybrid Detection to Your System
Drop-in replacement for hybrid_detector import in front.py
"""

from enhanced_hybrid_detector import EnhancedHybridDetector
import cv2

class FrontPyHybridIntegration:
    """
    Easy integration wrapper for front.py
    Handles both rule-based and ML detection with visual feedback + logging
    """
    
    def __init__(self, 
                 custom_model_path="runs/train/malpractice_detector/weights/best.pt",
                 voting_mode='any',
                 enable_visual_feedback=True):
        """
        Initialize hybrid detector for front.py
        
        Args:
            custom_model_path: Path to trained model
            voting_mode: 'any', 'majority', or 'all'
            enable_visual_feedback: Show detection text on frame
        """
        print("\n🚀 Initializing Hybrid Detection for front.py...")
        
        self.detector = EnhancedHybridDetector(
            custom_model_path=custom_model_path,
            voting_mode=voting_mode,
            use_custom_model=True,
            custom_threshold=0.25
        )
        
        self.enable_visual = enable_visual_feedback
        
        # Color mapping (matching front.py colors)
        self.action_colors = {
            'mobile': (0, 0, 255),           # Red
            'passing': (255, 0, 0),          # Blue
            'leaning': (0, 0, 255),          # Red
            'turning': (255, 0, 255),        # Magenta
            'hand_raise': (0, 255, 255),     # Cyan
            'phone': (0, 0, 255),            # Red
            'passing_paper': (255, 0, 0),    # Blue
            'turning_back': (255, 0, 255),   # Magenta
        }
        
        # Text positions (matching front.py layout)
        self.text_positions = {
            'leaning': (850, 100),
            'turning': (850, 130),
            'hand_raise': (850, 160),
            'passing': (850, 190),
            'mobile': (850, 220),
            'phone': (850, 220),
        }
        
        print("✅ Hybrid detection ready!\n")
    
    def check_detection(self, frame, detection_type, cv_detected, bbox=None):
        """
        Check if action should be logged (combines CV + ML)
        
        Args:
            frame: Current video frame
            detection_type: 'mobile', 'passing', 'leaning', 'turning', 'hand_raise'
            cv_detected: Boolean from your CV rules
            bbox: Optional bounding box [x1, y1, x2, y2]
        
        Returns:
            should_log (bool): True if detection confirmed
            confidence (float): Detection confidence (0-1)
            method (str): 'cv_only', 'ml_only', 'both_agree'
        """
        # Run hybrid detection
        detected, confidence, info = self.detector.detect_hybrid(
            frame=frame,
            cv_detection=cv_detected,
            detection_type=detection_type,
            bbox=bbox
        )
        
        return detected, confidence, info['method']
    
    def draw_detection_text(self, frame, detection_type, confidence=1.0):
        """
        Draw detection text on frame (front.py style)
        
        Args:
            frame: Frame to draw on
            detection_type: Type of detection
            confidence: Detection confidence
        """
        if not self.enable_visual:
            return frame
        
        # Get display name
        display_names = {
            'mobile': 'USING MOBILE',
            'passing': 'PASSING PAPER',
            'leaning': 'LEANING',
            'turning': 'TURNING BACK',
            'hand_raise': 'HAND RAISED',
            'phone': 'USING PHONE',
        }
        
        display_text = display_names.get(detection_type, detection_type.upper())
        color = self.action_colors.get(detection_type, (255, 255, 255))
        position = self.text_positions.get(detection_type, (850, 250))
        
        # Draw text (front.py style: large text with exclamation)
        cv2.putText(frame, f"{display_text}!", position,
                   cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)
        
        # Optional: show confidence
        if confidence < 0.95:
            conf_text = f"({int(confidence*100)}%)"
            conf_pos = (position[0], position[1] + 25)
            cv2.putText(frame, conf_text, conf_pos,
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        return frame
    
    def get_ml_detections(self, frame, conf_threshold=0.25):
        """
        Run ML model on full frame to catch things CV rules might miss
        
        Returns:
            List of detections: [{'class': 'passing', 'confidence': 0.85, 'bbox': [x1,y1,x2,y2]}, ...]
        """
        return self.detector.run_full_detection(frame, conf_threshold)
    
    def print_stats(self):
        """Print detection statistics"""
        self.detector.print_stats()


# Example usage in front.py:
"""
# At the top of front.py, replace:
# from hybrid_detector import HybridDetector

# With:
from front_integration import FrontPyHybridIntegration

# Initialize (one time, after loading other models)
hybrid = FrontPyHybridIntegration(
    custom_model_path="runs/train/malpractice_detector/weights/best.pt",
    voting_mode='any',  # Change to 'all' for stricter detection
    enable_visual_feedback=True
)

# In your detection loop, replace:
# if passing_detected:
#     passing_frames += 1

# With:
passing_detected_cv = detect_passing_paper(wrist_positions, all_keypoints)
passing_detected, confidence, method = hybrid.check_detection(
    frame=frame,
    detection_type='passing',
    cv_detected=passing_detected_cv,
    bbox=None  # Or pass person bounding box
)

if passing_detected:
    passing_frames += 1
    # Draw detection text
    frame = hybrid.draw_detection_text(frame, 'passing', confidence)
    
    # Optional: log method type
    if method == 'both_agree':
        print("🔥 HIGH CONFIDENCE: Both CV and ML detected passing!")

# At the end of your session:
hybrid.print_stats()
"""
