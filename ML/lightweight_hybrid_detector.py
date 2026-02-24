"""
Lightweight Hybrid Detector - Reuses Already-Loaded Models
NO duplicate model loading - maximum performance!
"""

import torch
import cv2
import numpy as np
from ultralytics import YOLO
import os

class LightweightHybridDetector:
    """
    Optimized hybrid detector that REUSES models already loaded by front.py
    Adds ONLY the custom trained model, nothing else
    
    Performance: Maintains original FPS (23-26) with hybrid detection benefits
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
        'mobile': ['phone', 'cheating'],
        'leaning': ['suspicious', 'cheating', 'peeking'],
        'passing': ['passing', 'cheating'],
        'turning': ['turning_back', 'cheating'],
        'hand_raise': ['hand_raise'],
    }
    
    def __init__(self, 
                 custom_model_path="runs/train/malpractice_detector/weights/best.pt",
                 use_custom_model=True,
                 custom_threshold=0.25,
                 voting_mode='any',
                 device='cuda' if torch.cuda.is_available() else 'cpu'):
        """
        Initialize LIGHTWEIGHT hybrid detector
        
        Args:
            custom_model_path: Path to YOUR trained model
            use_custom_model: Enable custom model
            custom_threshold: Confidence threshold
            voting_mode: 'any', 'majority', 'all'
            device: 'cuda' or 'cpu'
        """
        self.use_custom_model = use_custom_model
        self.custom_threshold = custom_threshold
        self.voting_mode = voting_mode
        self.device = device
        
        print("\n" + "="*60)
        print("🚀 LIGHTWEIGHT HYBRID DETECTOR")
        print("="*60)
        
        # Load ONLY the custom model (front.py already has pose + mobile models)
        self.custom_model = None
        if use_custom_model:
            try:
                # Get the directory where this script is located
                script_dir = os.path.dirname(os.path.abspath(__file__))
                
                paths_to_try = [
                    custom_model_path,  # Direct path
                    os.path.join(script_dir, custom_model_path),  # Relative to this script
                    os.path.join(script_dir, '..', custom_model_path),  # One level up
                    os.path.join(script_dir, '..', 'ML', custom_model_path),  # ML directory
                ]
                
                print(f"🔍 Searching for model: {custom_model_path}")
                print(f"   Script directory: {script_dir}")
                print(f"   Trying {len(paths_to_try)} paths...")
                
                found = False
                for i, path in enumerate(paths_to_try, 1):
                    abs_path = os.path.abspath(path)
                    exists = os.path.exists(path)
                    print(f"   [{i}] {abs_path[:80]}... {'✓' if exists else '✗'}")
                    if exists:
                        found = True
                        print(f"📦 Loading custom model: {path}")
                        print(f"🔧 Device parameter: '{device}' (type: {type(device).__name__})")
                        self.custom_model = YOLO(path)
                        self.custom_model.to(device)
                        
                        # Optimize for GPU if available
                        if 'cuda' in str(device):
                            try:
                                from gpu_config import gpu_config
                                self.custom_model = gpu_config.optimize_model(self.custom_model)
                                half = gpu_config.half_precision
                                if half:
                                    print(f"✅ Custom model optimized (FP16) on {device}")
                                else:
                                    print(f"✅ Custom model optimized (FP32) on {device}")
                            except Exception as e:
                                print(f"⚠️ GPU optimization failed: {e}")
                                print(f"✅ Custom model loaded on {device}")
                        else:
                            print(f"⚠️ CUDA not detected in device string: '{device}'")
                            print("✅ Custom model loaded on CPU")
                        
                        print(f"   Classes: phone, passing, cheating, etc.")
                        break
                
                if self.custom_model is None:
                    print(f"⚠️  Custom model not found, using CV-only")
                    self.use_custom_model = False
                    
            except Exception as e:
                print(f"❌ Error loading custom model: {e}")
                self.use_custom_model = False
        else:
            print("⚠️  Custom model disabled")
        
        print(f"🎯 Voting mode: {voting_mode.upper()}")
        print(f"🖥️  Device: {device}")
        print("="*60 + "\n")
        
        # Statistics (both new and old format for backward compatibility)
        self.stats = {
            # New format
            'cv_only': 0,
            'ml_only': 0,
            'both_agree': 0,
            'total': 0,
            'conflicts': 0,
            # Old format (backward compatible)
            'cv_detections': 0,
            'ml_verified': 0,
            'ml_rejected': 0,
            'false_positive_reduction': 0,
        }
    
    def verify_detection(self, frame, detection_type, cv_detected, bbox=None):
        """
        Quick verification using custom model ONLY
        
        Args:
            frame: Video frame
            detection_type: 'mobile', 'passing', 'leaning', 'turning', 'hand_raise'
            cv_detected: CV detection result (True/False)
            bbox: Optional bbox [x1, y1, x2, y2]
        
        Returns:
            (detected, confidence, method)
        """
        # If custom model not available, just use CV result
        if not self.use_custom_model or self.custom_model is None:
            return cv_detected, 0.7 if cv_detected else 0.0, 'cv_only'
        
        # Get region of interest
        roi = frame
        if bbox is not None:
            x1, y1, x2, y2 = map(int, bbox)
            h, w = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 > x1 and y2 > y1:
                roi = frame[y1:y2, x1:x2]
        
        # Run custom model (fast inference)
        ml_detected = False
        max_confidence = 0.0
        
        try:
            results = self.custom_model(roi, conf=self.custom_threshold, verbose=False, imgsz=640)
            
            # Check if relevant class detected
            expected_classes = self.CV_TO_CUSTOM.get(detection_type, [])
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = self.CUSTOM_CLASSES.get(cls_id, '')
                    
                    if class_name in expected_classes:
                        ml_detected = True
                        max_confidence = max(max_confidence, conf)
        
        except Exception as e:
            # Silently fail, use CV result
            pass
        
        # Voting
        if self.voting_mode == 'all':
            final = cv_detected and ml_detected
            method = 'both_agree' if final else 'rejected'
            conf = 0.95 if final else 0.0
            
        elif self.voting_mode == 'any':
            final = cv_detected or ml_detected
            if cv_detected and ml_detected:
                method = 'both_agree'
                conf = 0.95
            elif cv_detected:
                method = 'cv_only'
                conf = 0.7
            elif ml_detected:
                method = 'ml_only'
                conf = max_confidence
            else:
                method = 'none'
                conf = 0.0
        else:  # majority
            final = cv_detected or ml_detected
            method = 'both_agree' if (cv_detected and ml_detected) else ('cv_only' if cv_detected else 'ml_only')
            conf = 0.95 if method == 'both_agree' else (0.7 if cv_detected else max_confidence)
        
        # Update stats (both new and old format for backward compatibility)
        if final:
            self.stats['total'] += 1
            if method == 'both_agree':
                self.stats['both_agree'] += 1
            elif method == 'cv_only':
                self.stats['cv_only'] += 1
            elif method == 'ml_only':
                self.stats['ml_only'] += 1
        
        # Update old-format stats for front.py compatibility
        if cv_detected:
            self.stats['cv_detections'] += 1
            if ml_detected:
                self.stats['ml_verified'] += 1
            else:
                self.stats['ml_rejected'] += 1
                self.stats['false_positive_reduction'] += 1
        
        return final, conf, method
    
    def get_stats(self):
        """Get statistics"""
        return self.stats.copy()
    
    def get_statistics(self):
        """Get statistics (backward compatible alias with computed rate)"""
        stats = self.stats.copy()
        # Calculate false positive reduction rate as percentage string
        cv_detections = stats.get('cv_detections', 0)
        ml_rejected = stats.get('ml_rejected', 0)
        if cv_detections > 0:
            rate = int((ml_rejected / cv_detections) * 100)
            stats['false_positive_reduction_rate'] = f"{rate}%"
        else:
            stats['false_positive_reduction_rate'] = "0%"
        return stats
    
    def detect_ml_only_classes(self, frame, ml_only_threshold=None):
        """
        Detect ML-only classes that don't have CV rules
        
        Dataset has varying quality:
        - talking: ~22k examples (excellent)
        - peeking: ~9.5k examples (good)
        - cheat_material: ~2.7k examples (low - use 'cheating' as proxy)
        - suspicious: 0 examples (no data - use 'cheating' as proxy)
        
        Args:
            frame: Video frame
            ml_only_threshold: Optional separate threshold for ML-only detections
            
        Returns:
            dict: {
                'cheat_material': (detected, confidence, bbox),
                'peeking': (detected, confidence, bbox),
                'talking': (detected, confidence, bbox),
                'suspicious': (detected, confidence, bbox)
            }
        """
        ml_only_classes = ['cheat_material', 'peeking', 'talking', 'suspicious']
        detections = {cls: (False, 0.0, None) for cls in ml_only_classes}
        
        if not self.use_custom_model or self.custom_model is None:
            return detections
        
        # Use lower threshold for ML-only if provided
        threshold = ml_only_threshold if ml_only_threshold is not None else self.custom_threshold
        
        try:
            # Run inference on full frame with ML-only threshold
            results = self.custom_model(frame, conf=threshold, verbose=False, imgsz=640)
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = self.CUSTOM_CLASSES.get(cls_id, '')
                    
                    # Direct detection for well-trained classes
                    if class_name in ml_only_classes:
                        # Get bbox
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        bbox = [int(x1), int(y1), int(x2), int(y2)]
                        
                        # Keep highest confidence detection for each class
                        current_conf = detections[class_name][1]
                        if conf > current_conf:
                            detections[class_name] = (True, conf, bbox)
                    
                    # Proxy detection: Use 'cheating' (30k examples) as proxy for poorly-trained classes
                    elif class_name == 'cheating':
                        # Map 'cheating' to cheat_material and suspicious since they lack training data
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        bbox = [int(x1), int(y1), int(x2), int(y2)]
                       
                        # Use as proxy for cheat_material if not already detected
                        if not detections['cheat_material'][0] and conf > threshold * 1.3:
                            detections['cheat_material'] = (True, conf, bbox)
                        
                        # Use as proxy for suspicious if not already detected  
                        if not detections['suspicious'][0] and conf > threshold * 1.3:
                            detections['suspicious'] = (True, conf, bbox)
                    
                    # Proxy detection: Use 'cheating' (30k examples) as proxy for poorly-trained classes
                    elif class_name == 'cheating':
                        # Map 'cheating' to cheat_material and suspicious since they lack training data
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        bbox = [int(x1), int(y1), int(x2), int(y2)]
                        
                        # Use as proxy for cheat_material if not already detected
                        if not detections['cheat_material'][0]:
                            # Lower threshold since it's a proxy
                            if conf > threshold * 1.2:  # Require 20% higher confidence for proxy
                                detections['cheat_material'] = (True, conf, bbox)
                        
                        # Use as proxy for suspicious if not already detected  
                        if not detections['suspicious'][0]:
                            if conf > threshold * 1.2:
                                detections['suspicious'] = (True, conf, bbox)
        
        except Exception as e:
            pass
        
        return detections


# Alias for compatibility
class HybridDetector(LightweightHybridDetector):
    """Backward compatible alias"""
    
    def __init__(self, ml_model_path=None, pose_model_path=None, 
                 use_ml_verification=True, ml_confidence_threshold=0.25,
                 device='cuda' if torch.cuda.is_available() else 'cpu'):
        """
        Backward compatible constructor
        Ignores ml_model_path and pose_model_path (already loaded by front.py)
        """
        # Determine custom model path
        custom_path = "runs/train/malpractice_detector/weights/best.pt"
        
        super().__init__(
            custom_model_path=custom_path,
            use_custom_model=use_ml_verification,
            custom_threshold=ml_confidence_threshold,
            voting_mode='any',
            device=device
        )
    
    def verify_with_ml(self, frame, detection_type, bbox=None):
        """
        Backward compatible method
        
        Returns:
            (verified, confidence, class_name)
        """
        # Map old detection_type names
        type_map = {
            'mobile': 'mobile',
            'leaning': 'leaning',
            'passing': 'passing',
            'turning': 'turning',
            'hand_raise': 'hand_raise',
        }
        
        mapped_type = type_map.get(detection_type, detection_type)
        
        # Assume CV detected it (backward compat)
        detected, conf, method = self.verify_detection(
            frame=frame,
            detection_type=mapped_type,
            cv_detected=True,
            bbox=bbox
        )
        
        return detected, conf, detection_type
    
    def detect_leaning_hybrid(self, frame, cv_detected=True, person_bbox=None):
        """Verify leaning detection with ML (backward compatible)"""
        return self.verify_detection(frame, 'leaning', cv_detected, person_bbox)
    
    def detect_turning_hybrid(self, frame, cv_detected=True, person_bbox=None):
        """Verify turning detection with ML (backward compatible)"""
        return self.verify_detection(frame, 'turning', cv_detected, person_bbox)
    
    def detect_passing_hybrid(self, frame, cv_detected=True, bbox=None):
        """Verify passing detection with ML (backward compatible)"""
        return self.verify_detection(frame, 'passing', cv_detected, bbox)
    
    def detect_mobile_hybrid(self, frame, cv_detected=True, bbox=None):
        """Verify mobile detection with ML (backward compatible)"""
        return self.verify_detection(frame, 'mobile', cv_detected, bbox)
