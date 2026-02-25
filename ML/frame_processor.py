# frame_processor.py — Single-frame ML processing for live WebSocket camera streams
"""
Processes individual JPEG frames from teacher webcams.
Runs YOLO pose + object detection, returns annotated frame + detection list.
Maintains per-stream state for consecutive frame thresholds.
"""

import os
import sys
import cv2
import numpy as np
import logging
import time
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# ========================
# GLOBAL MODEL CACHE (shared across all FrameProcessor instances)
# Models are loaded once, used by all concurrent streams
# ========================
_model_lock = threading.Lock()
_pose_model = None
_mobile_model = None
_models_loaded = False


def _load_models():
    """Load YOLO models once (thread-safe singleton)"""
    global _pose_model, _mobile_model, _models_loaded

    if _models_loaded:
        return

    with _model_lock:
        if _models_loaded:
            return

        try:
            from ultralytics import YOLO

            # Get model paths from config
            base_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                import model_config
                paths = model_config.get_model_paths()
                pose_path = paths["pose_detection"]
                mobile_path = paths["object_detection"]
                logger.info(f"Loaded model config: {paths.get('description', 'Unknown')}")
            except ImportError:
                pose_path = os.path.join(base_dir, "yolov8n-pose.pt")
                mobile_path = os.path.join(base_dir, "yolo11n.pt")
                logger.info("Using default model paths")

            _pose_model = YOLO(pose_path)
            _mobile_model = YOLO(mobile_path)
            _models_loaded = True
            logger.info("ML models loaded successfully for frame processing")

        except Exception as e:
            logger.error(f"Failed to load ML models: {e}")
            raise


# ========================
# DETECTION HELPER FUNCTIONS
# ========================

def is_leaning(keypoints):
    """Detect leaning by comparing head & shoulder centers"""
    if keypoints is None or len(keypoints) < 7:
        return False

    nose, l_eye, r_eye, l_ear, r_ear, l_shoulder, r_shoulder = keypoints[:7]
    if any(pt is None for pt in [nose, l_eye, r_eye, l_ear, r_ear, l_shoulder, r_shoulder]):
        return False

    eye_dist = abs(l_eye[0] - r_eye[0])
    shoulder_dist = abs(l_shoulder[0] - r_shoulder[0])

    if shoulder_dist > 0:
        eye_ratio = eye_dist / shoulder_dist
        if eye_ratio < 0.17:
            return False  # Turning back, not leaning

    shoulder_height_diff = abs(l_shoulder[1] - r_shoulder[1])
    head_center_x = (l_eye[0] + r_eye[0]) / 2
    shoulder_center_x = (l_shoulder[0] + r_shoulder[0]) / 2

    if eye_dist > 0.35 * shoulder_dist:
        return False
    if shoulder_height_diff > 40:
        return False

    return abs(head_center_x - shoulder_center_x) > 80


def is_turning_back(keypoints):
    """Detect turning back using eye-to-shoulder ratio"""
    if keypoints is None or len(keypoints) < 7:
        return False

    nose, l_eye, r_eye, l_ear, r_ear, l_shoulder, r_shoulder = keypoints[:7]
    if any(pt is None or pt[0] == 0.0 or pt[1] == 0.0
           for pt in [l_eye, r_eye, l_shoulder, r_shoulder]):
        return False

    eye_dist = abs(l_eye[0] - r_eye[0])
    shoulder_dist = abs(l_shoulder[0] - r_shoulder[0])

    if shoulder_dist < 10:
        return False

    eye_ratio = eye_dist / shoulder_dist
    return eye_ratio < 0.15


def is_hand_raised(keypoints):
    """Detect hand raise — wrist above shoulder"""
    if keypoints is None or len(keypoints) < 11:
        return False

    l_shoulder, r_shoulder, l_elbow, r_elbow, l_wrist, r_wrist = keypoints[5:11]

    left_valid = all(pt is not None and pt[0] != 0.0 for pt in [l_shoulder, l_wrist])
    if left_valid and l_wrist[1] < (l_shoulder[1] - 20):
        return True

    right_valid = all(pt is not None and pt[0] != 0.0 for pt in [r_shoulder, r_wrist])
    if right_valid and r_wrist[1] < (r_shoulder[1] - 20):
        return True

    return False


def calculate_distance(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))


