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
import shutil
import threading
from collections import deque
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
_models_warmed = False  # True after first dummy inference


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


def prewarm_models():
    """Pre-load and warm up models with a dummy inference so first real frame is fast."""
    global _models_warmed
    if _models_warmed:
        return
    try:
        _load_models()
        # Run a dummy inference to JIT-compile / warm GPU caches
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        _pose_model(dummy, verbose=False, imgsz=320)    # Match ML_POSE_IMGSZ
        _mobile_model(dummy, verbose=False, imgsz=640)   # Match ML_MOBILE_IMGSZ
        _models_warmed = True
        logger.info("ML models pre-warmed with dummy inference")
    except Exception as e:
        logger.warning(f"Model pre-warm failed (will load on first use): {e}")


# ========================
# DETECTION HELPER FUNCTIONS
# ========================

def is_leaning(keypoints):
    """Detect leaning using nose-shoulder offset ratio (matches recorded video logic).
    Uses ratio-based detection that scales with any frame resolution."""
    if keypoints is None or len(keypoints) < 7:
        return False

    nose = keypoints[0]
    l_shoulder = keypoints[5]
    r_shoulder = keypoints[6]

    # Need good confidence on all key points
    if nose[2] < 0.5 or l_shoulder[2] < 0.5 or r_shoulder[2] < 0.5:
        return False

    shoulder_center_x = (l_shoulder[0] + r_shoulder[0]) / 2
    offset = abs(nose[0] - shoulder_center_x)
    shoulder_width = abs(r_shoulder[0] - l_shoulder[0])

    if shoulder_width > 0:
        lean_ratio = offset / shoulder_width
        return lean_ratio > 0.4  # Same threshold as recorded video

    return False


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
# SMART PHONE/CALCULATOR FILTER
# ========================

