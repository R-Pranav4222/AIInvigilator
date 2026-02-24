"""
MediaPipe-based ML Action Detector
Uses Google's MediaPipe for accurate face, hand, and pose detection
Much more accurate than geometry-based calculations
"""

import cv2
import mediapipe as mp
import numpy as np
from collections import deque

class MediaPipeMLDetector:
    def __init__(self):
        """Initialize MediaPipe solutions for face, hands, and pose detection"""
        
        # MediaPipe Face Mesh - 468 facial landmarks
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,  # Include iris landmarks
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # MediaPipe Hands - 21 landmarks per hand
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # MediaPipe Pose - 33 landmarks
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Tracking buffers for temporal analysis
        self.lip_distances = deque(maxlen=10)  # Talking detection
        self.face_angles = deque(maxlen=10)    # Peeking detection
        self.head_positions = deque(maxlen=15) # Suspicious movement
        self.hand_positions = deque(maxlen=8)  # Cheat material
        
        print("✅ MediaPipe Detector initialized!")
        print("   - Face Mesh: 468 landmarks")
        print("   - Hand Tracking: 21 landmarks/hand")
        print("   - Pose: 33 landmarks")
    
    def detect_talking(self, frame):
        """
        Detect talking by measuring lip distance changes
        Uses upper lip (13) and lower lip (14) landmarks from face mesh
        
        Returns: (detected: bool, confidence: float)
        """
        try:
            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)
            
            if results.multi_face_landmarks:
                face_landmarks = results.multi_face_landmarks[0]
                h, w = frame.shape[:2]
                
                # Key lip landmarks (MediaPipe face mesh indices)
                # 13: Upper lip top center
                # 14: Lower lip bottom center  
                # 61, 291: Mouth corners
                # 0: Mouth center
                # 17: Lower lip inner
                
                upper_lip = face_landmarks.landmark[13]
                lower_lip = face_landmarks.landmark[14]
                
                # Calculate vertical lip distance in pixels
                upper_y = upper_lip.y * h
                lower_y = lower_lip.y * h
                lip_distance = abs(lower_y - upper_y)
                
                self.lip_distances.append(lip_distance)
                
                # Detect talking if lip distance varies (opening/closing)
                if len(self.lip_distances) >= 5:
                    recent_distances = list(self.lip_distances)[-5:]
                    
                    # Calculate variation (talking shows high variation)
                    std_dev = np.std(recent_distances)
                    mean_distance = np.mean(recent_distances)
                    max_distance = max(recent_distances)
                    
                    # Talking detection criteria:
                    # 1. High variation (mouth opening/closing)
                    # 2. Reasonable mouth opening size
                    talking_detected = std_dev > 2.0 and max_distance > 10
                    
                    # Confidence based on movement intensity
                    confidence = min(0.95, (std_dev / 10.0) + (max_distance / 50.0))
                    
                    return talking_detected, confidence
                    
        except Exception as e:
            pass
        
        return False, 0.0
    
    def detect_peeking(self, frame):
        """
        Detect peeking/looking sideways by analyzing face orientation
        Uses nose tip and face contour to calculate head rotation
        
        Returns: (detected: bool, confidence: float)
        """
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)
            
            if results.multi_face_landmarks:
                face_landmarks = results.multi_face_landmarks[0]
                h, w = frame.shape[:2]
                
                # Key landmarks for face orientation
                # 1: Nose tip
                # 33: Left eye outer corner
                # 263: Right eye outer corner
                # 454: Left cheek
                # 234: Right cheek
                
                nose = face_landmarks.landmark[1]
                left_eye = face_landmarks.landmark[33]
                right_eye = face_landmarks.landmark[263]
                left_cheek = face_landmarks.landmark[454]
                right_cheek = face_landmarks.landmark[234]
                
                # Calculate face center (between eyes)
                face_center_x = (left_eye.x + right_eye.x) / 2
                
                # Calculate horizontal offset of nose from face center
                nose_offset = abs(nose.x - face_center_x)
                
                # Calculate asymmetry between cheeks (indicates turned head)
                left_cheek_x = left_cheek.x
                right_cheek_x = right_cheek.x
                cheek_asymmetry = abs(left_cheek_x - right_cheek_x)
                
                # Peeking detected if:
                # 1. Nose significantly offset from center
                # 2. High cheek asymmetry (one cheek more visible)
                peeking_score = nose_offset * 10 + cheek_asymmetry * 5
                
                peeking_detected = peeking_score > 0.3
                confidence = min(0.95, peeking_score * 2)
                
                return peeking_detected, confidence
                
        except Exception as e:
            pass
        
        return False, 0.0
    
    def detect_cheat_material(self, frame, mobile_detected=False):
        """
        Detect cheat material by analyzing:
        1. Hand positions near face/desk
        2. Looking down posture
        3. Object in hands (mobile detection input)
        
        Returns: (detected: bool, confidence: float)
        """
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Check hands
            hand_results = self.hands.process(rgb_frame)
            # Check pose for head angle
            pose_results = self.pose.process(rgb_frame)
            
            cheat_score = 0.0
            
            # Factor 1: Hands detected (holding something?)
            if hand_results.multi_hand_landmarks:
                num_hands = len(hand_results.multi_hand_landmarks)
                cheat_score += 0.2 * num_hands
                
                # Check if hands are raised (near face/chest area)
                for hand_landmarks in hand_results.multi_hand_landmarks:
                    wrist = hand_landmarks.landmark[0]  # Wrist landmark
                    # If wrist is in upper half of frame (raised)
                    if wrist.y < 0.6:
                        cheat_score += 0.2
            
            # Factor 2: Mobile phone detected
            if mobile_detected:
                cheat_score += 0.3
            
            # Factor 3: Looking down (head tilted forward)
            if pose_results.pose_landmarks:
                nose = pose_results.pose_landmarks.landmark[0]  # Nose
                left_shoulder = pose_results.pose_landmarks.landmark[11]
                right_shoulder = pose_results.pose_landmarks.landmark[12]
                
                shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
                
                # If nose is below shoulders = looking down
                if nose.y > shoulder_y:
                    cheat_score += 0.3
            
            cheat_detected = cheat_score >= 0.4
            confidence = min(0.95, cheat_score)
            
            return cheat_detected, confidence
            
        except Exception as e:
            pass
        
        return False, 0.0
    
    def detect_suspicious(self, frame):
        """
        Detect suspicious behavior by analyzing:
        1. Rapid eye movements (using iris landmarks)
        2. Frequent head turning
        3. Erratic movement patterns
        
        Returns: (detected: bool, confidence: float)
        """
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)
            
            if results.multi_face_landmarks:
                face_landmarks = results.multi_face_landmarks[0]
                h, w = frame.shape[:2]
                
                # Track nose position as head movement proxy
                nose = face_landmarks.landmark[1]
                nose_pos = np.array([nose.x * w, nose.y * h])
                
                self.head_positions.append(nose_pos.copy())
                
                # Need enough frames for pattern analysis
                if len(self.head_positions) >= 10:
                    positions = np.array(list(self.head_positions)[-10:])
                    
                    # Calculate movement metrics
                    displacements = np.diff(positions, axis=0)
                    distances = np.linalg.norm(displacements, axis=1)
                    
                    # Suspicious indicators:
                    # 1. High variation in movement speed
                    speed_std = np.std(distances)
                    
                    # 2. Frequent direction changes
                    direction_changes = 0
                    for i in range(1, len(displacements)-1):
                        # Check if direction reverses
                        dot_product = np.dot(displacements[i], displacements[i-1])
                        if dot_product < 0:
                            direction_changes += 1
                    
                    # 3. High average speed (nervous/checking around)
                    avg_speed = np.mean(distances)
                    
                    # Calculate suspicion score
                    suspicious_score = 0.0
                    
                    if speed_std > 3:  # Erratic speed changes
                        suspicious_score += 0.3
                    if direction_changes >= 4:  # Lots of back-and-forth
                        suspicious_score += 0.4
                    if avg_speed > 5:  # Fast movements
                        suspicious_score += 0.3
                    
                    suspicious_detected = suspicious_score >= 0.5
                    confidence = min(0.95, suspicious_score)
                    
                    return suspicious_detected, confidence
                    
        except Exception as e:
            pass
        
        return False, 0.0
    
    def detect_all(self, frame, mobile_detected=False):
        """
        Run all MediaPipe-based detections
        
        Args:
            frame: BGR image from camera
            mobile_detected: Whether mobile phone was detected by YOLO
        
        Returns:
            dict: {
                'talking': (detected, confidence),
                'peeking': (detected, confidence),
                'cheat_material': (detected, confidence),
                'suspicious': (detected, confidence)
            }
        """
        return {
            'talking': self.detect_talking(frame),
            'peeking': self.detect_peeking(frame),
            'cheat_material': self.detect_cheat_material(frame, mobile_detected),
            'suspicious': self.detect_suspicious(frame)
        }
    
    def __del__(self):
        """Cleanup MediaPipe resources"""
        if hasattr(self, 'face_mesh'):
            self.face_mesh.close()
        if hasattr(self, 'hands'):
            self.hands.close()
        if hasattr(self, 'pose'):
            self.pose.close()