def detect_passing_paper(wrists, keypoints_list):
    """Detect passing paper between multiple people"""
    if len(wrists) < 2:
        return False, []

    threshold = 200
    min_self_wrist_dist = 100
    max_vertical_diff = 150
    close_pairs = []
    passing = False

    for i in range(len(wrists)):
        host = wrists[i]
        if calculate_distance(*host) < min_self_wrist_dist:
            continue

        for j in range(i + 1, len(wrists)):
            other = wrists[j]
            if calculate_distance(*other) < min_self_wrist_dist:
                continue

            pairings = [
                (host[0], other[0]),
                (host[0], other[1]),
                (host[1], other[0]),
                (host[1], other[1]),
            ]
            for w_a, w_b in pairings:
                if w_a[0] == 0.0 or w_b[0] == 0.0:
                    continue
                if abs(w_a[1] - w_b[1]) > max_vertical_diff:
                    continue
                dist = calculate_distance(w_a, w_b)
                if dist < threshold:
                    close_pairs.append((i, j))
                    passing = True
    return passing, close_pairs


# ========================
# MOBILE CLASS ID
# ========================
try:
    import model_config
    _paths = model_config.get_model_paths()
    MOBILE_CLASS_ID = _paths.get("mobile_class_id", 67)
except Exception:
    MOBILE_CLASS_ID = 67  # COCO default


# ========================
# FRAME PROCESSOR CLASS
# ========================

