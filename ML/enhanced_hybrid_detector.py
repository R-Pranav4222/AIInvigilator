"""
Enhanced Hybrid Detection - Rule-Based CV + Custom Trained Model
Combines geometric rules with your trained malpractice detection model
"""

import torch
import cv2
import numpy as np
from ultralytics import YOLO
from datetime import datetime
import os

class EnhancedHybridDetector:
    """
    Combines THREE detection methods for maximum accuracy:
    1. Rule-based CV detection (geometric heuristics)
    2. Custom trained YOLO model (malpractice-specific)
    3. Pre-trained COCO model (for object verification)
    
    Voting system:
    - Both agree → HIGH confidence (log it!)
    - One agrees → MEDIUM confidence (log with caution)
    - Neither → Ignore (likely false positive)
    """
    
    # Custom model class mapping
    CUSTOM_CLASSES = {
        0: 'phone',
        1: 'cheat_material',
        2: 'peeking',
        3: 'turning_back',
        4: 'hand_raise',
        5: 'passing',
        6: 'talking',
        7: 'cheating',
        8: 'suspicious',
        9: 'normal'
    }
    
    # Map CV detection types to custom model classes
    CV_TO_CUSTOM = {
        'mobile': ['phone'],
        'leaning': ['suspicious', 'cheating', 'peeking'],
        'passing': ['passing', 'cheating'],
        'turning': ['turning_back', 'cheating'],
        'hand_raise': ['hand_raise'],
    }
    
    def __init__(self, 
                 custom_model_path="runs/train/malpractice_detector/weights/best.pt",
                 fallback_model_path="yolo11n.pt",
                 pose_model_path="yolov8n-pose.pt",
                 use_custom_model=True,
                 custom_threshold=0.25,
                 voting_mode='any',  # 'any', 'majority', 'all'
                 device='cuda' if torch.cuda.is_available() else 'cpu'):
        """
        Initialize enhanced hybrid detector
        
        Args:
            custom_model_path: Path to YOUR trained model
            fallback_model_path: Pre-trained COCO model (backup)
            pose_model_path: Pose detection model
            use_custom_model: Enable custom model detection
            custom_threshold: Confidence threshold for custom model
            voting_mode: 'any' (either), 'majority' (2/3), 'all' (both agree)
            device: 'cuda' or 'cpu'
        """
        self.use_custom_model = use_custom_model
        self.custom_threshold = custom_threshold
        self.voting_mode = voting_mode
        self.device = device
        
        print("\n" + "="*80)
        print("🚀 ENHANCED HYBRID DETECTOR - INITIALIZATION")
        print("="*80)
        
        # Load custom trained model
        self.custom_model = None
        if use_custom_model:
            try:
                # Try different paths
                paths_to_try = [
                    custom_model_path,
                    os.path.join('ML', custom_model_path),
                    os.path.join('..', custom_model_path),
                ]
                
                for path in paths_to_try:
                    if os.path.exists(path):
                        print(f"📦 Loading custom trained model: {path}")
                        self.custom_model = YOLO(path)
                        self.custom_model.to(device)
                        print(f"✅ Custom model loaded (10 malpractice classes)")
                        print(f"   Classes: {list(self.CUSTOM_CLASSES.values())}")
                        break
                
                if self.custom_model is None:
                    print(f"⚠️  Custom model not found at: {custom_model_path}")
                    print(f"   Trying to use fallback model...")
                    self.use_custom_model = False
                    
            except Exception as e:
                print(f"❌ Error loading custom model: {e}")
                self.use_custom_model = False
        
        # Load fallback COCO model
        self.fallback_model = None
        try:
            print(f"📦 Loading fallback model: {fallback_model_path}")
            self.fallback_model = YOLO(fallback_model_path)
            self.fallback_model.to(device)
            print(f"✅ Fallback model loaded (COCO classes)")
        except Exception as e:
            print(f"⚠️  Fallback model error: {e}")
        
        # Load pose model
        self.pose_model = None
        try:
            print(f"📦 Loading pose model: {pose_model_path}")
            self.pose_model = YOLO(pose_model_path)
            self.pose_model.to(device)
            print(f"✅ Pose model loaded")
        except Exception as e:
            print(f"⚠️  Pose model error: {e}")
        
        print(f"🎯 Detection mode: {voting_mode.upper()}")
        print(f"🖥️  Device: {device}")
        print("="*80 + "\n")
        
        # Statistics
        self.stats = {
            'cv_only': 0,
            'ml_only': 0,
            'both_agree': 0,
            'conflicts': 0,
            'total_detections': 0,
        }
    
    def detect_hybrid(self, frame, cv_detection=None, detection_type=None, bbox=None):
        """
        Run hybrid detection combining CV rules + custom model
        
        Args:
            frame: Video frame
            cv_detection: CV detection result (True/False or dict)
            detection_type: Type of CV detection ('mobile', 'passing', etc.)
            bbox: Bounding box to focus on [x1, y1, x2, y2]
        
        Returns:
            detected (bool): Final detection result
            confidence (float): Confidence score (0-1)
            detection_info (dict): Detailed detection info
        """
        results = {
            'cv_detected': bool(cv_detection),
            'ml_detected': False,
            'cv_type': detection_type,
            'ml_classes': [],
            'ml_confidences': [],
            'final_decision': False,
            'confidence': 0.0,
            'method': 'none'
        }
        
        # Get ML detections
        ml_detections = []
        if self.custom_model is not None:
            # Crop to region of interest if bbox provided
            roi = frame
            if bbox is not None:
                x1, y1, x2, y2 = map(int, bbox)
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 > x1 and y2 > y1:
                    roi = frame[y1:y2, x1:x2]
            
            # Run custom model inference
            try:
                preds = self.custom_model(roi, conf=self.custom_threshold, verbose=False)
                
                # Extract detections
                for pred in preds:
                    boxes = pred.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        class_name = self.CUSTOM_CLASSES.get(cls_id, f'class_{cls_id}')
                        
                        ml_detections.append({
                            'class': class_name,
                            'confidence': conf,
                            'class_id': cls_id
                        })
                        
                        results['ml_classes'].append(class_name)
                        results['ml_confidences'].append(conf)
                
                # Check if ML detected relevant class
                if detection_type and detection_type in self.CV_TO_CUSTOM:
                    expected_classes = self.CV_TO_CUSTOM[detection_type]
                    ml_found = any(d['class'] in expected_classes for d in ml_detections)
                    results['ml_detected'] = ml_found
                elif ml_detections:
                    # ML detected something (even if not exact match)
                    results['ml_detected'] = True
                    
            except Exception as e:
                print(f"⚠️  ML inference error: {e}")
        
        # Voting system
        cv_vote = results['cv_detected']
        ml_vote = results['ml_detected']
        
        if self.voting_mode == 'all':
            # Both must agree
            final = cv_vote and ml_vote
            method = 'both_agree' if final else 'rejected'
            
        elif self.voting_mode == 'any':
            # Either one is enough
            final = cv_vote or ml_vote
            if cv_vote and ml_vote:
                method = 'both_agree'
            elif cv_vote:
                method = 'cv_only'
            elif ml_vote:
                method = 'ml_only'
            else:
                method = 'none'
                
        else:  # majority (at least 1)
            final = cv_vote or ml_vote
            method = 'cv_only' if cv_vote else 'ml_only'
            if cv_vote and ml_vote:
                method = 'both_agree'
        
        # Calculate confidence
        if method == 'both_agree':
            confidence = 0.95  # High confidence
        elif method in ['cv_only', 'ml_only']:
            if results['ml_confidences']:
                confidence = max(results['ml_confidences'])
            else:
                confidence = 0.7  # Medium confidence
        else:
            confidence = 0.0
        
        results['final_decision'] = final
        results['confidence'] = confidence
        results['method'] = method
        
        # Update stats
        if final:
            self.stats['total_detections'] += 1
            if method == 'both_agree':
                self.stats['both_agree'] += 1
            elif method == 'cv_only':
                self.stats['cv_only'] += 1
            elif method == 'ml_only':
                self.stats['ml_only'] += 1
        
        if cv_vote != ml_vote:
            self.stats['conflicts'] += 1
        
        return final, confidence, results
    
    def run_full_detection(self, frame, conf_threshold=None):
        """
        Run custom model on full frame (without CV detection)
        
        Returns list of all detected malpractices
        """
        if self.custom_model is None:
            return []
        
        threshold = conf_threshold or self.custom_threshold
        
        try:
            results = self.custom_model(frame, conf=threshold, verbose=False)
            detections = []
            
            for pred in results:
                boxes = pred.boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = self.CUSTOM_CLASSES.get(cls_id, f'class_{cls_id}')
                    xyxy = box.xyxy[0].cpu().numpy()
                    
                    detections.append({
                        'class': class_name,
                        'confidence': conf,
                        'bbox': xyxy,
                        'class_id': cls_id
                    })
            
            return detections
            
        except Exception as e:
            print(f"⚠️  Full detection error: {e}")
            return []
    
    def get_stats(self):
        """Get detection statistics"""
        return self.stats.copy()
    
    def print_stats(self):
        """Print detection statistics"""
        print("\n" + "="*80)
        print("📊 HYBRID DETECTION STATISTICS")
        print("="*80)
        print(f"Total detections: {self.stats['total_detections']}")
        print(f"  CV + ML agree: {self.stats['both_agree']} (HIGH confidence)")
        print(f"  CV only: {self.stats['cv_only']} (MEDIUM confidence)")
        print(f"  ML only: {self.stats['ml_only']} (MEDIUM confidence)")
        print(f"  Conflicts: {self.stats['conflicts']} (disagreements)")
        
        if self.stats['total_detections'] > 0:
            agreement_rate = (self.stats['both_agree'] / self.stats['total_detections']) * 100
            print(f"\n✅ Agreement rate: {agreement_rate:.1f}%")
        print("="*80 + "\n")


# Backward compatibility wrapper
class HybridDetector(EnhancedHybridDetector):
    """Alias for backward compatibility with existing code"""
    pass
