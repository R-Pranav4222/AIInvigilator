"""
CV Rule-Based Detection for ML-Only Actions
Fast, reliable alternative to custom ML model - works like leaning/hand_raise

Uses pose keypoints + movement analysis
NO custom model needed - restores FPS to 25+
"""

import cv2
import numpy as np
from collections import deque

class CVRulesMLActions:
    """
    Computer Vision rule-based detector for:
    - Talking (mouth movement detection)
    - Peeking (head angle + eye direction)
    - Cheat Material (object in hand + looking down)
    - Suspicious (rapid/unusual movements)
    """
    
    def __init__(self, frame_buffer_size=10):
        # Movement tracking buffers
        self.head_positions = deque(maxlen=frame_buffer_size)
        self.hand_positions = deque(maxlen=frame_buffer_size)
        self.mouth_openness = deque(maxlen=frame_buffer_size)
        
        # State tracking
        self.frame_count = 0
        
    def detect_talking(self, pose_results):
        """
        Detect talking by analyzing mouth/jaw movement
        Uses nose-to-ear distance changes as proxy for mouth opening
        
        Returns: (detected: bool, confidence: float)
        """
        if not pose_results or len(pose_results) == 0:
            return False, 0.0
        
        try:
            keypoints = pose_results[0].keypoints.xy.cpu().numpy()[0]
            
            # Key facial points
            nose = keypoints[0]  # Nose
            left_ear = keypoints[3]  # Left ear
            right_ear = keypoints[4]  # Right ear
            
            # Check if all points are detected
            if nose[0] == 0 or left_ear[0] == 0 or right_ear[0] == 0:
                return False, 0.0
            
            # Calculate head height (ear to ear distance)
            ear_distance = np.linalg.norm(left_ear - right_ear)
            
            # Calculate vertical distance from nose to ear line
            # When mouth opens, nose moves down relative to ears
            nose_to_ear_vertical = abs(nose[1] - (left_ear[1] + right_ear[1]) / 2)
            
            # Normalized mouth openness metric
            if ear_distance > 0:
                mouth_metric = nose_to_ear_vertical / ear_distance
                self.mouth_openness.append(mouth_metric)
            
            # Detect talking if mouth metric shows variation (opening/closing)
            if len(self.mouth_openness) >= 5:
                recent_mouth = list(self.mouth_openness)[-5:]
                mouth_variation = np.std(recent_mouth)
                mean_openness = np.mean(recent_mouth)
                
                # Talking shows both variation AND openness
                talking_detected = mouth_variation > 0.05 and mean_openness > 0.3
                confidence = min(0.9, mouth_variation * 10 + mean_openness * 0.5)
                
                return talking_detected, confidence
                
        except Exception as e:
            pass
        
        return False, 0.0
    
    def detect_peeking(self, pose_results):
        """
        Detect peeking by analyzing head angle/orientation
        Person turns head sideways to look at neighbor's work
        
        Returns: (detected: bool, confidence: float)
        """
        if not pose_results or len(pose_results) == 0:
            return False, 0.0
        
        try:
            keypoints = pose_results[0].keypoints.xy.cpu().numpy()[0]
            
            # Shoulder points for body orientation
            left_shoulder = keypoints[5]
            right_shoulder = keypoints[6]
            
            # Head points
            nose = keypoints[0]
            left_ear = keypoints[3]
            right_ear = keypoints[4]
            
            # Check detection
            if left_shoulder[0] == 0 or right_shoulder[0] == 0 or nose[0] == 0:
                return False, 0.0
            
            # Body center (between shoulders)
            body_center_x = (left_shoulder[0] + right_shoulder[0]) / 2
            shoulder_width = abs(left_shoulder[0] - right_shoulder[0])
            
            # Head center (nose position)
            head_offset = abs(nose[0] - body_center_x)
            
            # Peeking: head significantly offset from body center
            if shoulder_width > 0:
                head_offset_ratio = head_offset / shoulder_width
                
                # Also check ear visibility (peeking shows one ear much more than other)
                ear_diff = abs(left_ear[0] - right_ear[0])
                ear_asymmetry = ear_diff / shoulder_width if shoulder_width > 0 else 0
                
                # Peeking detected if head offset AND ear asymmetry
                peeking_detected = head_offset_ratio > 0.4 and ear_asymmetry > 0.3
                confidence = min(0.9, head_offset_ratio + ear_asymmetry * 0.5)
                
                return peeking_detected, confidence
                
        except Exception as e:
            pass
        
        return False, 0.0
    
    def detect_cheat_material(self, pose_results, mobile_results):
        """
        Detect cheat material: person holding object + looking down
        Uses mobile detection (any object in hand) + head down posture
        
        Returns: (detected: bool, confidence: float)
        """
        if not pose_results or len(pose_results) == 0:
            return False, 0.0
        
        try:
            keypoints = pose_results[0].keypoints.xy.cpu().numpy()[0]
            
            # Head points
            nose = keypoints[0]
            left_eye = keypoints[1]
            right_eye = keypoints[2]
            
            # Hand/wrist points
            left_wrist = keypoints[9]
            right_wrist = keypoints[10]
            
            # Shoulder reference
            left_shoulder = keypoints[5]
            right_shoulder = keypoints[6]
            
            if nose[0] == 0 or left_shoulder[0] == 0:
                return False, 0.0
            
            # Check if looking down (nose below shoulders)
            shoulder_avg_y = (left_shoulder[1] + right_shoulder[1]) / 2
            looking_down = nose[1] > shoulder_avg_y + 30
            
            # Check if hands are raised (holding something)
            hands_raised = False
            if left_wrist[0] > 0 and left_wrist[1] < shoulder_avg_y:
                hands_raised = True
            if right_wrist[0] > 0 and right_wrist[1] < shoulder_avg_y:
                hands_raised = True
            
            # Check for mobile/object detection
            object_detected = False
            if mobile_results and len(mobile_results) > 0:
                object_detected = len(mobile_results[0].boxes) > 0
            
            # Cheat material: looking down + (hands raised OR object detected)
            cheat_detected = looking_down and (hands_raised or object_detected)
            
            # Confidence based on combination
            confidence = 0.0
            if cheat_detected:
                confidence = 0.5
                if looking_down:
                    confidence += 0.2
                if hands_raised:
                    confidence += 0.15
                if object_detected:
                    confidence += 0.15
            
            return cheat_detected, min(0.9, confidence)
            
        except Exception as e:
            pass
        
        return False, 0.0
    
    def detect_suspicious(self, pose_results):
        """
        Detect suspicious behavior: rapid/erratic movements, unusual posture
        Analyzes movement patterns over time
        
        Returns: (detected: bool, confidence: float)
        """
        if not pose_results or len(pose_results) == 0:
            return False, 0.0
        
        try:
            keypoints = pose_results[0].keypoints.xy.cpu().numpy()[0]
            
            # Track head position
            nose = keypoints[0]
            if nose[0] == 0:
                return False, 0.0
            
            self.head_positions.append(nose.copy())
            
            # Need enough frames to detect movement patterns
            if len(self.head_positions) >= 8:
                positions = np.array(list(self.head_positions)[-8:])
                
                # Calculate movement metrics
                displacements = np.diff(positions, axis=0)
                distances = np.linalg.norm(displacements, axis=1)
                
                # Suspicious patterns:
                # 1. High movement variation (jittery/nervous)
                movement_std = np.std(distances)
                
                # 2. Rapid back-and-forth (checking surroundings)
                direction_changes = 0
                for i in range(1, len(displacements)):
                    if np.dot(displacements[i], displacements[i-1]) < 0:
                        direction_changes += 1
                
                # 3. High average speed
                avg_speed = np.mean(distances)
                
                # Suspicious if multiple indicators present
                suspicious_score = 0
                if movement_std > 5:  # Jittery movement
                    suspicious_score += 0.3
                if direction_changes >= 3:  # Lots of direction changes
                    suspicious_score += 0.3
                if avg_speed > 8:  # Fast movements
                    suspicious_score += 0.2
                
                # Also check for unusual head positions
                head_heights = positions[:, 1]
                height_variation = np.std(head_heights)
                if height_variation > 15:  # Head bobbing
                    suspicious_score += 0.2
                
                suspicious_detected = suspicious_score >= 0.5
                confidence = min(0.9, suspicious_score)
                
                return suspicious_detected, confidence
                
        except Exception as e:
            pass
        
        return False, 0.0
    
    def detect_all(self, pose_results, mobile_results=None):
        """
        Run all detections and return results
        
        Returns:
            dict: {
                'talking': (detected, confidence),
                'peeking': (detected, confidence),
                'cheat_material': (detected, confidence),
                'suspicious': (detected, confidence)
            }
        """
        self.frame_count += 1
        
        return {
            'talking': self.detect_talking(pose_results),
            'peeking': self.detect_peeking(pose_results),
            'cheat_material': self.detect_cheat_material(pose_results, mobile_results),
            'suspicious': self.detect_suspicious(pose_results)
        }