def is_likely_phone(x1, y1, x2, y2, conf, frame_width, frame_height):
    """Smart filter to distinguish mobile phones from calculators/remotes.
    
    Returns: (is_phone: bool, reason: str)
    """
    box_w = x2 - x1
    box_h = y2 - y1
    area = box_w * box_h
    frame_area = frame_width * frame_height
    area_ratio = area / frame_area if frame_area > 0 else 0
    aspect = box_w / box_h if box_h > 0 else 1.0

    # Too large at low confidence
    if area_ratio > 0.05 and conf < 0.45:
        return False, f"too large ({area_ratio:.1%}) at low conf {conf:.2f}"

    # Square + large + low confidence = likely calculator
    if 0.7 < aspect < 1.4 and area_ratio > 0.02 and conf < 0.40:
        return False, f"likely calculator (aspect:{aspect:.2f})"

    # Extremely large object
    if area_ratio > 0.10:
        return False, f"extremely large ({area_ratio:.1%})"

    return True, f"phone-like (aspect:{aspect:.2f}, area:{area_ratio:.2%}, conf:{conf:.2f})"


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
    Records video clips with pre-roll buffer and grace period (matching recorded video pipeline).
    Thread-safe: each teacher stream gets its own FrameProcessor instance.
    """

    # Detection thresholds (consecutive ML frames needed to START recording)
    LEANING_THRESHOLD = 3
    MOBILE_THRESHOLD = 3
    TURNING_THRESHOLD = 3
    PASSING_THRESHOLD = 3
    HAND_RAISE_THRESHOLD = 5

    # Video recording config
    INPUT_FPS = 15              # Expected webcam FPS from browser
    PRE_ROLL_SECONDS = 1.0      # Buffered seconds before detection (reduced for shorter clips)
    GRACE_FRAMES = 30           # ML-processed frames after detection stops (~2s at real ML rate)

    # ML inference resolution (lower = faster)
    ML_POSE_IMGSZ = 320     # Pose detection: 320 is fine for skeleton keypoints
    ML_MOBILE_IMGSZ = 640   # Mobile detection: needs higher res for small objects (matches recorded video)

    # COCO skeleton connection pairs
    SKELETON_PAIRS = [
        (0, 1), (0, 2), (1, 3), (2, 4),       # head
        (5, 6),                                  # shoulders
        (5, 7), (7, 9),                          # left arm
        (6, 8), (8, 10),                         # right arm
        (5, 11), (6, 12),                        # torso
        (11, 12),                                # hips
        (11, 13), (13, 15),                      # left leg
        (12, 14), (14, 16),                      # right leg
    ]

    # Action keys (must match names used in DB)
    ACTION_KEYS = ['Leaning', 'Turning Back', 'Hand Raised', 'Passing Paper', 'Mobile Phone Detected']

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

        # Frame counter
        self.frame_num = 0

        # ML FPS tracking (for accurate probability calc)
        self._ml_frame_count = 0
        self._ml_start_time = None
        self._actual_ml_fps = 15.0  # Will be updated as we process

        # === VIDEO RECORDING STATE ===
        self._recording_lock = threading.Lock()
        pre_roll_count = int(self.PRE_ROLL_SECONDS * self.INPUT_FPS)
        self._pre_roll_buffer = deque(maxlen=max(pre_roll_count, 10))

        # Per-action recording state
        self._recordings = {}
        for action in self.ACTION_KEYS:
            self._recordings[action] = {
                'active': False,
                'writer': None,
                'temp_path': '',
                'grace_frames': 0,
                'det_frames': 0,        # ML frames with active detection
                'total_ml_frames': 0,   # Total ML-processed frames during recording
                'total_frames': 0,      # Total buffered frames in recording (for video)
                'conf_sum': 0.0,
                'conf_count': 0,
            }

        # Completed detections (consumed by caller)
        self._completed_detections = []

        # Paths
        self._ml_dir = os.path.dirname(os.path.abspath(__file__))
        # media root: go up from ML/ to project root, then media/
        self._media_root = os.path.join(os.path.dirname(self._ml_dir), 'media')

        logger.info(f"FrameProcessor init: hall={lecture_hall}, teacher={teacher_id}, "
                     f"pre_roll={pre_roll_count} frames, grace={self.GRACE_FRAMES} frames, "
                     f"ML pose_imgsz={self.ML_POSE_IMGSZ}, mobile_imgsz={self.ML_MOBILE_IMGSZ}")

    # ===========================
    # FRAME BUFFERING (called for EVERY incoming frame)
    # ===========================

    def buffer_frame(self, jpeg_bytes):
        """
        Buffer a raw JPEG frame for video recording.
        Called for EVERY incoming frame (even those not ML-processed).
        Writes to active VideoWriters for smooth video.
        """
        with self._recording_lock:
            # Always add to pre-roll buffer (raw JPEG bytes)
            self._pre_roll_buffer.append(jpeg_bytes)

            # Write to all active recordings
            frame = None
            for action, rec in self._recordings.items():
                if rec['active'] and rec['writer'] is not None:
                    if frame is None:
                        nparr = np.frombuffer(jpeg_bytes, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if frame is None:
                            return
                    rec['writer'].write(frame)
                    rec['total_frames'] += 1

    # ===========================
    # RECORDING MANAGEMENT
    # ===========================

    def _start_recording(self, action, frame_width, frame_height):
        """Start video recording for an action — flush pre-roll buffer."""
        rec = self._recordings[action]
        if rec['active']:
            return

        safe_action = action.replace(' ', '_').lower()
        temp_path = os.path.join(self._ml_dir, f'temp_live_{safe_action}_{self.teacher_id}.mp4')

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(temp_path, fourcc, self.INPUT_FPS, (frame_width, frame_height))

        if not writer.isOpened():
            logger.error(f"Failed to open VideoWriter for {action} at {temp_path}")
            return

        # Flush pre-roll buffer (decode JPEG → write to video)
        pre_roll_count = 0
        for jpeg in self._pre_roll_buffer:
            nparr = np.frombuffer(jpeg, np.uint8)
            f = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if f is not None:
                h, w = f.shape[:2]
                if w != frame_width or h != frame_height:
                    f = cv2.resize(f, (frame_width, frame_height))
                writer.write(f)
                pre_roll_count += 1

        rec['active'] = True
        rec['writer'] = writer
        rec['temp_path'] = temp_path
        rec['grace_frames'] = 0
        rec['det_frames'] = 0
        rec['total_ml_frames'] = 0
        rec['total_frames'] = pre_roll_count
        rec['conf_sum'] = 0.0
        rec['conf_count'] = 0

        logger.info(f"Recording STARTED: {action} (pre-roll: {pre_roll_count} frames)")

    def _finalize_recording(self, action):
        """Stop recording and save video to media directory. Returns detection dict or None."""
        rec = self._recordings[action]
        if not rec['active']:
            return None

        rec['active'] = False
        if rec['writer']:
            rec['writer'].release()
            rec['writer'] = None

        temp_path = rec['temp_path']
        total_frames = rec['total_frames']

        if not os.path.exists(temp_path) or total_frames < 5:
            # Too short — discard
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            self._reset_recording_state(action)
            return None

        # Copy to media directory
        os.makedirs(self._media_root, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_action = action.replace(' ', '_').lower()
        filename = f'live_{safe_action}_{self.teacher_id}_{timestamp}.mp4'
        final_path = os.path.join(self._media_root, filename)

        try:
            shutil.copy(temp_path, final_path)
        except Exception as e:
            logger.error(f"Failed to copy recording {temp_path} → {final_path}: {e}")
            self._reset_recording_state(action)
            return None

        # Calculate probability score
        # Use ML-processed frame ratio (not total buffered frames)
        total_ml_frames = rec.get('total_ml_frames', 0) or max(rec['det_frames'], 1)
        probability = self._calc_probability_video(
            action, rec['det_frames'], total_ml_frames,
            rec['conf_sum'] / rec['conf_count'] if rec['conf_count'] > 0 else 0.0
        )

        # Cleanup temp file
        try:
            os.remove(temp_path)
        except Exception:
            pass

        det_frames = rec['det_frames']
        self._reset_recording_state(action)

        logger.info(f"Recording SAVED: {action} → {filename} "
                     f"({total_frames} frames, {det_frames} detection frames, prob={probability}%)")

        return {
            'action': action,
            'proof': filename,
            'probability': probability,
        }

    def _reset_recording_state(self, action):
        """Reset a single action's recording counters."""
        rec = self._recordings[action]
        rec['grace_frames'] = 0
        rec['det_frames'] = 0
        rec['total_ml_frames'] = 0
        rec['total_frames'] = 0
        rec['conf_sum'] = 0.0
        rec['conf_count'] = 0

    def finalize_all_recordings(self):
        """Finalize all active recordings — called on stream disconnect."""
        completed = []
        with self._recording_lock:
            for action in self.ACTION_KEYS:
                result = self._finalize_recording(action)
                if result:
                    completed.append(result)
        return completed

    # ===========================
    # ML FRAME PROCESSING
    # ===========================

    def process_frame(self, frame_bytes):
        """
        Process a single JPEG frame with ML detection.

        Called by the consumer's ML thread (with frame-dropping).
        Manages recording state based on detections.

        Returns:
            dict with:
                - annotated_frame: JPEG bytes with detection overlays
                - detections: list of COMPLETED detections (with video proof)
            or None on error
        """
        try:
            # Decode JPEG to numpy array
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return None

            self.frame_num += 1
            h_frame, w_frame = frame.shape[:2]
            completed_detections = []
            annotated = frame.copy()

            # Track ML FPS for accurate probability scoring
            self._ml_frame_count += 1
            now = time.time()
            if self._ml_start_time is None:
                self._ml_start_time = now
            elif now - self._ml_start_time > 2.0:
                self._actual_ml_fps = self._ml_frame_count / (now - self._ml_start_time)
                self._ml_frame_count = 0
                self._ml_start_time = now

            # ---- YOLO Pose Detection (320px for speed — skeleton doesn't need high res) ----
            pose_results = _pose_model(frame, verbose=False, conf=0.3, imgsz=self.ML_POSE_IMGSZ)
            all_keypoints = []
            all_wrists = []
            all_boxes = []

            # Scale factors: YOLO returns coords in original frame space when
            # imgsz is set, so no manual scaling needed
            for result in pose_results:
                if result.keypoints is not None and result.keypoints.data is not None:
                    for person_idx, kp_data in enumerate(result.keypoints.data):
                        kp = kp_data.cpu().numpy()
                        if len(kp) >= 11:
                            all_keypoints.append(kp)
                            l_wrist = tuple(kp[9][:2])
                            r_wrist = tuple(kp[10][:2])
                            all_wrists.append((l_wrist, r_wrist))

                if result.boxes is not None:
                    for box in result.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        conf = float(box.conf[0])
                        all_boxes.append((x1, y1, x2, y2, conf))
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # ---- Per-person behavior detection ----
            leaning_detected = False
            turning_detected = False
            hand_raise_detected = False

            for kp in all_keypoints:
                # Turning back check FIRST (priority over leaning — mutual exclusion)
                if is_turning_back(kp):
                    turning_detected = True
                elif is_leaning(kp):
                    leaning_detected = True
                if is_hand_raised(kp):
                    hand_raise_detected = True

            # Passing paper (multi-person)
            passing_detected = False
            if len(all_wrists) >= 2:
                passing_detected, _ = detect_passing_paper(all_wrists, [])

            # ---- YOLO Object Detection (mobile phone) — 640px for small objects ----
            mobile_detected = False
            mobile_conf = 0.0
            obj_results = _mobile_model(frame, verbose=False, conf=0.25, imgsz=self.ML_MOBILE_IMGSZ)

            for result in obj_results:
                if result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        if cls_id == MOBILE_CLASS_ID and conf > 0.25:
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)

                            # Smart phone/calculator filter
                            is_phone, reason = is_likely_phone(x1, y1, x2, y2, conf, w_frame, h_frame)
                            if not is_phone:
                                continue

                            mobile_detected = True
                            mobile_conf = max(mobile_conf, conf)

                            # Draw mobile detection with thick orange box
                            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 165, 255), 3)
                            label = f"PHONE {conf:.0%}"
                            (tw, th_t), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
                            cv2.rectangle(annotated, (x1, y1 - th_t - 10), (x1 + tw, y1), (0, 165, 255), -1)
                            cv2.putText(annotated, label,
                                        (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX,
                                        0.8, (255, 255, 255), 2)

            # ---- Draw skeleton keypoints and limb connections ----
            for person_idx, kp in enumerate(all_keypoints):
                person_leaning = is_leaning(kp)
                person_turning = is_turning_back(kp)
                person_hand_raised = is_hand_raised(kp)

                if person_leaning:
                    color = (0, 0, 255)       # Red
                elif person_turning:
                    color = (255, 0, 255)     # Magenta
                elif person_hand_raised:
                    color = (0, 255, 255)     # Cyan
                else:
                    color = (0, 255, 0)       # Green

                # Skeleton limb connections
                for (i, j) in self.SKELETON_PAIRS:
                    if i < len(kp) and j < len(kp):
                        x1, y1 = int(kp[i][0]), int(kp[i][1])
                        x2, y2 = int(kp[j][0]), int(kp[j][1])
                        if x1 > 0 and y1 > 0 and x2 > 0 and y2 > 0:
                            cv2.line(annotated, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

                # Keypoint circles
                for idx, point in enumerate(kp[:17]):
                    x, y = int(point[0]), int(point[1])
                    if x > 0 and y > 0:
                        if idx in (9, 10) and passing_detected:
                            cv2.circle(annotated, (x, y), 6, (255, 0, 0), -1)
                            cv2.circle(annotated, (x, y), 8, (255, 0, 0), 2)
                        else:
                            cv2.circle(annotated, (x, y), 5, color, -1)

            # ---- Update consecutive frame counters ----
            self.leaning_frames = self.leaning_frames + 1 if leaning_detected else 0
            self.turning_frames = self.turning_frames + 1 if turning_detected else 0
            self.hand_raise_frames = self.hand_raise_frames + 1 if hand_raise_detected else 0
            self.passing_frames = self.passing_frames + 1 if passing_detected else 0
            self.mobile_frames = self.mobile_frames + 1 if mobile_detected else 0

            # ---- Recording management (lock for thread safety with buffer_frame) ----
            with self._recording_lock:
                # Map action → (counter, threshold, detected_flag, confidence)
                action_map = [
                    ('Leaning', self.leaning_frames, self.LEANING_THRESHOLD, leaning_detected, 0.0),
                    ('Turning Back', self.turning_frames, self.TURNING_THRESHOLD, turning_detected, 0.0),
                    ('Hand Raised', self.hand_raise_frames, self.HAND_RAISE_THRESHOLD, hand_raise_detected, 0.0),
                    ('Passing Paper', self.passing_frames, self.PASSING_THRESHOLD, passing_detected, 0.0),
                    ('Mobile Phone Detected', self.mobile_frames, self.MOBILE_THRESHOLD, mobile_detected, mobile_conf),
                ]

                for action, counter, threshold, detected, conf in action_map:
                    rec = self._recordings[action]

                    if counter >= threshold:
                        # Detection active — reset grace, start recording if needed
                        rec['grace_frames'] = 0
                        if not rec['active']:
                            self._start_recording(action, w_frame, h_frame)

                        # Track detection density (ML frames only)
                        if rec['active']:
                            rec['total_ml_frames'] += 1
                            if detected:
                                rec['det_frames'] += 1
                                if conf > 0:
                                    rec['conf_sum'] += conf
                                    rec['conf_count'] += 1
                                elif all_keypoints:
                                    # Use average keypoint confidence for pose-based detections
                                    kp = all_keypoints[0]
                                    avg_kp_conf = float(np.mean([kp[ki][2] for ki in range(min(len(kp), 17)) if kp[ki][2] > 0]))
                                    rec['conf_sum'] += avg_kp_conf
                                    rec['conf_count'] += 1
                    else:
                        # Detection stopped — grace period countdown
                        if rec['active']:
                            rec['total_ml_frames'] += 1
                            rec['grace_frames'] += 1
                            if rec['grace_frames'] >= self.GRACE_FRAMES:
                                result = self._finalize_recording(action)
                                if result:
                                    completed_detections.append(result)

            # ---- Draw status overlay ----
            action_labels = []
            if leaning_detected:
                status = "REC" if self._recordings['Leaning']['active'] else ""
                action_labels.append((f"LEANING ({self.leaning_frames}) {status}", (0, 0, 255)))
            if turning_detected:
                status = "REC" if self._recordings['Turning Back']['active'] else ""
                action_labels.append((f"TURNING BACK ({self.turning_frames}) {status}", (255, 0, 255)))
            if hand_raise_detected:
                status = "REC" if self._recordings['Hand Raised']['active'] else ""
                action_labels.append((f"HAND RAISED ({self.hand_raise_frames}) {status}", (0, 255, 255)))
            if passing_detected:
                status = "REC" if self._recordings['Passing Paper']['active'] else ""
                action_labels.append((f"PASSING PAPER ({self.passing_frames}) {status}", (255, 0, 0)))
            if mobile_detected:
                status = "REC" if self._recordings['Mobile Phone Detected']['active'] else ""
                action_labels.append((f"MOBILE PHONE ({self.mobile_frames}) {status}", (0, 165, 255)))

            # Show recording indicators for actions recording in grace period
            for action in self.ACTION_KEYS:
                rec = self._recordings[action]
                if rec['active'] and not any(action.upper().startswith(label[0].split('(')[0].strip().upper().split()[0]) for label in action_labels):
                    action_labels.append((f"{action.upper()} (grace {rec['grace_frames']}/{self.GRACE_FRAMES}) REC", (128, 128, 128)))

            y_offset = 30
            for text, text_color in action_labels:
                (tw, th_t), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
                overlay = annotated.copy()
                cv2.rectangle(overlay, (8, y_offset - th_t - 4), (16 + tw, y_offset + baseline + 4), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.6, annotated, 0.4, 0, annotated)
                cv2.putText(annotated, text, (12, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, text_color, 2, cv2.LINE_AA)
                y_offset += th_t + 14

            # Info overlay (top-right)
            active_recs = sum(1 for a in self.ACTION_KEYS if self._recordings[a]['active'])
            info_lines = [
                f"ML Processing",
                f"People: {len(all_keypoints)}",
            ]
            if active_recs > 0:
                info_lines.append(f"Recording: {active_recs}")

            for idx_line, info_text in enumerate(info_lines):
                (tw, th_t), _ = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                x_pos = w_frame - tw - 12
                y_pos = 25 + idx_line * 28
                overlay = annotated.copy()
                cv2.rectangle(overlay, (x_pos - 4, y_pos - th_t - 2), (w_frame - 4, y_pos + 6), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.5, annotated, 0.5, 0, annotated)
                cv2.putText(annotated, info_text, (x_pos, y_pos),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)

            # Encode annotated frame to JPEG (70% quality for faster encode/send)
            _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            annotated_bytes = buffer.tobytes()

            return {
                'annotated_frame': annotated_bytes,
                'detections': completed_detections,
            }

        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ===========================
    # PROBABILITY SCORING
    # ===========================

    def _calc_probability_video(self, action, detection_frames, total_frames,
                                 avg_confidence=0.0):
        """
        Calculate AI probability score for a video clip detection.
        Matches the recorded video pipeline's scoring system.
        """
        type_priors = {
            'Mobile Phone Detected': 0.85,
            'Turning Back': 0.75,
            'Leaning': 0.65,
            'Passing Paper': 0.60,
            'Hand Raised': 0.50,
        }
        type_score = type_priors.get(action, 0.50)

        # Clip duration factor (25%): use ML frame count / actual ML FPS
        # total_frames here is total_ml_frames (not buffered video frames)
        ml_fps = max(self._actual_ml_fps, 3.0)  # floor at 3 FPS
        clip_duration = total_frames / ml_fps if ml_fps > 0 else 0
        if clip_duration >= 8:
            duration_score = 1.0
        elif clip_duration >= 4:
            duration_score = 0.7 + (clip_duration - 4) * 0.075
        elif clip_duration >= 2:
            duration_score = 0.4 + (clip_duration - 2) * 0.15
        else:
            duration_score = max(0.2, clip_duration * 0.2)

        # Detection density factor (30%): what % of ML-processed frames had active detection
        # This is now accurate because we use ML frames, not buffered video frames
        if total_frames > 0 and detection_frames > 0:
            density = min(detection_frames / total_frames, 1.0)
        else:
            density = 0.5

        # Confidence factor (20%)
        confidence_score = min(avg_confidence, 1.0) if avg_confidence > 0 else 0.65

        # Sustainability factor (15%): how many multiples of threshold were detected
        threshold_map = {
            'Leaning': self.LEANING_THRESHOLD,
            'Mobile Phone Detected': self.MOBILE_THRESHOLD,
            'Turning Back': self.TURNING_THRESHOLD,
            'Passing Paper': self.PASSING_THRESHOLD,
            'Hand Raised': self.HAND_RAISE_THRESHOLD,
        }
        threshold = threshold_map.get(action, 3)
        sustainability = min(detection_frames / threshold, 5.0) / 5.0

        # Weighted combination
        probability = (
            duration_score * 0.25
            + density * 0.30
            + confidence_score * 0.20
            + sustainability * 0.15
            + type_score * 0.10
        ) * 100

        logger.info(f"Probability calc: {action} dur={clip_duration:.1f}s "
                     f"density={density:.2f} conf={confidence_score:.2f} "
                     f"sustain={sustainability:.2f} type={type_score:.2f} "
                     f"→ {probability:.1f}%")

        return round(max(0, min(100, probability)), 1)
