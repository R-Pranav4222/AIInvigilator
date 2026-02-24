# process_uploaded_video_stream.py
# Video processor that yields frames for live streaming
import sys
import os
import cv2
import numpy as np
import mysql.connector
from datetime import datetime
import torch
import shutil
from collections import deque

# Add parent directory to path for imports
sys.path.append(os.path.dirname(__file__))

# Import GPU configuration
try:
    from gpu_config import DEVICE
    GPU_AVAILABLE = True
except:
    DEVICE = 'cpu'
    GPU_AVAILABLE = False

from ultralytics import YOLO

# Database configuration
DB_USER = "root"
DB_PASSWORD = "robertlewandowski"
DB_NAME = "aiinvigilator_db"

# Model paths
try:
    import model_config
    _paths = model_config.get_model_paths()
    POSE_MODEL_PATH = _paths["pose_detection"]
    MOBILE_MODEL_PATH = _paths["object_detection"]
    MOBILE_CLASS_ID = _paths.get("mobile_class_id", 67)
except ImportError:
    POSE_MODEL_PATH = "yolov8n-pose.pt"
    MOBILE_MODEL_PATH = "yolo11n.pt"
    MOBILE_CLASS_ID = 67

# Media directory (relative to app folder)
MEDIA_DIR = os.path.join(os.path.dirname(__file__), "..", "media")

# Thresholds (adjusted for frame skipping)
# With frame_skip=3, 3 processed frames = 9 actual frames = 0.3 seconds at 30fps
# Lowered to 3 frames to catch short actions (grace period extends to 4+ seconds anyway)
LEANING_THRESHOLD = 3
PASSING_THRESHOLD = 3
MOBILE_THRESHOLD = 3
TURNING_THRESHOLD = 3
HAND_RAISE_THRESHOLD = 3
CHEAT_THRESHOLD = 3

# Grace periods - keep recording for 3 seconds after action stops (exactly like front.py)
# With frame_skip=3, 30 processed frames = 90 actual frames = 3 seconds at 30fps
LEANING_GRACE_PERIOD = 30
PASSING_GRACE_PERIOD = 30
MOBILE_GRACE_PERIOD = 30
TURNING_GRACE_PERIOD = 30
HAND_RAISE_GRACE_PERIOD = 30
PEEKING_THRESHOLD = 30
TALKING_THRESHOLD = 30
SUSPICIOUS_THRESHOLD = 30

# Action strings
LEANING_ACTION = "Leaning"
PASSING_ACTION = "Passing Paper"
ACTION_MOBILE = "Mobile Phone Detected"
TURNING_ACTION = "Turning Back"
HAND_RAISE_ACTION = "Hand Raised"
CHEAT_MATERIAL_ACTION = "Cheat Material"
PEEKING_ACTION = "Peeking"
TALKING_ACTION = "Talking"
SUSPICIOUS_ACTION = "Suspicious Behavior"

# Colors for detection overlays (BGR format)
COLOR_LEANING = (0, 165, 255)      # Orange
COLOR_MOBILE = (0, 140, 255)       # Dark Orange
COLOR_TURNING = (0, 0, 255)        # Red
COLOR_PASSING = (255, 0, 255)      # Magenta  
COLOR_HAND_RAISE = (255, 255, 0)   # Cyan
COLOR_TALKING = (0, 255, 0)        # Green
COLOR_PEEKING = (255, 0, 255)      # Magenta
COLOR_CHEAT = (180, 105, 255)      # Pink
COLOR_SUSPICIOUS = (0, 255, 255)   # Yellow


# ===== MODEL CACHE (load once, reuse across uploads) =====
# Loading YOLO models + moving to GPU takes 10-15s.
# By caching them as module-level globals, subsequent uploads start instantly.
_cached_pose_model = None
_cached_mobile_model = None
_cached_half_precision = False


def get_cached_models():
    """Load models once and cache them. Returns (pose_model, mobile_model, use_half)."""
    global _cached_pose_model, _cached_mobile_model, _cached_half_precision
    
    if _cached_pose_model is not None and _cached_mobile_model is not None:
        print("\u26a1 Models already cached - instant start!")
        return _cached_pose_model, _cached_mobile_model, _cached_half_precision
    
    print("\U0001f4e6 Loading models (first time - will be cached for next upload)...")
    _cached_pose_model = YOLO(POSE_MODEL_PATH)
    _cached_mobile_model = YOLO(MOBILE_MODEL_PATH)
    
    _cached_half_precision = False
    if GPU_AVAILABLE:
        _cached_pose_model.to(DEVICE)
        _cached_mobile_model.to(DEVICE)
        try:
            if 'cuda' in str(DEVICE):
                _cached_half_precision = True
                print(f"\u2705 Models loaded on {DEVICE} with FP16 (half precision)")
            else:
                print(f"\u2705 Models loaded on {DEVICE}")
        except:
            print(f"\u2705 Models loaded on {DEVICE}")
    else:
        print("\u2705 Models loaded on CPU")
    
    # Warm up models with a dummy inference (CUDA lazy initialization)
    print("\U0001f525 Warming up models (CUDA kernel compilation)...")
    try:
        import time as _t
        _warmup_start = _t.time()
        dummy = np.zeros((416, 416, 3), dtype=np.uint8)
        _cached_pose_model(dummy, verbose=False, half=_cached_half_precision, imgsz=416)
        _cached_mobile_model(dummy, verbose=False, half=_cached_half_precision, imgsz=640)
        print(f"\u2705 Warmup done in {_t.time() - _warmup_start:.1f}s")
    except Exception as e:
        print(f"\u26a0\ufe0f Warmup failed (non-critical): {e}")
    
    return _cached_pose_model, _cached_mobile_model, _cached_half_precision


def is_likely_phone(x1, y1, x2, y2, conf, frame_width, frame_height):
    """Smart filter to distinguish mobile phones from calculators/remotes.
    
    Calculators are typically:
    - Larger than phones (bigger bounding box area)
    - More square or landscape aspect ratio
    - Detected at lower confidence than real phones
    
    Real phones are typically:
    - Smaller bounding boxes
    - Portrait or elongated aspect ratio
    - Higher confidence detections
    
    Returns: (is_phone: bool, reason: str)
    """
    box_w = x2 - x1
    box_h = y2 - y1
    area = box_w * box_h
    frame_area = frame_width * frame_height
    area_ratio = area / frame_area if frame_area > 0 else 0
    
    # Aspect ratio: width/height (phone portrait < 1.0, landscape > 1.0)
    aspect = box_w / box_h if box_h > 0 else 1.0
    
    # === REJECT criteria (definitely NOT a phone) ===
    
    # Too large: object covers >5% of frame (calculator, book, laptop)
    if area_ratio > 0.05 and conf < 0.45:
        return False, f"too large ({area_ratio:.1%} of frame) at low conf {conf:.2f}"
    
    # Very square + large + low confidence = very likely calculator
    if 0.7 < aspect < 1.4 and area_ratio > 0.02 and conf < 0.40:
        return False, f"square shape ({aspect:.2f}) + large ({area_ratio:.1%}) + low conf {conf:.2f} = likely calculator"
    
    # Extremely large object at any confidence = not a phone
    if area_ratio > 0.10:
        return False, f"extremely large ({area_ratio:.1%} of frame)"
    
    # === ACCEPT: passes all filters ===
    return True, f"phone-like (aspect:{aspect:.2f}, area:{area_ratio:.2%}, conf:{conf:.2f})"


