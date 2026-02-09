"""
Hybrid Detection Module - Combines Computer Vision + ML
This module uses PRE-TRAINED YOLO models to verify and reduce false positives from CV detection
NO DATASET DOWNLOAD NEEDED - Uses COCO pre-trained models!
"""

import torch
import cv2
import numpy as np
from ultralytics import YOLO
from datetime import datetime
import os

class HybridDetector:
    """
    Combines rule-based CV detection with PRE-TRAINED ML verification
    
    Workflow:
    1. CV rules detect potential malpractice (fast)
    2. Pre-trained YOLO model verifies detection (accurate)
    3. Only high-confidence detections are logged
    
    Uses COCO-trained models - NO custom training required!
    """
    
    def __init__(self, 
                 ml_model_path="yolo11n.pt",  # Use pre-trained YOLO
                 pose_model_path="yolov8n-pose.pt",  # Pose detection
                 use_ml_verification=True,
                 ml_confidence_threshold=0.45,  # Lower for pre-trained models
                 device='cuda' if torch.cuda.is_available() else 'cpu'):
        """
        Initialize hybrid detector with PRE-TRAINED YOLO models
        
        Args:
            ml_model_path: Path to YOLO model (default: yolo11n.pt - pre-trained on COCO)
            pose_model_path: Path to pose model (default: yolov8n-pose.pt)
            use_ml_verification: Enable/disable ML verification
            ml_confidence_threshold: Minimum confidence for ML detection
            device: 'cuda' or 'cpu'
        """
        self.use_ml_verification = use_ml_verification
        self.ml_threshold = ml_confidence_threshold
        self.device = device
        
        # Load ML model if verification is enabled
        if self.use_ml_verification:
            print(f"🚀 Loading PRE-TRAINED YOLO models...")
            
            # Try to load object detection model
            try:
                if not os.path.exists(ml_model_path):
                    # Try ML folder
                    ml_model_path = os.path.join('ML', ml_model_path)
                
                self.ml_model = YOLO(ml_model_path)
                self.ml_model.to(device)
                print(f"✅ Object detection model loaded: {ml_model_path}")
            except Exception as e:
                print(f"⚠️  Could not load {ml_model_path}: {e}")
                print("   Trying yolov8n.pt...")
                try:
                    self.ml_model = YOLO('yolov8n.pt')
                    self.ml_model.to(device)
                    print(f"✅ Using yolov8n.pt (pre-trained)")
                except:
                    self.ml_model = None
                    print("❌ No object detection model available")
                    self.use_ml_verification = False
            
            # Try to load pose model
            try:
                if not os.path.exists(pose_model_path):
                    pose_model_path = os.path.join('ML', pose_model_path)
                
                self.pose_model = YOLO(pose_model_path)
                self.pose_model.to(device)
                print(f"✅ Pose detection model loaded: {pose_model_path}")
            except Exception as e:
                print(f"⚠️  Could not load pose model: {e}")
                self.pose_model = None
            
            print(f"🎯 Running on: {device}")
        else:
            self.ml_model = None
            self.pose_model = None
        
        # Detection statistics
        self.stats = {
            'cv_detections': 0,
            'ml_verified': 0,
            'ml_rejected': 0,
            'false_positive_reduction': 0
        }
        
        # COCO class mapping (pre-trained YOLO models)
        # These are standard COCO dataset classes
        self.coco_classes = {
            0: 'person',
            67: 'cell phone',  # Mobile phone detection!
            73: 'book',
            74: 'clock',
            76: 'keyboard',
            63: 'laptop',
            # Add more COCO classes as needed
        }
        
        # Map exam behaviors to COCO classes for verification
        self.behavior_to_coco = {
            'mobile': [67],  # cell phone
            'leaning': [0],  # person (check pose)
            'turning': [0],  # person (check pose)
            'passing': [0, 73],  # person + book/paper
            'hand_raise': [0],  # person (check pose)
        }
    
    def verify_with_ml(self, frame, detection_type, bbox=None):
        """
        Use PRE-TRAINED YOLO model to verify CV detection using COCO classes
        
        Args:
            frame: Video frame
            detection_type: Type of CV detection (e.g., 'mobile', 'leaning')
            bbox: Bounding box [x1, y1, x2, y2] to focus on (optional)
        
        Returns:
            verified (bool): True if ML confirms detection
            confidence (float): ML confidence score
            ml_class (str): ML detected class name
        """
        if not self.use_ml_verification or self.ml_model is None:
            # No ML verification, accept CV detection
            return True, 1.0, detection_type
        
        # Crop frame to bbox if provided (focus on area of interest)
        if bbox is not None:
            x1, y1, x2, y2 = map(int, bbox)
            # Ensure valid coordinates
            h, w = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            if x2 > x1 and y2 > y1:
                roi = frame[y1:y2, x1:x2]
            else:
                roi = frame
        else:
            roi = frame
        
        # Run ML inference
        with torch.no_grad():
            results = self.ml_model(roi, device=self.device, verbose=False)
        
        # Get expected COCO classes for this detection type
        expected_classes = self.behavior_to_coco.get(detection_type, [0])
        
        # Parse results
        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            
            # Get highest confidence detection matching expected class
            if len(boxes) > 0:
                confidences = boxes.conf.cpu().numpy()
                classes = boxes.cls.cpu().numpy().astype(int)
                
                # Find best match for expected classes
                best_confidence = 0.0
                best_class = -1
                
                for i, cls in enumerate(classes):
                    if cls in expected_classes and confidences[i] > best_confidence:
                        best_confidence = confidences[i]
                        best_class = cls
                
                if best_class >= 0:
                    # Map to COCO class name
                    ml_class = self.coco_classes.get(best_class, 'unknown')
                    
                    # Verify if ML confidence is high enough
                    verified = best_confidence >= self.ml_threshold
                    
                    # Update stats
                    if verified:
                        self.stats['ml_verified'] += 1
                    else:
                        self.stats['ml_rejected'] += 1
                    
                    return verified, float(best_confidence), ml_class
        
        # No ML detection of expected class, reject CV detection
        self.stats['ml_rejected'] += 1
        return False, 0.0, 'none'
    
    def detect_mobile_hybrid(self, frame, cv_detected, cv_bbox=None):
        """
        Hybrid mobile phone detection
        
        Args:
            frame: Video frame
            cv_detected: CV detection result (True/False)
            cv_bbox: CV bounding box (optional)
        
        Returns:
            final_detection (bool): Final decision
            confidence (float): Detection confidence
            method (str): Detection method used
        """
        self.stats['cv_detections'] += int(cv_detected)
        
        if not cv_detected:
            return False, 0.0, 'cv'
        
        # CV detected something, verify with ML
        verified, ml_conf, ml_class = self.verify_with_ml(
            frame, 'mobile', cv_bbox
        )
        
        if verified:
            return True, ml_conf, 'hybrid'
        else:
            self.stats['false_positive_reduction'] += 1
            return False, ml_conf, 'ml_rejected'
    
    def detect_leaning_hybrid(self, frame, cv_detected, person_bbox=None):
        """Hybrid leaning detection using pose estimation"""
        self.stats['cv_detections'] += int(cv_detected)
        
        if not cv_detected:
            return False, 0.0, 'cv'
        
        # Use pose model for better leaning detection
        if self.pose_model is not None and person_bbox is not None:
            x1, y1, x2, y2 = map(int, person_bbox)
            h, w = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            if x2 > x1 and y2 > y1:
                roi = frame[y1:y2, x1:x2]
                
                # Run pose detection
                with torch.no_grad():
                    pose_results = self.pose_model(roi, device=self.device, verbose=False)
                
                # Check if pose is detected with good confidence
                if len(pose_results) > 0 and pose_results[0].keypoints is not None:
                    keypoints = pose_results[0].keypoints
                    if len(keypoints) > 0:
                        # Get confidence from pose detection
                        try:
                            if hasattr(keypoints, 'conf') and keypoints.conf is not None:
                                conf = float(keypoints.conf.mean())
                            else:
                                conf = 0.5
                        except:
                            conf = 0.5
                        
                        if conf >= self.ml_threshold:
                            self.stats['ml_verified'] += 1
                            return True, conf, 'hybrid_pose'
        
        # Fallback to standard verification
        verified, ml_conf, ml_class = self.verify_with_ml(
            frame, 'leaning', person_bbox
        )
        
        if verified:
            return True, ml_conf, 'hybrid'
        else:
            self.stats['false_positive_reduction'] += 1
            return False, ml_conf, 'ml_rejected'
    
    def detect_turning_hybrid(self, frame, cv_detected, person_bbox=None):
        """Hybrid turning back detection using pose estimation"""
        self.stats['cv_detections'] += int(cv_detected)
        
        if not cv_detected:
            return False, 0.0, 'cv'
        
        # Use pose model for better orientation detection
        if self.pose_model is not None and person_bbox is not None:
            x1, y1, x2, y2 = map(int, person_bbox)
            h, w = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            if x2 > x1 and y2 > y1:
                roi = frame[y1:y2, x1:x2]
                
                # Run pose detection
                with torch.no_grad():
                    pose_results = self.pose_model(roi, device=self.device, verbose=False)
                
                # Check if pose is detected
                if len(pose_results) > 0 and pose_results[0].keypoints is not None:
                    keypoints = pose_results[0].keypoints
                    if len(keypoints) > 0:
                        try:
                            if hasattr(keypoints, 'conf') and keypoints.conf is not None:
                                conf = float(keypoints.conf.mean())
                            else:
                                conf = 0.5
                        except:
                            conf = 0.5
                        
                        if conf >= self.ml_threshold:
                            self.stats['ml_verified'] += 1
                            return True, conf, 'hybrid_pose'
        
        # Fallback to standard verification
        verified, ml_conf, ml_class = self.verify_with_ml(
            frame, 'turning', person_bbox
        )
        
        if verified:
            return True, ml_conf, 'hybrid'
        else:
            self.stats['false_positive_reduction'] += 1
            return False, ml_conf, 'ml_rejected'
    
    def detect_passing_hybrid(self, frame, cv_detected, bbox=None):
        """Hybrid paper passing detection"""
        self.stats['cv_detections'] += int(cv_detected)
        
        if not cv_detected:
            return False, 0.0, 'cv'
        
        verified, ml_conf, ml_class = self.verify_with_ml(
            frame, 'passing', bbox
        )
        
        # Accept if person or book is detected
        if verified:
            return True, ml_conf, 'hybrid'
        else:
            self.stats['false_positive_reduction'] += 1
            return False, ml_conf, 'ml_rejected'
    
    def get_statistics(self):
        """Get detection statistics"""
        if self.stats['cv_detections'] > 0:
            reduction_rate = (self.stats['false_positive_reduction'] / 
                            self.stats['cv_detections'] * 100)
        else:
            reduction_rate = 0
        
        return {
            **self.stats,
            'false_positive_reduction_rate': f"{reduction_rate:.1f}%"
        }
    
    def reset_statistics(self):
        """Reset statistics"""
        for key in self.stats:
            self.stats[key] = 0