class FrameProcessor:
    """
    Processes individual frames for malpractice detection.
    Maintains per-stream state for consecutive frame thresholds.
    Thread-safe: each teacher stream gets its own FrameProcessor instance.
    """

    # Thresholds (consecutive frames needed)
    LEANING_THRESHOLD = 3
    MOBILE_THRESHOLD = 5
    TURNING_THRESHOLD = 3
    PASSING_THRESHOLD = 3
    HAND_RAISE_THRESHOLD = 5

    # Cooldown: minimum seconds between same-type detections
    DETECTION_COOLDOWN = 30

    def __init__(self, lecture_hall='Unknown', teacher_id=None):
        self.lecture_hall = lecture_hall
        self.teacher_id = teacher_id

        # Ensure models are loaded
        _load_models()

        # Per-action consecutive frame counters
        self.leaning_frames = 0
        self.mobile_frames = 0
        self.turning_frames = 0
        self.passing_frames = 0
        self.hand_raise_frames = 0

        # Last detection timestamps (for cooldown)
        self.last_detections = {}

        # Frame counter
        self.frame_num = 0

        # Smart phone/calculator filter
        self.phone_detections = 0
        self.calculator_detections = 0

    def process_frame(self, frame_bytes):
        """
        Process a single JPEG frame.

        Args:
            frame_bytes: Raw JPEG bytes from webcam

        Returns:
            dict with:
                - annotated_frame: JPEG bytes of frame with detection overlays
                - detections: list of detected malpractice events (may be empty)
            or None on error
        """
        try:
            # Decode JPEG to numpy array
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return None

            self.frame_num += 1
            detections = []
            annotated = frame.copy()

            # ---- YOLO Pose Detection ----
            pose_results = _pose_model(frame, verbose=False, conf=0.3)
            all_keypoints = []
            all_wrists = []
            all_boxes = []

            for result in pose_results:
                if result.keypoints is not None and result.keypoints.data is not None:
                    for person_idx, kp_data in enumerate(result.keypoints.data):
                        kp = kp_data.cpu().numpy()
                        if len(kp) >= 11:
                            all_keypoints.append(kp)
                            # Extract wrists for passing paper detection
                            l_wrist = tuple(kp[9][:2])
                            r_wrist = tuple(kp[10][:2])
                            all_wrists.append((l_wrist, r_wrist))

                if result.boxes is not None:
                    for box in result.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        conf = float(box.conf[0])
                        all_boxes.append((x1, y1, x2, y2, conf))
                        # Draw person bounding box
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw keypoints on annotated frame
            for kp in all_keypoints:
                for point in kp[:17]:
                    x, y = int(point[0]), int(point[1])
                    if x > 0 and y > 0:
                        cv2.circle(annotated, (x, y), 3, (0, 255, 255), -1)

            # ---- Per-person behavior detection ----
            leaning_detected = False
            turning_detected = False
            hand_raise_detected = False

            for kp in all_keypoints:
                if is_leaning(kp):
                    leaning_detected = True
                if is_turning_back(kp):
                    turning_detected = True
                if is_hand_raised(kp):
                    hand_raise_detected = True

            # Passing paper (multi-person)
            passing_detected = False
            if len(all_wrists) >= 2:
                passing_detected, _ = detect_passing_paper(all_wrists, [])

            # ---- YOLO Object Detection (mobile phone) ----
            mobile_detected = False
            obj_results = _mobile_model(frame, verbose=False, conf=0.3)

            for result in obj_results:
                if result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        if cls_id == MOBILE_CLASS_ID and conf > 0.35:
                            # Smart filter: skip calculators (aspect ratio check)
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                            w = x2 - x1
                            h = y2 - y1
                            aspect = h / w if w > 0 else 0
                            # Phones are typically taller than wide (aspect > 1.3)
                            # or wider than tall for horizontal hold (aspect < 0.7)
                            if 0.3 < aspect < 3.0:
                                mobile_detected = True
                                # Draw mobile detection
                                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 3)
                                cv2.putText(annotated, f"PHONE {conf:.0%}",
                                            (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                                            0.7, (0, 0, 255), 2)

            # ---- Update consecutive frame counters ----
            self.leaning_frames = self.leaning_frames + 1 if leaning_detected else 0
            self.turning_frames = self.turning_frames + 1 if turning_detected else 0
            self.hand_raise_frames = self.hand_raise_frames + 1 if hand_raise_detected else 0
            self.passing_frames = self.passing_frames + 1 if passing_detected else 0
            self.mobile_frames = self.mobile_frames + 1 if mobile_detected else 0

            # ---- Check thresholds and emit detections ----
            now = time.time()

            if self.leaning_frames >= self.LEANING_THRESHOLD:
                if self._can_detect('Leaning', now):
                    detections.append({
                        'action': 'Leaning',
                        'probability': self._calc_probability('Leaning', self.leaning_frames),
                        'proof': '',
                    })
                    self.leaning_frames = 0

            if self.turning_frames >= self.TURNING_THRESHOLD:
                if self._can_detect('Turning Back', now):
                    detections.append({
                        'action': 'Turning Back',
                        'probability': self._calc_probability('Turning Back', self.turning_frames),
                        'proof': '',
                    })
                    self.turning_frames = 0

            if self.hand_raise_frames >= self.HAND_RAISE_THRESHOLD:
                if self._can_detect('Hand Raised', now):
                    detections.append({
                        'action': 'Hand Raised',
                        'probability': self._calc_probability('Hand Raised', self.hand_raise_frames),
                        'proof': '',
                    })
                    self.hand_raise_frames = 0

            if self.passing_frames >= self.PASSING_THRESHOLD:
                if self._can_detect('Passing Paper', now):
                    detections.append({
                        'action': 'Passing Paper',
                        'probability': self._calc_probability('Passing Paper', self.passing_frames),
                        'proof': '',
                    })
                    self.passing_frames = 0

            if self.mobile_frames >= self.MOBILE_THRESHOLD:
                if self._can_detect('Mobile Phone Detected', now):
                    detections.append({
                        'action': 'Mobile Phone Detected',
                        'probability': self._calc_probability('Mobile Phone Detected', self.mobile_frames),
                        'proof': '',
                    })
                    self.mobile_frames = 0

            # ---- Draw status overlay ----
            status_text = []
            if leaning_detected:
                status_text.append(f"LEANING ({self.leaning_frames})")
            if turning_detected:
                status_text.append(f"TURNING BACK ({self.turning_frames})")
            if hand_raise_detected:
                status_text.append(f"HAND RAISED ({self.hand_raise_frames})")
            if passing_detected:
                status_text.append(f"PASSING PAPER ({self.passing_frames})")
            if mobile_detected:
                status_text.append(f"MOBILE PHONE ({self.mobile_frames})")

            # Draw detection status on annotated frame
            y_offset = 30
            for text in status_text:
                cv2.putText(annotated, text, (10, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                y_offset += 30

            # Draw frame counter
            cv2.putText(annotated, f"Frame: {self.frame_num}",
                        (annotated.shape[1] - 200, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

            # People count
            cv2.putText(annotated, f"People: {len(all_keypoints)}",
                        (annotated.shape[1] - 200, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

            # Encode annotated frame to JPEG
            _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
            annotated_bytes = buffer.tobytes()

            return {
                'annotated_frame': annotated_bytes,
                'detections': detections,
            }

        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _can_detect(self, action, now):
        """Check cooldown — avoid flooding with same detection type"""
        last = self.last_detections.get(action, 0)
        if now - last >= self.DETECTION_COOLDOWN:
            self.last_detections[action] = now
            return True
        return False

    def _calc_probability(self, action, consecutive_frames):
        """Calculate probability score for live detection"""
        type_priors = {
            'Mobile Phone Detected': 0.85,
            'Turning Back': 0.75,
            'Leaning': 0.65,
            'Passing Paper': 0.60,
            'Hand Raised': 0.50,
        }
        type_score = type_priors.get(action, 0.50)

        # More consecutive frames = higher confidence
        threshold_map = {
            'Leaning': self.LEANING_THRESHOLD,
            'Mobile Phone Detected': self.MOBILE_THRESHOLD,
            'Turning Back': self.TURNING_THRESHOLD,
            'Passing Paper': self.PASSING_THRESHOLD,
            'Hand Raised': self.HAND_RAISE_THRESHOLD,
        }
        threshold = threshold_map.get(action, 3)
        sustainability = min(consecutive_frames / threshold, 5.0) / 5.0

        # Weighted score
        probability = (type_score * 0.50 + sustainability * 0.35 + 0.65 * 0.15) * 100
        return round(max(0, min(100, probability)), 1)