def calculate_malpractice_probability(action, video_filepath, detection_frames=0, 
                                      total_recording_frames=0, avg_confidence=0.0, fps=30):
    """
    Multi-factor AI probability scoring for malpractice detection.
    Returns a score from 0-100 representing how likely the detection is real malpractice.
    
    Factors:
    1. Clip Duration (30%) — longer sustained clips = more likely real
    2. Detection Frame Density (25%) — what fraction of recording had active detection  
    3. Detection Confidence (20%) — average YOLO/pose confidence during detection
    4. Detection Sustainability (15%) — how far above threshold the detection went
    5. Malpractice Type Prior (10%) — type-specific false positive rates
    """
    
    # ===== Factor 1: Clip Duration Score (30% weight) =====
    # Get video duration from file
    clip_duration = 0.0
    try:
        cap = cv2.VideoCapture(video_filepath)
        if cap.isOpened():
            total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            vid_fps = cap.get(cv2.CAP_PROP_FPS) or fps
            clip_duration = total / vid_fps if vid_fps > 0 else 0
            cap.release()
    except:
        pass
    
    if clip_duration <= 0 and total_recording_frames > 0:
        # Fallback: estimate from frame count
        clip_duration = total_recording_frames / fps
    
    # Duration scoring: < 1s → 0.15, 1-2s → 0.30, 2-4s → 0.55, 4-6s → 0.75, 6-10s → 0.90, 10+ → 1.0
    if clip_duration >= 10:
        duration_score = 1.0
    elif clip_duration >= 6:
        duration_score = 0.90
    elif clip_duration >= 4:
        duration_score = 0.75
    elif clip_duration >= 2:
        duration_score = 0.55
    elif clip_duration >= 1:
        duration_score = 0.30
    else:
        duration_score = 0.15
    
    # ===== Factor 2: Detection Frame Density (25% weight) =====
    # What fraction of the total recording frames actually had the action detected
    if total_recording_frames > 0 and detection_frames > 0:
        density = min(detection_frames / total_recording_frames, 1.0)
        # Higher density = more consistent detection
        density_score = min(density * 1.5, 1.0)  # Boost slightly, cap at 1.0
    else:
        density_score = 0.3  # Default if no data
    
    # ===== Factor 3: Detection Confidence (20% weight) =====
    # Average YOLO/pose confidence during detection
    if avg_confidence > 0:
        # Confidence is typically 0.25-0.95 for valid detections
        # Map to 0-1: conf < 0.30 → low, 0.30-0.50 → medium, 0.50+ → high
        if avg_confidence >= 0.70:
            conf_score = 1.0
        elif avg_confidence >= 0.50:
            conf_score = 0.80
        elif avg_confidence >= 0.35:
            conf_score = 0.55
        elif avg_confidence >= 0.25:
            conf_score = 0.35
        else:
            conf_score = 0.15
    else:
        conf_score = 0.5  # Default if no confidence data available
    
    # ===== Factor 4: Detection Sustainability (15% weight) =====
    # How many frames above threshold — sustained detection = more reliable
    threshold_map = {
        LEANING_ACTION: LEANING_THRESHOLD,
        ACTION_MOBILE: MOBILE_THRESHOLD,
        PASSING_ACTION: PASSING_THRESHOLD,
        TURNING_ACTION: TURNING_THRESHOLD,
        HAND_RAISE_ACTION: HAND_RAISE_THRESHOLD,
    }
    threshold = threshold_map.get(action, 3)
    
    if detection_frames > 0:
        sustainability_ratio = detection_frames / threshold
        if sustainability_ratio >= 5:
            sustainability_score = 1.0
        elif sustainability_ratio >= 3:
            sustainability_score = 0.85
        elif sustainability_ratio >= 2:
            sustainability_score = 0.65
        elif sustainability_ratio >= 1.5:
            sustainability_score = 0.45
        else:
            sustainability_score = 0.25
    else:
        sustainability_score = 0.25
    
    # ===== Factor 5: Malpractice Type Prior (10% weight) =====
    # Based on historical false positive rates per detection type
    type_priors = {
        ACTION_MOBILE: 0.85,        # YOLO object detection — very accurate
        TURNING_ACTION: 0.75,       # Pose-based, fairly distinct
        LEANING_ACTION: 0.65,       # Pose-based, can be natural posture  
        PASSING_ACTION: 0.60,       # Wrist proximity heuristic, can be coincidental
        HAND_RAISE_ACTION: 0.50,    # Could be legitimate behavior
    }
    type_score = type_priors.get(action, 0.50)
    
    # ===== Weighted Combination =====
    probability = (
        duration_score * 0.30 +
        density_score * 0.25 +
        conf_score * 0.20 +
        sustainability_score * 0.15 +
        type_score * 0.10
    ) * 100
    
    # Clamp to 0-100
    probability = max(0.0, min(100.0, round(probability, 1)))
    
    print(f"   📊 Probability Score: {probability}%")
    print(f"      Duration: {clip_duration:.1f}s → {duration_score:.2f} (30%)")
    print(f"      Density: {detection_frames}/{total_recording_frames} → {density_score:.2f} (25%)")
    print(f"      Confidence: {avg_confidence:.2f} → {conf_score:.2f} (20%)")
    print(f"      Sustainability: {detection_frames}/{threshold}x → {sustainability_score:.2f} (15%)")
    print(f"      Type Prior ({action}): {type_score:.2f} (10%)")
    
    return probability