# Example usage
if __name__ == "__main__":
    print("="*70)
    print("HYBRID DETECTOR TEST - Using Pre-trained YOLO Models")
    print("="*70)
    
    # Initialize hybrid detector with PRE-TRAINED models
    detector = HybridDetector(
        ml_model_path="yolo11n.pt",  # Pre-trained YOLO11
        pose_model_path="yolov8n-pose.pt",  # Pre-trained pose
        use_ml_verification=True,  # Set to False to use CV-only
        ml_confidence_threshold=0.45  # Lower for pre-trained models
    )
    
    print("\n" + "="*70)
    print("✅ HYBRID DETECTOR READY - Using Pre-trained YOLO Models")
    print("📊 COCO Classes: person, cell phone, book, laptop, etc.")
    print("🎯 No dataset download needed!")
    print("="*70)
    
    # Simulate detection
    print("\n📹 Testing hybrid detection...")
    
    # Load test image/video
    cap = cv2.VideoCapture(0)  # Use camera
    
    print("\nPress 'q' to quit\n")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Simulate CV detection (replace with your actual CV code)
        cv_mobile_detected = False  # Your CV logic here
        cv_bbox = [100, 100, 300, 300]  # Your CV bbox here
        
        # Hybrid detection
        final_detection, confidence, method = detector.detect_mobile_hybrid(
            frame, cv_mobile_detected, cv_bbox
        )
        
        # Display results
        if final_detection:
            cv2.putText(frame, f"Mobile Detected! ({method}, {confidence:.2f})",
                       (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Show statistics
        stats = detector.get_statistics()
        stats_text = f"CV: {stats['cv_detections']} | Verified: {stats['ml_verified']} | Rejected: {stats['ml_rejected']}"
        cv2.putText(frame, stats_text, (50, frame.shape[0] - 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        cv2.imshow("Hybrid Detection Test", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    # Final statistics
    print("\n" + "="*70)
    print("DETECTION STATISTICS")
    print("="*70)
    stats = detector.get_statistics()
    for key, value in stats.items():
        print(f"{key}: {value}")
    print("="*70)