def save_video_to_database(action, video_filepath, lecture_hall_id, 
                           detection_frames=0, total_recording_frames=0, 
                           avg_confidence=0.0, fps=30):
    """Save video clip to database with AI probability score.
    
    Args:
        action: Type of malpractice detected
        video_filepath: Path to the proof video
        lecture_hall_id: ID of the lecture hall
        detection_frames: Number of frames with active detection
        total_recording_frames: Total frames in the recording
        avg_confidence: Average YOLO/pose confidence score
        fps: Video FPS for duration calculation
    """
    try:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        
        # Extract just the filename for database
        proof_filename = os.path.basename(video_filepath)
        
        # Calculate AI probability score
        probability = calculate_malpractice_probability(
            action, video_filepath, detection_frames, 
            total_recording_frames, avg_confidence, fps
        )
        
        db = mysql.connector.connect(
            host="localhost",
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = db.cursor()
        
        sql = """INSERT INTO app_malpraticedetection 
                 (date, time, malpractice, proof, lecture_hall_id, verified, probability_score) 
                 VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        
        cursor.execute(sql, (date_str, time_str, action, proof_filename, lecture_hall_id, False, probability))
        db.commit()
        cursor.close()
        db.close()
        
        print(f"\n✅ SAVED TO DATABASE: {action}")
        print(f"   🎥 Video: {proof_filename}")
        print(f"   🕒 Time: {time_str}")
        print(f"   📊 AI Probability: {probability}%")
        return True
    except Exception as e:
        print(f"❌ Database save error: {e}")
        import traceback
        traceback.print_exc()
        return False


def is_leaning(keypoints, frame_width, frame_height):
    """Check if person is leaning (rule-based)"""
    try:
        nose = keypoints[0]
        left_shoulder = keypoints[5]
        right_shoulder = keypoints[6]
        
        if nose[2] < 0.5 or left_shoulder[2] < 0.5 or right_shoulder[2] < 0.5:
            return False
        
        shoulder_center_x = (left_shoulder[0] + right_shoulder[0]) / 2
        offset = abs(nose[0] - shoulder_center_x)
        shoulder_width = abs(right_shoulder[0] - left_shoulder[0])
        
        if shoulder_width > 0:
            lean_ratio = offset / shoulder_width
            return lean_ratio > 0.4
        
        return False
    except:
        return False


def is_turning_back(keypoints):
    """Check if person is turning back (eye ratio)"""
    try:
        left_eye = keypoints[1]
        right_eye = keypoints[2]
        left_shoulder = keypoints[5]
        right_shoulder = keypoints[6]
        
        if all(kp[2] > 0.5 for kp in [left_eye, right_eye, left_shoulder, right_shoulder]):
            eye_dist = np.linalg.norm(np.array(left_eye[:2]) - np.array(right_eye[:2]))
            shoulder_dist = np.linalg.norm(np.array(left_shoulder[:2]) - np.array(right_shoulder[:2]))
            
            if shoulder_dist > 0:
                eye_ratio = eye_dist / shoulder_dist
                return eye_ratio < 0.15  # Balanced sensitivity
        
        return False
    except:
        return False


def is_hand_raised(keypoints):
    """Check if hand is raised"""
    try:
        nose = keypoints[0]
        left_wrist = keypoints[9]
        right_wrist = keypoints[10]
        
        if nose[2] < 0.5:
            return False
        
        if left_wrist[2] > 0.5 and left_wrist[1] < nose[1]:
            return True
        if right_wrist[2] > 0.5 and right_wrist[1] < nose[1]:
            return True
        
        return False
    except:
        return False


def calculate_distance(p1, p2):
    """Calculate Euclidean distance between two points."""
    return np.linalg.norm(np.array(p1) - np.array(p2))


def detect_passing_paper(wrists, keypoints_list):
    """Detect paper passing by checking if wrists from DIFFERENT people are close together.
    
    This is a multi-person detection: requires at least 2 people.
    Checks if any wrist from person A is close to any wrist from person B.
    Filters out vertical hand raises to avoid false positives.
    
    Args:
        wrists: list of [(left_wrist_xy, right_wrist_xy), ...] per person
        keypoints_list: list of keypoints arrays per person (for hand raise filtering)
    
    Returns:
        (passing_detected: bool, close_pairs: list)
    """
    if len(wrists) < 2:
        return False, []
    
    threshold = 200          # Max distance between wrists to count as passing
    min_self_wrist_dist = 100  # Skip person if their own wrists are too close (bad pose)
    max_vertical_diff = 150  # Max vertical difference between wrists

    close_pairs = []
    passing_detected = False

    for i in range(len(wrists)):
        host = wrists[i]
        # Skip if person's own wrists are too close (invalid pose)
        if calculate_distance(host[0], host[1]) < min_self_wrist_dist:
            continue
        
        # Check if BOTH wrists are straight up (vertical hand raise) - skip if so
        skip_vertical_raise = False
        if i < len(keypoints_list):
            kp = keypoints_list[i]
            if len(kp) >= 11:
                l_shoulder = kp[5]
                r_shoulder = kp[6]
                l_elbow = kp[7]
                r_elbow = kp[8]
                shoulder_y = min(l_shoulder[1], r_shoulder[1])
                if (host[0][1] < shoulder_y - 80 and host[1][1] < shoulder_y - 80 and
                    l_elbow[1] < shoulder_y - 40 and r_elbow[1] < shoulder_y - 40):
                    skip_vertical_raise = True
        
        if skip_vertical_raise:
            continue
        
        for j in range(i + 1, len(wrists)):
            other = wrists[j]
            if calculate_distance(other[0], other[1]) < min_self_wrist_dist:
                continue
            
            # Skip if other person has clear vertical hand raise
            skip_other_raise = False
            if j < len(keypoints_list):
                kp_other = keypoints_list[j]
                if len(kp_other) >= 7:
                    l_shoulder = kp_other[5]
                    r_shoulder = kp_other[6]
                    shoulder_y = min(l_shoulder[1], r_shoulder[1])
                    if other[0][1] < shoulder_y - 80 and other[1][1] < shoulder_y - 80:
                        skip_other_raise = True
            
            if skip_other_raise:
                continue
            
            # Check all 4 wrist pairings between the two people
            pairings = [
                (host[0], other[0]),
                (host[0], other[1]),
                (host[1], other[0]),
                (host[1], other[1])
            ]
            for w_a, w_b in pairings:
                if w_a[0] == 0.0 or w_b[0] == 0.0:
                    continue
                if abs(w_a[1] - w_b[1]) > max_vertical_diff:
                    continue
                dist = calculate_distance(w_a, w_b)
                if dist < threshold:
                    close_pairs.append((i, j))
                    passing_detected = True
    
    return passing_detected, close_pairs


def is_looking_down(keypoints):
    """Check if person is looking down at cheat material"""
    try:
        nose = keypoints[0]
        left_shoulder = keypoints[5]
        right_shoulder = keypoints[6]
        
        if all(kp[2] > 0.5 for kp in [nose, left_shoulder, right_shoulder]):
            # Calculate shoulder center Y position
            shoulder_center_y = (left_shoulder[1] + right_shoulder[1]) / 2
            
            # If nose is significantly BELOW shoulders, person is looking down
            # Normal: nose is above shoulders
            # Looking down: nose approaches or goes below shoulder level
            if nose[1] > shoulder_center_y - 20:  # Small threshold for head tilt
                return True
        
        return False
    except:
        return False


def is_peeking_sideways(keypoints):
    """Check if person is peeking at neighbor (head turned to side but not back)"""
    try:
        nose = keypoints[0]
        left_eye = keypoints[1]
        right_eye = keypoints[2]
        left_shoulder = keypoints[5]
        right_shoulder = keypoints[6]
        
        if all(kp[2] > 0.5 for kp in [nose, left_shoulder, right_shoulder]):
            # Calculate shoulder center X position
            shoulder_center_x = (left_shoulder[0] + right_shoulder[0]) / 2
            shoulder_width = abs(right_shoulder[0] - left_shoulder[0])
            
            if shoulder_width > 0:
                # Check horizontal offset of nose from shoulder center
                nose_offset = abs(nose[0] - shoulder_center_x)
                offset_ratio = nose_offset / shoulder_width
                
                # Peeking: nose offset 0.3-0.6 (moderate turn, not full back turn)
                # This catches side glances at neighbor's paper
                if 0.25 < offset_ratio < 0.7:
                    # Also check eye visibility to distinguish from turning back
                    if left_eye[2] > 0.3 and right_eye[2] > 0.3:
                        return True
        
        return False
    except:
        return False


def is_talking(keypoints, prev_keypoints=None):
    """Check if person is talking (simple mouth area change detection)"""
    try:
        # Approximate mouth area using nose and ear positions
        nose = keypoints[0]
        left_ear = keypoints[3]
        right_ear = keypoints[4]
        
        if all(kp[2] > 0.5 for kp in [nose, left_ear, right_ear]):
            # Estimate mouth region below nose
            # Use distance between ears as reference for face width
            ear_distance = np.linalg.norm(np.array(left_ear[:2]) - np.array(right_ear[:2]))
            
            # If we have previous keypoints, check for movement in lower face region
            if prev_keypoints is not None:
                prev_nose = prev_keypoints[0]
                if prev_nose[2] > 0.5:
                    # Detect vertical movement of nose (jaw movement indicator)
                    nose_movement = abs(nose[1] - prev_nose[1])
                    
                    # Normalize by ear distance (face size)
                    if ear_distance > 0:
                        movement_ratio = nose_movement / ear_distance
                        
                        # Talking causes small but consistent nose/jaw movements
                        if movement_ratio > 0.02:  # 2% of face width
                            return True
        
        return False
    except:
        return False


def detect_suspicious_behavior(keypoints_history):
    """Check for suspicious behavior (rapid head movements, fidgeting)"""
    try:
        if len(keypoints_history) < 10:  # Need at least 10 frames
            return False
        
        # Analyze last 10 frames for rapid movements
        recent_keypoints = keypoints_history[-10:]
        
        # Track nose positions (head movement)
        nose_positions = []
        for kp in recent_keypoints:
            if kp is not None and kp[0][2] > 0.5:  # Nose visible
                nose_positions.append(kp[0][:2])
        
        if len(nose_positions) < 8:
            return False
        
        # Calculate movement variance
        nose_array = np.array(nose_positions)
        movement_variance = np.var(nose_array, axis=0).sum()
        
        # High variance indicates rapid, erratic movements (suspicious)
        # Threshold based on typical stable head movement
        if movement_variance > 50:  # Adjust based on testing
            return True
        
        return False
    except:
        return False




def stream_process_video(video_path, lecture_hall_id):
    """Process video with ffmpeg pre-transcode + threaded pipeline for 25fps streaming.
    
    Architecture:
    1. ffmpeg pre-transcodes high-res video to 720p (~3-5 seconds for 8K)
    2. Background Thread: Reads 720p frames lightning fast, runs YOLO with FP16
    3. Main Generator: Yields ALL annotated frames at 25fps from queue
    
    Key: 8K decode was the bottleneck (100ms/frame). 720p decode = 5ms/frame = 20x faster.
    """
    import threading
    from queue import Queue, Empty
    import time as time_module
    import subprocess

    print(f"\n{'='*60}")
    print(f"🎬 ULTRA-FAST VIDEO PROCESSOR (ffmpeg + Threaded Pipeline)")
    print(f"📁 Video: {video_path}")
    print(f"🏛️ Lecture Hall ID: {lecture_hall_id}")
    print(f"🔧 Device: {DEVICE}")
    print(f"🚀 Mode: ffmpeg transcode → GPU processing → 25fps streaming")
    print(f"{'='*60}\n")

    # Load models (cached after first call - instant on subsequent uploads)
    pose_model, mobile_model, use_half_precision = get_cached_models()

    # ===== STEP 1: Probe video and ffmpeg pre-transcode if needed =====
    cap_probe = cv2.VideoCapture(video_path)
    if not cap_probe.isOpened():
        print(f"❌ Error: Cannot open video {video_path}")
        return

    fps = int(cap_probe.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap_probe.get(cv2.CAP_PROP_FRAME_COUNT))
    original_width = int(cap_probe.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap_probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0
    cap_probe.release()

    print(f"📹 Original: {original_width}x{original_height}, {fps} FPS, {total_frames} frames, {duration:.1f}s")

    MAX_WIDTH = 1280
    MAX_HEIGHT = 720
    actual_video_path = video_path  # May change if we transcode
    transcode_path = None

    if original_width > MAX_WIDTH or original_height > MAX_HEIGHT:
        # Calculate target size maintaining aspect ratio
        width_scale = MAX_WIDTH / original_width
        height_scale = MAX_HEIGHT / original_height
        scale = min(width_scale, height_scale)
        target_w = int(original_width * scale)
        target_h = int(original_height * scale)
        # Ensure even dimensions (required by most codecs)
        target_w = target_w if target_w % 2 == 0 else target_w - 1
        target_h = target_h if target_h % 2 == 0 else target_h - 1

        print(f"\n🔄 Pre-transcoding {original_width}x{original_height} → {target_w}x{target_h} with ffmpeg...")
        transcode_start = time_module.time()

        # Transcode to 720p with ffmpeg (MUCH faster than OpenCV decode + resize per frame)
        ml_dir = os.path.dirname(__file__)
        transcode_path = os.path.join(ml_dir, "temp_transcode_720p.mp4")

        ffmpeg_cmd = [
            'ffmpeg', '-y',             # Overwrite output
            '-i', video_path,           # Input
            '-vf', f'scale={target_w}:{target_h}',  # Resize
            '-c:v', 'libx264',          # Fast H.264 encoding
            '-preset', 'ultrafast',     # Fastest encoding preset
            '-crf', '18',               # High quality
            '-an',                      # No audio
            '-loglevel', 'error',       # Quiet
            transcode_path
        ]

        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
            transcode_elapsed = time_module.time() - transcode_start

            if result.returncode == 0 and os.path.exists(transcode_path):
                actual_video_path = transcode_path
                print(f"✅ Transcode complete in {transcode_elapsed:.1f}s → {transcode_path}")
                frame_width = target_w
                frame_height = target_h
            else:
                print(f"⚠️ ffmpeg failed, falling back to OpenCV resize")
                if result.stderr:
                    print(f"   Error: {result.stderr[:200]}")
                frame_width = target_w
                frame_height = target_h
        except Exception as e:
            print(f"⚠️ ffmpeg not available ({e}), falling back to OpenCV resize")
            frame_width = target_w
            frame_height = target_h
    else:
        frame_width = original_width
        frame_height = original_height
        print(f"📹 Video is already ≤720p, no transcode needed")

    # Open the (possibly transcoded) video
    cap = cv2.VideoCapture(actual_video_path)
    if not cap.isOpened():
        print(f"❌ Error: Cannot open processed video")
        return

    # Re-read properties from actual file (may differ slightly after transcode)
    actual_fps = int(cap.get(cv2.CAP_PROP_FPS)) or fps
    actual_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or total_frames
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    needs_resize = (actual_w != frame_width or actual_h != frame_height)

    if needs_resize:
        print(f"📹 Will resize {actual_w}x{actual_h} → {frame_width}x{frame_height} per frame (fallback)")
    else:
        print(f"📹 Processing at {actual_w}x{actual_h} (no per-frame resize needed)")

    # ===== THREADED PIPELINE SETTINGS =====
    FRAME_SKIP = 3        # Every 3rd frame gets YOLO
    POSE_IMGSZ = 416      # Fast pose inference
    MOBILE_IMGSZ = 640    # Higher res for small phone objects
    JPEG_QUALITY = 55
    STREAM_FPS = 25       # Target streaming framerate
    GRACE_PERIOD = 30     # ~3 seconds of grace
    MOBILE_CONF = 0.25    # Catch phones on desks

    print(f"\n⚙️ Ultra-Fast Pipeline Settings:")
    print(f"   Frame skip: Every {FRAME_SKIP}rd frame")
    print(f"   Pose imgsz: {POSE_IMGSZ}px, Mobile imgsz: {MOBILE_IMGSZ}px")
    print(f"   Stream: ALL frames at {STREAM_FPS}fps (persistent annotations)")
    print(f"   Grace period: {GRACE_PERIOD} processed frames (~3 seconds)")
    print(f"   Mobile confidence: {MOBILE_CONF}")
    print(f"   GPU: {'FP16 half-precision' if use_half_precision else 'FP32'}")
    print(f"   Expected: ~{actual_total / STREAM_FPS:.0f}s streaming")

    # COCO skeleton connections
    skeleton_connections = [
        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
        (5, 11), (6, 12), (11, 12),
        (11, 13), (13, 15), (12, 14), (14, 16),
        (0, 1), (0, 2), (1, 3), (2, 4)
    ]

    # Thread-safe queue for frame transfer
    frame_queue = Queue(maxsize=600)
    processing_complete = threading.Event()
    processing_error = [None]

    print(f"\n▶️ Starting threaded pipeline...\n")
    pipeline_start = time_module.time()

    def processing_worker():
        """Process entire video at MAX GPU speed in background thread.
        
        All detection state is LOCAL to this thread - no shared mutable state.
        Only communicates with main thread via thread-safe Queue and Event.
        """
        try:
            worker_start = time_module.time()

            # ===== ALL STATE IS LOCAL TO THIS THREAD =====
            frame_count = 0
            frames_processed = 0

            detections_count = {
                'leaning': 0, 'mobile': 0, 'turning': 0, 'passing': 0, 'hand_raise': 0
            }

            # Frame counters for threshold detection
            leaning_frames = 0
            passing_frames = 0
            mobile_frames = 0
            turning_frames = 0
            hand_raise_frames = 0

            # Max frame counters for debugging
            max_leaning_frames = 0
            max_passing_frames = 0
            max_mobile_frames = 0
            max_turning_frames = 0
            max_hand_raise_frames = 0

            # Grace period counters
            leaning_grace_frames = 0
            passing_grace_frames = 0
            mobile_grace_frames = 0
            turning_grace_frames = 0
            hand_raise_grace_frames = 0

            # Recording states
            leaning_in_progress = False
            leaning_recording = False
            leaning_video = None

            passing_in_progress = False
            passing_recording = False
            passing_video = None

            mobile_in_progress = False
            mobile_recording = False
            mobile_video = None

            turning_in_progress = False
            turning_recording = False
            turning_video = None

            hand_raise_in_progress = False
            hand_raise_recording = False
            hand_raise_video = None

            # Temporary video files
            ml_dir = os.path.dirname(__file__)
            temp_leaning = os.path.join(ml_dir, "temp_leaning.mp4")
            temp_passing = os.path.join(ml_dir, "temp_passing.mp4")
            temp_mobile = os.path.join(ml_dir, "temp_mobile.mp4")
            temp_turning = os.path.join(ml_dir, "temp_turning.mp4")
            temp_hand_raise = os.path.join(ml_dir, "temp_hand_raise.mp4")

            # Circular buffer for 1.5s pre-roll
            buffer_size = int(1.5 * actual_fps)
            frame_buffer = deque(maxlen=buffer_size)
            print(f"💾 Frame Buffer: {buffer_size} frames (1.5 seconds pre-roll)")

            # ===== PROBABILITY SCORING TRACKERS =====
            # Total detection frames per recording session (for density calculation)
            leaning_detection_total = 0
            mobile_detection_total = 0
            passing_detection_total = 0
            turning_detection_total = 0
            hand_raise_detection_total = 0

            # Total recording frames per session
            leaning_recording_total = 0
            mobile_recording_total = 0
            passing_recording_total = 0
            turning_recording_total = 0
            hand_raise_recording_total = 0

            # Confidence accumulators (sum + count for averaging)
            mobile_conf_sum = 0.0
            mobile_conf_count = 0
            leaning_conf_sum = 0.0
            leaning_conf_count = 0
            passing_conf_sum = 0.0
            passing_conf_count = 0
            turning_conf_sum = 0.0
            turning_conf_count = 0
            hand_raise_conf_sum = 0.0
            hand_raise_conf_count = 0

            # Persistent annotation state (carried between YOLO runs for smooth visuals)
            last_keypoints_list = []
            last_mobile_boxes = []

            # ===== MAIN PROCESSING LOOP =====
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1

                # Resize only if ffmpeg transcode failed (fallback)
                if needs_resize:
                    frame = cv2.resize(frame, (frame_width, frame_height))

                # Add to circular buffer (for pre-roll recording)
                frame_buffer.append(frame.copy())

                # Write ALL frames to ongoing recordings (smooth 30fps playback)
                if leaning_in_progress and leaning_recording and leaning_video:
                    leaning_video.write(frame)
                if mobile_in_progress and mobile_recording and mobile_video:
                    mobile_video.write(frame)
                if passing_in_progress and passing_recording and passing_video:
                    passing_video.write(frame)
                if turning_in_progress and turning_recording and turning_video:
                    turning_video.write(frame)
                if hand_raise_in_progress and hand_raise_recording and hand_raise_video:
                    hand_raise_video.write(frame)

                # Create display frame for streaming
                display_frame = frame.copy()

                # ===== YOLO FRAME: Full AI detection =====
                if frame_count % FRAME_SKIP == 0:
                    frames_processed += 1

                    # Reset detection flags
                    leaning_this_frame = False
                    passing_this_frame = False
                    mobile_this_frame = False
                    turning_this_frame = False
                    hand_raise_this_frame = False

                    # --- Pose Detection (imgsz=416 for speed) ---
                    pose_results = pose_model(frame, verbose=False, half=use_half_precision, imgsz=POSE_IMGSZ)

                    last_keypoints_list = []
                    wrist_positions = []  # For multi-person passing detection
                    all_person_keypoints = []  # Raw xy keypoints per person

                    for result in pose_results:
                        if result.keypoints is not None and len(result.keypoints) > 0:
                            # Also get xy-only keypoints for passing detection
                            kpts_xy = result.keypoints.xy.cpu().numpy() if hasattr(result.keypoints, 'xy') else None

                            for p_idx, keypoints in enumerate(result.keypoints.data):
                                keypoints_np = keypoints.cpu().numpy()
                                last_keypoints_list.append(keypoints_np)

                                # Collect wrists for multi-person passing detection
                                if len(keypoints_np) >= 11:
                                    lw = keypoints_np[9]  # left wrist
                                    rw = keypoints_np[10]  # right wrist
                                    if lw[2] > 0.3 and rw[2] > 0.3:
                                        wrist_positions.append([lw[:2], rw[:2]])
                                        all_person_keypoints.append(keypoints_np)

                                # Draw skeleton keypoints
                                for i, (x, y, conf) in enumerate(keypoints_np):
                                    if conf > 0.5:
                                        cv2.circle(display_frame, (int(x), int(y)), 5, (0, 255, 0), -1)

                                # Draw skeleton connections
                                for start_idx, end_idx in skeleton_connections:
                                    if start_idx < len(keypoints_np) and end_idx < len(keypoints_np):
                                        sp = keypoints_np[start_idx]
                                        ep = keypoints_np[end_idx]
                                        if sp[2] > 0.5 and ep[2] > 0.5:
                                            cv2.line(display_frame,
                                                    (int(sp[0]), int(sp[1])),
                                                    (int(ep[0]), int(ep[1])),
                                                    (0, 255, 0), 2)

                                # Check turning back FIRST (priority over leaning)
                                if is_turning_back(keypoints_np):
                                    turning_this_frame = True
                                elif is_leaning(keypoints_np, frame_width, frame_height):
                                    # Only flag leaning if NOT turning back
                                    leaning_this_frame = True
                                if is_hand_raised(keypoints_np):
                                    hand_raise_this_frame = True

                    # Multi-person passing paper detection (requires 2+ people)
                    passing_detected, close_pairs = detect_passing_paper(wrist_positions, all_person_keypoints)
                    if passing_detected:
                        passing_this_frame = True

                    # --- Mobile Detection (imgsz=640, higher res for small phone objects) ---
                    mobile_results = mobile_model(frame, verbose=False, half=use_half_precision, imgsz=MOBILE_IMGSZ)
                    last_mobile_boxes = []
                    for result in mobile_results:
                        if result.boxes is not None:
                            for box in result.boxes:
                                class_id = int(box.cls[0])
                                if class_id == MOBILE_CLASS_ID and box.conf[0] > MOBILE_CONF:
                                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                                    conf_val = float(box.conf[0])
                                    
                                    # Smart filter: distinguish phones from calculators
                                    is_phone, reason = is_likely_phone(x1, y1, x2, y2, conf_val, frame_width, frame_height)
                                    if is_phone:
                                        mobile_this_frame = True
                                        last_mobile_boxes.append((x1, y1, x2, y2, conf_val))
                                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), COLOR_MOBILE, 3)
                                        cv2.putText(display_frame, f"Mobile {conf_val:.2f}",
                                                   (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_MOBILE, 2)
                                    else:
                                        # Draw filtered detection in gray (visible but not flagged)
                                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (128, 128, 128), 1)
                                        cv2.putText(display_frame, f"Filtered: {reason[:30]}",
                                                   (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
                                        if frame_count % 30 == 0:  # Log every 30th frame to avoid spam
                                            print(f"\U0001f6ab Mobile filtered: {reason}")

                    # Update frame counters
                    leaning_frames = leaning_frames + 1 if leaning_this_frame else 0
                    passing_frames = passing_frames + 1 if passing_this_frame else 0
                    mobile_frames = mobile_frames + 1 if mobile_this_frame else 0
                    turning_frames = turning_frames + 1 if turning_this_frame else 0
                    hand_raise_frames = hand_raise_frames + 1 if hand_raise_this_frame else 0

                    # Update max counters
                    max_leaning_frames = max(max_leaning_frames, leaning_frames)
                    max_passing_frames = max(max_passing_frames, passing_frames)
                    max_mobile_frames = max(max_mobile_frames, mobile_frames)
                    max_turning_frames = max(max_turning_frames, turning_frames)
                    max_hand_raise_frames = max(max_hand_raise_frames, hand_raise_frames)

                    # ===== PROBABILITY TRACKING: Count detection/recording frames =====
                    # Track frames while recording is active (for density calculation)
                    if leaning_in_progress:
                        leaning_recording_total += 1
                        if leaning_this_frame:
                            leaning_detection_total += 1
                            # Track avg keypoint confidence for leaning
                            if last_keypoints_list:
                                kp = last_keypoints_list[0]
                                avg_kp_conf = float(np.mean([kp[i][2] for i in [0, 5, 6, 11, 12] if i < len(kp) and kp[i][2] > 0]))
                                leaning_conf_sum += avg_kp_conf
                                leaning_conf_count += 1
                    
                    if mobile_in_progress:
                        mobile_recording_total += 1
                        if mobile_this_frame:
                            mobile_detection_total += 1
                            # Track avg YOLO confidence for mobile
                            if last_mobile_boxes:
                                avg_mob_conf = float(np.mean([b[4] for b in last_mobile_boxes]))
                                mobile_conf_sum += avg_mob_conf
                                mobile_conf_count += 1
                    
                    if passing_in_progress:
                        passing_recording_total += 1
                        if passing_this_frame:
                            passing_detection_total += 1
                            if last_keypoints_list and len(last_keypoints_list) >= 2:
                                avg_kp_conf = float(np.mean([kp[i][2] for kp in last_keypoints_list[:2] for i in [9, 10] if i < len(kp) and kp[i][2] > 0]))
                                passing_conf_sum += avg_kp_conf
                                passing_conf_count += 1
                    
                    if turning_in_progress:
                        turning_recording_total += 1
                        if turning_this_frame:
                            turning_detection_total += 1
                            if last_keypoints_list:
                                kp = last_keypoints_list[0]
                                avg_kp_conf = float(np.mean([kp[i][2] for i in [0, 1, 2, 5, 6] if i < len(kp) and kp[i][2] > 0]))
                                turning_conf_sum += avg_kp_conf
                                turning_conf_count += 1
                    
                    if hand_raise_in_progress:
                        hand_raise_recording_total += 1
                        if hand_raise_this_frame:
                            hand_raise_detection_total += 1
                            if last_keypoints_list:
                                kp = last_keypoints_list[0]
                                avg_kp_conf = float(np.mean([kp[i][2] for i in [5, 6, 7, 8, 9, 10] if i < len(kp) and kp[i][2] > 0]))
                                hand_raise_conf_sum += avg_kp_conf
                                hand_raise_conf_count += 1

                    # ===== RECORDING LOGIC WITH GRACE PERIOD =====

                    # LEANING
                    if leaning_frames >= LEANING_THRESHOLD:
                        leaning_grace_frames = 0
                        if not leaning_in_progress:
                            leaning_in_progress = True
                            leaning_recording = True
                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            leaning_video = cv2.VideoWriter(temp_leaning, fourcc, fps, (frame_width, frame_height))
                            print(f"\n▶️ LEANING detected! Writing {len(frame_buffer)} buffered frames (1.5s pre-roll)...")
                            for bf in frame_buffer:
                                leaning_video.write(bf)
                            print(f"   ✅ Buffer written, continuing live recording...")
                    else:
                        if leaning_in_progress:
                            leaning_grace_frames += 1
                            if leaning_grace_frames >= GRACE_PERIOD:
                                leaning_in_progress = False
                                if leaning_recording and leaning_video:
                                    leaning_video.release()
                                    leaning_video = None
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    final_filename = f"leaning_{timestamp}.mp4"
                                    final_path = os.path.join(MEDIA_DIR, final_filename)
                                    if os.path.exists(temp_leaning):
                                        print(f"\n  💾 Grace period ended - saving leaning clip")
                                        shutil.copy(temp_leaning, final_path)
                                        save_video_to_database(
                                            LEANING_ACTION, final_path, lecture_hall_id,
                                            detection_frames=leaning_detection_total,
                                            total_recording_frames=leaning_recording_total,
                                            avg_confidence=leaning_conf_sum / leaning_conf_count if leaning_conf_count > 0 else 0,
                                            fps=actual_fps
                                        )
                                        detections_count['leaning'] += 1
                                    leaning_recording = False
                                    leaning_detection_total = 0
                                    leaning_recording_total = 0
                                    leaning_conf_sum = 0.0
                                    leaning_conf_count = 0
                                leaning_grace_frames = 0

                    # MOBILE
                    if mobile_frames >= MOBILE_THRESHOLD:
                        mobile_grace_frames = 0
                        if not mobile_in_progress:
                            mobile_in_progress = True
                            mobile_recording = True
                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            mobile_video = cv2.VideoWriter(temp_mobile, fourcc, fps, (frame_width, frame_height))
                            print(f"\n▶️ MOBILE detected! Writing {len(frame_buffer)} buffered frames (1.5s pre-roll)...")
                            for bf in frame_buffer:
                                mobile_video.write(bf)
                            print(f"   ✅ Buffer written, continuing live recording...")
                    else:
                        if mobile_in_progress:
                            mobile_grace_frames += 1
                            if mobile_grace_frames >= GRACE_PERIOD:
                                mobile_in_progress = False
                                if mobile_recording and mobile_video:
                                    mobile_video.release()
                                    mobile_video = None
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    final_filename = f"mobile_{timestamp}.mp4"
                                    final_path = os.path.join(MEDIA_DIR, final_filename)
                                    if os.path.exists(temp_mobile):
                                        print(f"\n  💾 Grace period ended - saving mobile clip")
                                        shutil.copy(temp_mobile, final_path)
                                        save_video_to_database(
                                            ACTION_MOBILE, final_path, lecture_hall_id,
                                            detection_frames=mobile_detection_total,
                                            total_recording_frames=mobile_recording_total,
                                            avg_confidence=mobile_conf_sum / mobile_conf_count if mobile_conf_count > 0 else 0,
                                            fps=actual_fps
                                        )
                                        detections_count['mobile'] += 1
                                    mobile_recording = False
                                    mobile_detection_total = 0
                                    mobile_recording_total = 0
                                    mobile_conf_sum = 0.0
                                    mobile_conf_count = 0
                                mobile_grace_frames = 0

                    # PASSING PAPER
                    if passing_frames >= PASSING_THRESHOLD:
                        passing_grace_frames = 0
                        if not passing_in_progress:
                            passing_in_progress = True
                            passing_recording = True
                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            passing_video = cv2.VideoWriter(temp_passing, fourcc, fps, (frame_width, frame_height))
                            print(f"\n▶️ PASSING PAPER detected! Writing {len(frame_buffer)} buffered frames (1.5s pre-roll)...")
                            for bf in frame_buffer:
                                passing_video.write(bf)
                            print(f"   ✅ Buffer written, continuing live recording...")
                    else:
                        if passing_in_progress:
                            passing_grace_frames += 1
                            if passing_grace_frames >= GRACE_PERIOD:
                                passing_in_progress = False
                                if passing_recording and passing_video:
                                    passing_video.release()
                                    passing_video = None
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    final_filename = f"passing_{timestamp}.mp4"
                                    final_path = os.path.join(MEDIA_DIR, final_filename)
                                    if os.path.exists(temp_passing):
                                        print(f"\n  💾 Grace period ended - saving passing paper clip")
                                        shutil.copy(temp_passing, final_path)
                                        save_video_to_database(
                                            PASSING_ACTION, final_path, lecture_hall_id,
                                            detection_frames=passing_detection_total,
                                            total_recording_frames=passing_recording_total,
                                            avg_confidence=passing_conf_sum / passing_conf_count if passing_conf_count > 0 else 0,
                                            fps=actual_fps
                                        )
                                        detections_count['passing'] += 1
                                    passing_recording = False
                                    passing_detection_total = 0
                                    passing_recording_total = 0
                                    passing_conf_sum = 0.0
                                    passing_conf_count = 0
                                passing_grace_frames = 0

                    # TURNING BACK
                    if turning_frames >= TURNING_THRESHOLD:
                        turning_grace_frames = 0
                        if not turning_in_progress:
                            turning_in_progress = True
                            turning_recording = True
                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            turning_video = cv2.VideoWriter(temp_turning, fourcc, fps, (frame_width, frame_height))
                            print(f"\n▶️ TURNING BACK detected! Writing {len(frame_buffer)} buffered frames (1.5s pre-roll)...")
                            for bf in frame_buffer:
                                turning_video.write(bf)
                            print(f"   ✅ Buffer written, continuing live recording...")
                    else:
                        if turning_in_progress:
                            turning_grace_frames += 1
                            if turning_grace_frames >= GRACE_PERIOD:
                                turning_in_progress = False
                                if turning_recording and turning_video:
                                    turning_video.release()
                                    turning_video = None
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    final_filename = f"turning_{timestamp}.mp4"
                                    final_path = os.path.join(MEDIA_DIR, final_filename)
                                    if os.path.exists(temp_turning):
                                        print(f"\n  💾 Grace period ended - saving turning back clip")
                                        shutil.copy(temp_turning, final_path)
                                        save_video_to_database(
                                            TURNING_ACTION, final_path, lecture_hall_id,
                                            detection_frames=turning_detection_total,
                                            total_recording_frames=turning_recording_total,
                                            avg_confidence=turning_conf_sum / turning_conf_count if turning_conf_count > 0 else 0,
                                            fps=actual_fps
                                        )
                                        detections_count['turning'] += 1
                                    turning_recording = False
                                    turning_detection_total = 0
                                    turning_recording_total = 0
                                    turning_conf_sum = 0.0
                                    turning_conf_count = 0
                                turning_grace_frames = 0

                    # HAND RAISE
                    if hand_raise_frames >= HAND_RAISE_THRESHOLD:
                        hand_raise_grace_frames = 0
                        if not hand_raise_in_progress:
                            hand_raise_in_progress = True
                            hand_raise_recording = True
                            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                            hand_raise_video = cv2.VideoWriter(temp_hand_raise, fourcc, fps, (frame_width, frame_height))
                            print(f"\n▶️ HAND RAISED detected! Writing {len(frame_buffer)} buffered frames (1.5s pre-roll)...")
                            for bf in frame_buffer:
                                hand_raise_video.write(bf)
                            print(f"   ✅ Buffer written, continuing live recording...")
                    else:
                        if hand_raise_in_progress:
                            hand_raise_grace_frames += 1
                            if hand_raise_grace_frames >= GRACE_PERIOD:
                                hand_raise_in_progress = False
                                if hand_raise_recording and hand_raise_video:
                                    hand_raise_video.release()
                                    hand_raise_video = None
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    final_filename = f"hand_raise_{timestamp}.mp4"
                                    final_path = os.path.join(MEDIA_DIR, final_filename)
                                    if os.path.exists(temp_hand_raise):
                                        print(f"\n  💾 Grace period ended - saving hand raise clip")
                                        shutil.copy(temp_hand_raise, final_path)
                                        save_video_to_database(
                                            HAND_RAISE_ACTION, final_path, lecture_hall_id,
                                            detection_frames=hand_raise_detection_total,
                                            total_recording_frames=hand_raise_recording_total,
                                            avg_confidence=hand_raise_conf_sum / hand_raise_conf_count if hand_raise_conf_count > 0 else 0,
                                            fps=actual_fps
                                        )
                                        detections_count['hand_raise'] += 1
                                    hand_raise_recording = False
                                    hand_raise_detection_total = 0
                                    hand_raise_recording_total = 0
                                    hand_raise_conf_sum = 0.0
                                    hand_raise_conf_count = 0
                                hand_raise_grace_frames = 0

                    # ===== YOLO FRAME: Add overlays, encode and queue for streaming =====
                    y_offset = 50
                    if leaning_frames > 0:
                        cv2.putText(display_frame, f"LEANING! ({leaning_frames}/{LEANING_THRESHOLD})",
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_LEANING, 3)
                        y_offset += 40
                    if mobile_frames > 0:
                        cv2.putText(display_frame, f"MOBILE! ({mobile_frames}/{MOBILE_THRESHOLD})",
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_MOBILE, 3)
                        y_offset += 40
                    if turning_frames > 0:
                        cv2.putText(display_frame, f"TURNING BACK! ({turning_frames}/{TURNING_THRESHOLD})",
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_TURNING, 3)
                        y_offset += 40
                    if passing_frames > 0:
                        cv2.putText(display_frame, f"PASSING PAPER! ({passing_frames}/{PASSING_THRESHOLD})",
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_PASSING, 3)
                        y_offset += 40
                    if hand_raise_frames > 0:
                        cv2.putText(display_frame, f"HAND RAISED! ({hand_raise_frames}/{HAND_RAISE_THRESHOLD})",
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_HAND_RAISE, 3)
                        y_offset += 40

                    # Progress bar
                    progress = frame_count / total_frames if total_frames > 0 else 0
                    if total_frames - frame_count <= 5:
                        progress = 1.0
                    bar_width = int(progress * frame_width)
                    cv2.rectangle(display_frame, (0, frame_height - 20), (bar_width, frame_height), (0, 255, 0), -1)
                    cv2.putText(display_frame, f"Processing: {progress*100:.1f}% | Frame: {frame_count}/{total_frames}",
                               (10, frame_height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                    ret_enc, enc_buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                    if ret_enc:
                        try:
                            frame_queue.put(enc_buffer.tobytes(), timeout=10)
                        except:
                            pass  # Queue full, skip frame

                else:
                    # ===== NON-YOLO FRAME: Draw persistent annotations from last YOLO run =====
                    # This gives smooth visual feedback at full frame rate
                    for keypoints_np in last_keypoints_list:
                        for i, (x, y, conf) in enumerate(keypoints_np):
                            if conf > 0.5:
                                cv2.circle(display_frame, (int(x), int(y)), 5, (0, 255, 0), -1)
                        for start_idx, end_idx in skeleton_connections:
                            if start_idx < len(keypoints_np) and end_idx < len(keypoints_np):
                                sp = keypoints_np[start_idx]
                                ep = keypoints_np[end_idx]
                                if sp[2] > 0.5 and ep[2] > 0.5:
                                    cv2.line(display_frame,
                                            (int(sp[0]), int(sp[1])),
                                            (int(ep[0]), int(ep[1])),
                                            (0, 255, 0), 2)

                    for (x1, y1, x2, y2, conf_val) in last_mobile_boxes:
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), COLOR_MOBILE, 3)
                        cv2.putText(display_frame, f"Mobile {conf_val:.2f}",
                                   (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_MOBILE, 2)

                    # Detection text overlays
                    y_offset = 50
                    if leaning_frames > 0:
                        cv2.putText(display_frame, f"LEANING! ({leaning_frames}/{LEANING_THRESHOLD})",
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_LEANING, 3)
                        y_offset += 40
                    if mobile_frames > 0:
                        cv2.putText(display_frame, f"MOBILE! ({mobile_frames}/{MOBILE_THRESHOLD})",
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_MOBILE, 3)
                        y_offset += 40
                    if turning_frames > 0:
                        cv2.putText(display_frame, f"TURNING BACK! ({turning_frames}/{TURNING_THRESHOLD})",
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_TURNING, 3)
                        y_offset += 40
                    if passing_frames > 0:
                        cv2.putText(display_frame, f"PASSING PAPER! ({passing_frames}/{PASSING_THRESHOLD})",
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_PASSING, 3)
                        y_offset += 40
                    if hand_raise_frames > 0:
                        cv2.putText(display_frame, f"HAND RAISED! ({hand_raise_frames}/{HAND_RAISE_THRESHOLD})",
                                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLOR_HAND_RAISE, 3)
                        y_offset += 40

                    # Progress bar
                    progress = frame_count / total_frames if total_frames > 0 else 0
                    if total_frames - frame_count <= 5:
                        progress = 1.0
                    bar_width = int(progress * frame_width)
                    cv2.rectangle(display_frame, (0, frame_height - 20), (bar_width, frame_height), (0, 255, 0), -1)
                    cv2.putText(display_frame, f"Processing: {progress*100:.1f}% | Frame: {frame_count}/{total_frames}",
                               (10, frame_height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                    ret_enc, enc_buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                    if ret_enc:
                        try:
                            frame_queue.put(enc_buffer.tobytes(), timeout=10)
                        except:
                            pass

            # ===== END OF VIDEO - Save any ongoing recordings =====
            print(f"\n{'='*60}")
            print(f"VIDEO ENDED - Saving any ongoing recordings...")
            print(f"{'='*60}")

            worker_elapsed = time_module.time() - worker_start
            print(f"⚡ GPU processing completed in {worker_elapsed:.1f} seconds")

            # Save incomplete leaning recording
            if leaning_in_progress and leaning_recording and leaning_video:
                print(f"\n💾 Saving incomplete LEANING recording...")
                leaning_video.release()
                leaning_video = None
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                final_filename = f"leaning_{timestamp}.mp4"
                final_path = os.path.join(MEDIA_DIR, final_filename)
                if os.path.exists(temp_leaning):
                    shutil.copy(temp_leaning, final_path)
                    save_video_to_database(
                        LEANING_ACTION, final_path, lecture_hall_id,
                        detection_frames=leaning_detection_total,
                        total_recording_frames=leaning_recording_total,
                        avg_confidence=leaning_conf_sum / leaning_conf_count if leaning_conf_count > 0 else 0,
                        fps=actual_fps
                    )
                    detections_count['leaning'] += 1

            # Save incomplete mobile recording
            if mobile_in_progress and mobile_recording and mobile_video:
                print(f"\n💾 Saving incomplete MOBILE recording...")
                mobile_video.release()
                mobile_video = None
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                final_filename = f"mobile_{timestamp}.mp4"
                final_path = os.path.join(MEDIA_DIR, final_filename)
                if os.path.exists(temp_mobile):
                    shutil.copy(temp_mobile, final_path)
                    save_video_to_database(
                        ACTION_MOBILE, final_path, lecture_hall_id,
                        detection_frames=mobile_detection_total,
                        total_recording_frames=mobile_recording_total,
                        avg_confidence=mobile_conf_sum / mobile_conf_count if mobile_conf_count > 0 else 0,
                        fps=actual_fps
                    )
                    detections_count['mobile'] += 1

            # Save incomplete passing paper recording
            if passing_in_progress and passing_recording and passing_video:
                print(f"\n💾 Saving incomplete PASSING PAPER recording...")
                passing_video.release()
                passing_video = None
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                final_filename = f"passing_{timestamp}.mp4"
                final_path = os.path.join(MEDIA_DIR, final_filename)
                if os.path.exists(temp_passing):
                    shutil.copy(temp_passing, final_path)
                    save_video_to_database(
                        PASSING_ACTION, final_path, lecture_hall_id,
                        detection_frames=passing_detection_total,
                        total_recording_frames=passing_recording_total,
                        avg_confidence=passing_conf_sum / passing_conf_count if passing_conf_count > 0 else 0,
                        fps=actual_fps
                    )
                    detections_count['passing'] += 1

            # Save incomplete turning back recording
            if turning_in_progress and turning_recording and turning_video:
                print(f"\n💾 Saving incomplete TURNING BACK recording...")
                turning_video.release()
                turning_video = None
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                final_filename = f"turning_{timestamp}.mp4"
                final_path = os.path.join(MEDIA_DIR, final_filename)
                if os.path.exists(temp_turning):
                    shutil.copy(temp_turning, final_path)
                    save_video_to_database(
                        TURNING_ACTION, final_path, lecture_hall_id,
                        detection_frames=turning_detection_total,
                        total_recording_frames=turning_recording_total,
                        avg_confidence=turning_conf_sum / turning_conf_count if turning_conf_count > 0 else 0,
                        fps=actual_fps
                    )
                    detections_count['turning'] += 1

            # Save incomplete hand raise recording
            if hand_raise_in_progress and hand_raise_recording and hand_raise_video:
                print(f"\n💾 Saving incomplete HAND RAISE recording...")
                hand_raise_video.release()
                hand_raise_video = None
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                final_filename = f"hand_raise_{timestamp}.mp4"
                final_path = os.path.join(MEDIA_DIR, final_filename)
                if os.path.exists(temp_hand_raise):
                    shutil.copy(temp_hand_raise, final_path)
                    save_video_to_database(
                        HAND_RAISE_ACTION, final_path, lecture_hall_id,
                        detection_frames=hand_raise_detection_total,
                        total_recording_frames=hand_raise_recording_total,
                        avg_confidence=hand_raise_conf_sum / hand_raise_conf_count if hand_raise_conf_count > 0 else 0,
                        fps=actual_fps
                    )
                    detections_count['hand_raise'] += 1

            # Cleanup video capture and writers
            cap.release()
            for vw in [leaning_video, mobile_video, passing_video, turning_video, hand_raise_video]:
                if vw:
                    vw.release()

            # Delete temp files
            for temp_file in [temp_leaning, temp_mobile, temp_passing, temp_turning, temp_hand_raise]:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        print(f"🗑️ Deleted temp file: {os.path.basename(temp_file)}")
                    except:
                        pass

            # Delete transcode temp file
            if transcode_path and os.path.exists(transcode_path):
                try:
                    os.remove(transcode_path)
                    print(f"🗑️ Deleted transcode temp: {os.path.basename(transcode_path)}")
                except:
                    pass

            # Print summary
            print(f"\n{'='*60}")
            print(f"✅ VIDEO PROCESSING COMPLETE")

            print(f"\n🔍 Detection Analysis (max consecutive frames):")
            print(f"   Leaning: {max_leaning_frames} frames (threshold: {LEANING_THRESHOLD})")
            print(f"   Passing: {max_passing_frames} frames (threshold: {PASSING_THRESHOLD})")
            print(f"   Mobile: {max_mobile_frames} frames (threshold: {MOBILE_THRESHOLD})")
            print(f"   Turning: {max_turning_frames} frames (threshold: {TURNING_THRESHOLD})")
            print(f"   Hand Raise: {max_hand_raise_frames} frames (threshold: {HAND_RAISE_THRESHOLD})")

            print(f"\n📊 Total Detections Saved to Database:")
            detections_found = False
            total_detections = 0
            for action, count in detections_count.items():
                if count > 0:
                    print(f"   ✅ {action}: {count}")
                    detections_found = True
                    total_detections += count

            if not detections_found:
                print(f"   ⚠️ No malpractice detections saved to database")
                print(f"   💡 Possible reasons:")
                print(f"      - Detections didn't reach threshold ({LEANING_THRESHOLD} frames)")
                print(f"      - No suspicious behavior detected in the video")

            print(f"{'='*60}\n")

            # Create completion frame
            completion_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
            completion_frame[:] = (40, 40, 40)

            title = "PROCESSING COMPLETE"
            title_size = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 4)[0]
            title_x = (frame_width - title_size[0]) // 2
            cv2.putText(completion_frame, title, (title_x, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 4)

            center_x = frame_width // 2
            cv2.circle(completion_frame, (center_x, 200), 60, (0, 255, 0), 5)

            total_elapsed = time_module.time() - worker_start
            speed_text = f"Processed in {total_elapsed:.1f}s (GPU: {worker_elapsed:.1f}s)"
            speed_size = cv2.getTextSize(speed_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            speed_x = (frame_width - speed_size[0]) // 2
            cv2.putText(completion_frame, speed_text, (speed_x, 280),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

            y_pos = 340
            if detections_found:
                summary_title = f"{total_detections} Malpractice(s) Detected & Saved"
                summary_size = cv2.getTextSize(summary_title, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)[0]
                summary_x = (frame_width - summary_size[0]) // 2
                cv2.putText(completion_frame, summary_title, (summary_x, y_pos),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

                y_pos += 60
                for action, count in detections_count.items():
                    if count > 0:
                        detail = f"{action.replace('_', ' ').title()}: {count}"
                        detail_size = cv2.getTextSize(detail, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                        detail_x = (frame_width - detail_size[0]) // 2
                        cv2.putText(completion_frame, detail, (detail_x, y_pos),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
                        y_pos += 40
            else:
                no_detection = "No malpractice detected"
                no_detection_size = cv2.getTextSize(no_detection, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)[0]
                no_detection_x = (frame_width - no_detection_size[0]) // 2
                cv2.putText(completion_frame, no_detection, (no_detection_x, y_pos),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2)
                y_pos += 60

            y_pos += 40
            instruction = "View details in Malpractice Logs section"
            inst_size = cv2.getTextSize(instruction, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            inst_x = (frame_width - inst_size[0]) // 2
            cv2.putText(completion_frame, instruction, (inst_x, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 200, 255), 2)

            cv2.rectangle(completion_frame, (0, frame_height - 20), (frame_width, frame_height), (0, 255, 0), -1)
            cv2.putText(completion_frame, "Processing: 100.0% | Complete",
                       (10, frame_height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Queue completion frame for ~1.5 seconds display
            ret_enc, enc_buffer = cv2.imencode('.jpg', completion_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret_enc:
                completion_bytes = enc_buffer.tobytes()
                for _ in range(20):  # ~20 frames for completion screen display
                    try:
                        frame_queue.put(completion_bytes, timeout=5)
                    except:
                        break

        except Exception as e:
            processing_error[0] = e
            import traceback
            traceback.print_exc()
        finally:
            processing_complete.set()

    # ===== START PROCESSING THREAD =====
    worker = threading.Thread(target=processing_worker, daemon=True)
    worker.start()
    print(f"🧵 Processing thread started (ID: {worker.ident})")

    # ===== YIELD FRAMES AT 25 FPS (smooth paced streaming) =====
    # Processing is fast (720p decode + GPU), so frames buffer ahead.
    # We pace output at 25fps for smooth visual feedback.
    frames_yielded = 0
    target_interval = 1.0 / STREAM_FPS  # 0.04s = 25fps

    while not processing_complete.is_set() or not frame_queue.empty():
        frame_start = time_module.time()
        try:
            frame_data = frame_queue.get(timeout=1.0)
        except Empty:
            if processing_complete.is_set():
                break
            continue

        yield frame_data
        frames_yielded += 1

        # Pace at 25fps
        elapsed = time_module.time() - frame_start
        if elapsed < target_interval:
            time_module.sleep(target_interval - elapsed)

    # Drain any remaining frames in queue (still paced)
    while not frame_queue.empty():
        frame_start = time_module.time()
        try:
            frame_data = frame_queue.get_nowait()
            yield frame_data
            frames_yielded += 1
            elapsed = time_module.time() - frame_start
            if elapsed < target_interval:
                time_module.sleep(target_interval - elapsed)
        except Empty:
            break

    # Wait for worker to finish (should already be done)
    worker.join(timeout=5)

    total_time = time_module.time() - pipeline_start
    print(f"\n🏁 Streaming complete: {frames_yielded} frames in {total_time:.1f}s ({frames_yielded/total_time:.1f} fps effective)")

    if processing_error[0]:
        print(f"❌ Processing error occurred: {processing_error[0]}")
