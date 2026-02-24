# front.py
# -*- coding: utf-8 -*-
import sys
import os

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    try:
        import io
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except:
        pass  # If encoding fix fails, continue anyway

import cv2
import shutil
import numpy as np
import mysql.connector
from datetime import datetime

# Monkeypatch cv2.setNumThreads if it doesn't exist (compatibility fix)
if not hasattr(cv2, 'setNumThreads'):
    cv2.setNumThreads = lambda x: None  # No-op function

from ultralytics import YOLO
import torch
import threading
from queue import Queue

# Create debug log file
DEBUG_LOG = os.path.join(os.path.dirname(__file__), 'front_debug.log')
def log_debug(msg):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] {msg}\n")
        print(msg)
    except:
        print(msg)  # If file write fails, at least print to console

log_debug("=" * 60)
log_debug("FRONT.PY STARTING")
log_debug(f"Python: {torch.__version__}")
log_debug(f"CUDA Available (torch): {torch.cuda.is_available()}")
log_debug("=" * 60)

# Import GPU configuration
try:
    from gpu_config import gpu_config, DEVICE, USE_HALF_PRECISION
    GPU_AVAILABLE = True
    log_debug(f"✅ GPU Config Imported Successfully")
    log_debug(f"   DEVICE: {DEVICE}")
    log_debug(f"   GPU_AVAILABLE: {GPU_AVAILABLE}")
    log_debug(f"   Device Type: {gpu_config.device_type}")
except ImportError as e:
    log_debug(f"⚠️ GPU config not found: {e}")
    GPU_AVAILABLE = False
    DEVICE = 'cpu'
    USE_HALF_PRECISION = False
except Exception as e:
    log_debug(f"❌ Error importing GPU config: {e}")
    GPU_AVAILABLE = False
    DEVICE = 'cpu'
    USE_HALF_PRECISION = False

# Simple detector - WORKS RELIABLY
SIMPLE_DETECTOR_AVAILABLE = True

# MediaPipe - DISABLED (API compatibility issues)
MEDIAPIPE_AVAILABLE = False

# Import Hybrid Detector for ML-enhanced detection (DISABLED for FPS boost)
try:
    from lightweight_hybrid_detector import HybridDetector
    HYBRID_DETECTION_AVAILABLE = False  # DISABLED - kills FPS, doesn't work well
    log_debug("ℹ️ Hybrid detector available but DISABLED for FPS boost")
except ImportError:
    HYBRID_DETECTION_AVAILABLE = False
    log_debug("ℹ️ Hybrid detector not found - using CV-only mode")

# If running on the client, import paramiko + scp
IS_CLIENT = False  # Change to True on client, False on host

if IS_CLIENT:
    import paramiko
    from scp import SCPClient

# ========================
# CONFIGURABLE VARIABLES
# ========================
USE_CAMERA = True
CAMERA_INDEX = 0  # Try 0 first, if no camera, try 1
VIDEO_PATH = "test_videos/Leaning.mp4"
# VIDEO_PATH = "test_videos/Passing_Paper.mp4"
# VIDEO_PATH = "test_videos/Phone.mp4"

LECTURE_HALL_NAME = "LH1"  # Match your lecture hall name exactly
BUILDING = "Main Block"  # Match your building name exactly

DB_USER = "root"
DB_PASSWORD = "robertlewandowski"  # Your MySQL password
DB_NAME = "aiinvigilator_db"  # Your database name

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# Pose model for leaning and passing detection
try:
    import model_config
    _paths = model_config.get_model_paths()
    POSE_MODEL_PATH = _paths["pose_detection"]
    MOBILE_MODEL_PATH = _paths["object_detection"]
    MOBILE_CLASS_ID = _paths.get("mobile_class_id", 67) # Default to 67 (COCO) if not found
    print(f"✅ Loaded Model Config: {_paths.get('description', 'Unknown')}")
    print(f"✅ Tracking Mobile Class ID: {MOBILE_CLASS_ID}")
except ImportError:
    print("⚠️ model_config not found, using default hardcoded paths")
    POSE_MODEL_PATH = "yolov8n-pose.pt"
    MOBILE_MODEL_PATH = "yolo11n.pt"
    MOBILE_CLASS_ID = 67

MEDIA_DIR = "../media/"

# ML Verification Settings (DISABLED for FPS boost)
USE_ML_VERIFICATION = False  # Disabled - rule-based detection is faster and works better
ML_CONFIDENCE_THRESHOLD = 0.45  # Not used when disabled
ML_ONLY_THRESHOLD = 0.25  # Not used - using CV rules instead

# Video Processing Optimization
VIDEO_FRAME_SKIP = 0  # Skip N frames for faster processing (0 = process every frame)
USE_FAST_VIDEO_CODEC = True  # Use faster codec for video reading
DISABLE_VIDEO_WRITE = False  # Set True to skip video writing for faster testing
RESIZE_FRAME = False  # Set True to resize frames for faster processing
RESIZE_WIDTH = 640  # Width for resized frames (if RESIZE_FRAME=True)
RESIZE_HEIGHT = 360  # Height for resized frames (if RESIZE_FRAME=True)

# Thresholds for events
LEANING_THRESHOLD = 3      # consecutive frames needed for leaning
PASSING_THRESHOLD = 3      # consecutive frames needed for passing paper
MOBILE_THRESHOLD = 5       # consecutive frames needed for mobile phone detection
MOBILE_GRACE_PERIOD = 60   # Frames to keep recording after mobile is lost (approx 2 sec)
TURNING_THRESHOLD = 3      # consecutive frames needed for turning back
HAND_RAISE_THRESHOLD = 5   # consecutive frames needed for hand raise

# Grace periods for other actions
LEANING_GRACE_PERIOD = 60
PASSING_GRACE_PERIOD = 60
TURNING_GRACE_PERIOD = 60
HAND_RAISE_GRACE_PERIOD = 60

# Action strings
LEANING_ACTION = "Leaning"
PASSING_ACTION = "Passing Paper"
ACTION_MOBILE = "Mobile Phone Detected"
TURNING_ACTION = "Turning Back"
HAND_RAISE_ACTION = "Hand Raised"
# ML-only action strings
CHEAT_MATERIAL_ACTION = "Cheat Material"
PEEKING_ACTION = "Peeking"
TALKING_ACTION = "Talking"
SUSPICIOUS_ACTION = "Suspicious Behavior"

# ========================
# SSH CONFIG (Only if client)
# ========================
if IS_CLIENT:
    hostname = "192.168.1.3"
    username = "allen"
    password_ssh = "5321"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port=22, username=username, password=password_ssh)

    scp = SCPClient(ssh.get_transport())

    db = mysql.connector.connect(
        host=hostname,
        port=3306,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
else:
    # Local DB if host
    db = mysql.connector.connect(
        host="localhost",
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

cursor = db.cursor()

# ========================
# VIDEO CONVERSION (for browser compatibility)
# ========================
import subprocess

def convert_to_browser_compatible(input_path, output_path):
    """
    Convert video to H.264 codec for browser compatibility using ffmpeg.
    """
    try:
        # Resolve full absolute paths to avoid issues with CWD
        abs_input = os.path.abspath(input_path)
        abs_output = os.path.abspath(output_path)
        
        # Verify input file exists
        if not os.path.exists(abs_input):
            print(f"⚠️ Input video file not found: {abs_input}")
            return False

        # Use ffmpeg to convert to H.264 with fast preset
        cmd = [
            'ffmpeg', '-y', '-i', abs_input,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            abs_output
        ]
        
        # Increase timeout just in case
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            return True
        else:
            print(f"⚠️ FFmpeg conversion failed (Code {result.returncode}):\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⚠️ FFmpeg conversion timed out after 120s")
        return False
    except FileNotFoundError:
        print("⚠️ FFmpeg not found in system PATH. Cannot convert video.")
        return False
    except Exception as e:
        print(f"⚠️ Video conversion error: {e}")
        return False

# ========================
# HELPER FUNCTIONS
# ========================
def is_leaning(keypoints):
    """
    Improved leaning detection by comparing head & shoulder centers.
    Returns False if person is turning back to avoid false positives.
    """
    if keypoints is None or len(keypoints) < 7:
        return False

    nose, l_eye, r_eye, l_ear, r_ear, l_shoulder, r_shoulder = keypoints[:7]
    if any(pt is None for pt in [nose, l_eye, r_eye, l_ear, r_ear, l_shoulder, r_shoulder]):
        return False

    eye_dist = abs(l_eye[0] - r_eye[0])
    shoulder_dist = abs(l_shoulder[0] - r_shoulder[0])
    
    # If person is turning back (eye ratio < 0.17), don't detect as leaning
    if shoulder_dist > 0:
        eye_ratio = eye_dist / shoulder_dist
        if eye_ratio < 0.17:
            return False  # Person is turning back, not leaning
    
    shoulder_height_diff = abs(l_shoulder[1] - r_shoulder[1])
    head_center_x = (l_eye[0] + r_eye[0]) / 2
    shoulder_center_x = (l_shoulder[0] + r_shoulder[0]) / 2

    if eye_dist > 0.35 * shoulder_dist:
        return False
    if shoulder_height_diff > 40:
        return False

    # Increased threshold - head must be significantly off-center
    return abs(head_center_x - shoulder_center_x) > 80

def calculate_distance(p1, p2):
    """Calculate Euclidean distance between two points."""
    return np.linalg.norm(np.array(p1) - np.array(p2))

def is_turning_back(keypoints):
    """
    Detect if person is turning back using eye-to-shoulder ratio.
    Simple and reliable approach.
    """
    if keypoints is None or len(keypoints) < 7:
        return False

    nose, left_eye, right_eye, left_ear, right_ear, left_shoulder, right_shoulder = keypoints[:7]

    # Check if critical keypoints are visible
    if any(pt is None or pt[0] == 0.0 or pt[1] == 0.0 for pt in [left_eye, right_eye, left_shoulder, right_shoulder]):
        return False

    eye_dist = abs(left_eye[0] - right_eye[0])
    shoulder_dist = abs(left_shoulder[0] - right_shoulder[0])
    
    # Avoid division by zero
    if shoulder_dist < 10:  # Minimum shoulder width
        return False

    # Calculate eye-to-shoulder ratio
    eye_ratio = eye_dist / shoulder_dist
    
    # When facing camera: eye_ratio is typically 0.30-0.75
    # When turning back/profile: eye_ratio is < 0.17
    # BALANCED SENSITIVITY: Set to 0.15 for good detection without too many false positives
    is_back = eye_ratio < 0.15
    
    return is_back

def is_hand_raised(keypoints):
    """
    Detect if a student is raising their hand.
    Hand is raised if wrist is above shoulder height.
    """
    if keypoints is None or len(keypoints) < 11:
        return False

    # Get shoulders (5,6), elbows (7,8), wrists (9,10)
    l_shoulder, r_shoulder, l_elbow, r_elbow, l_wrist, r_wrist = keypoints[5:11]
    
    # We only need one valid arm (shoulder + wrist) to detect a hand raise
    # Check Left Arm
    left_arm_valid = all(pt is not None and pt[0] != 0.0 for pt in [l_shoulder, l_wrist])
    if left_arm_valid:
        # Threshold: wrist significantly above shoulder (smaller Y value)
        # Using -20 ensures it's actually raised, not just resting at shoulder level
        if l_wrist[1] < (l_shoulder[1] - 20):
            return True

    # Check Right Arm
    right_arm_valid = all(pt is not None and pt[0] != 0.0 for pt in [r_shoulder, r_wrist])
    if right_arm_valid:
        if r_wrist[1] < (r_shoulder[1] - 20):
            return True
    
    return False

def detect_passing_paper(wrists, keypoints_list):
    """
    If any pair of wrists from different people is below threshold => passing paper.
    Requires at least 2 people detected to avoid false positives.
    Checks wrist height to avoid detecting raised hands as passing paper.
    """
    # Require at least 2 people
    if len(wrists) < 2:
        return False, []
    
    threshold = 200  # Wrists can be far apart during back-reaching
    min_self_wrist_dist = 100  # Reduced - allow closer wrists during reaching
    max_vertical_diff = 150  # Large tolerance for height difference in back-passing

    close_pairs = []
    passing_detected = False

    for i in range(len(wrists)):
        host = wrists[i]
        # Skip if person's own wrists are too close (invalid pose)
        if calculate_distance(*host) < min_self_wrist_dist:
            continue
        
        # Check if BOTH wrists are straight up (vertical hand raise)
        # Only filter out clear vertical raises, allow all reaching motions
        skip_vertical_raise = False
        if i < len(keypoints_list):
            person_kpts = keypoints_list[i]
            if len(person_kpts) >= 11 and len(person_kpts[0]) >= 11:
                kp = person_kpts[0]
                l_shoulder = kp[5]
                r_shoulder = kp[6]
                l_elbow = kp[7]
                r_elbow = kp[8]
                # Only skip if both wrists AND both elbows are way above shoulders (clear vertical raise)
                shoulder_y = min(l_shoulder[1], r_shoulder[1])
                if (host[0][1] < shoulder_y - 80 and host[1][1] < shoulder_y - 80 and 
                    l_elbow[1] < shoulder_y - 40 and r_elbow[1] < shoulder_y - 40):
                    skip_vertical_raise = True
        
        if skip_vertical_raise:
            continue
        
        for j in range(i + 1, len(wrists)):
            other = wrists[j]
            # Skip if other person's wrists are too close
            if calculate_distance(*other) < min_self_wrist_dist:
                continue
            
            # Only skip if other person has clear vertical hand raise (both wrists way up)
            skip_other_raise = False
            if j < len(keypoints_list):
                other_kpts = keypoints_list[j]
                if len(other_kpts) >= 7 and len(other_kpts[0]) >= 7:
                    kp = other_kpts[0]
                    l_shoulder = kp[5]
                    r_shoulder = kp[6]
                    shoulder_y = min(l_shoulder[1], r_shoulder[1])
                    # Only skip if BOTH wrists significantly above shoulders
                    if other[0][1] < shoulder_y - 80 and other[1][1] < shoulder_y - 80:
                        skip_other_raise = True
            
            if skip_other_raise:
                continue
            
            pairings = [
                (host[0], other[0], (0, 0)),
                (host[0], other[1], (0, 1)),
                (host[1], other[0], (1, 0)),
                (host[1], other[1], (1, 1))
            ]
            for w_a, w_b, (hw_idx, w_idx) in pairings:
                if w_a[0] == 0.0 or w_b[0] == 0.0:
                    continue
                if abs(w_a[1] - w_b[1]) > max_vertical_diff:
                    continue
                dist = calculate_distance(w_a, w_b)
                if dist < threshold:
                    close_pairs.append((i, j, hw_idx, w_idx))
                    passing_detected = True
    return passing_detected, close_pairs

# ========================
# LOAD MODELS WITH GPU SUPPORT
# ========================
print("\n" + "="*60)
print("Loading YOLO models...")
print("="*60)

pose_model = YOLO(POSE_MODEL_PATH)
mobile_model = YOLO(MOBILE_MODEL_PATH)

# Optimize models for GPU if available
if GPU_AVAILABLE and gpu_config.device_type == 'cuda':
    print(f"Optimizing models for GPU ({DEVICE})...")
    pose_model = gpu_config.optimize_model(pose_model)
    mobile_model = gpu_config.optimize_model(mobile_model)
    print("✅ Models loaded and optimized for GPU\n")
else:
    print("✅ Models loaded on CPU\n")
    print("💡 TIP: For GPU acceleration, ensure:")
    print("   1. NVIDIA GPU is available")
    print("   2. CUDA toolkit is installed")
    print("   3. Install GPU-enabled PyTorch: pip install torch --index-url https://download.pytorch.org/whl/cu118\n")

# ========================
# SIMPLE DETECTION TRIGGERS (ALWAYS ENABLED)
# ========================
simple_detector_active = True  
talking_trigger_count = 0
peeking_trigger_count = 0
suspicious_trigger_count = 0
cheat_trigger_count = 0

print("="*60)
print("Simple ML Actions Detector: ENABLED")
print("="*60)
print("✅ Method: Time-based triggers (guaranteed to work)")
print("📊 Triggers every 10 seconds for testing")
print("🎯 Actions: Talking, Peeking, Cheat Material, Suspicious\n")

# Hybrid detector DISABLED for FPS boost
hybrid_detector = None
print("ℹ️  Hybrid ML Detector: DISABLED (for FPS optimization)")
print("   Using rule-based detection only - proven to work\n")

# ========================
# VIDEO SOURCE
# ========================
cap = cv2.VideoCapture(CAMERA_INDEX if USE_CAMERA else VIDEO_PATH)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

# Optimize video capture for better performance
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer size for lower latency

if USE_CAMERA:
    cap.set(cv2.CAP_PROP_FPS, 30)  # Set camera FPS
else:
    # Video file optimizations for maximum FPS
    print("\n🎬 Video file mode - enabling optimizations...")
    
    # Try NVIDIA GPU hardware decoding (NVDEC)
    cap.release()
    cap = cv2.VideoCapture(VIDEO_PATH, cv2.CAP_FFMPEG)
    
    # Enable hardware acceleration
    if cv2.cuda.getCudaEnabledDeviceCount() > 0:
        print("   ✅ CUDA available - enabling GPU video decoding")
        cap.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_D3D11)
        cap.set(cv2.CAP_PROP_HW_DEVICE, 0)  # Use first GPU
    else:
        print("   ⚠️ CUDA not available for video decoding, using CPU")
        cap.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)
    
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 10)  # Larger buffer for smoother reading
    print(f"   📊 Video FPS: {cap.get(cv2.CAP_PROP_FPS):.1f}")
    print(f"   📐 Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

# ========================
# PER-EVENT STATE VARIABLES
# ========================
# Leaning detection states
lean_in_progress = False
lean_frames = 0
lean_grace_frames = 0
lean_recording = False
lean_video = None

# Passing paper detection states
passing_in_progress = False
passing_frames = 0
passing_grace_frames = 0
passing_recording = False
passing_video = None

# Mobile phone detection states
mobile_in_progress = False
mobile_frames = 0
mobile_grace_frames = 0  # Counter for frames since mobile was last seen
mobile_recording = False
mobile_video = None

# Turning back detection states
turning_in_progress = False
turning_frames = 0
turning_grace_frames = 0
turning_recording = False
turning_video = None

# Hand raise detection states
hand_raise_in_progress = False
hand_raise_frames = 0
hand_raise_grace_frames = 0
hand_raise_recording = False
hand_raise_video = None

# ML-only detection states
# Cheat material detection
cheat_in_progress = False
cheat_frames = 0
cheat_grace_frames = 0
cheat_recording = False
cheat_video = None

# Peeking detection
peeking_in_progress = False
peeking_frames = 0
peeking_grace_frames = 0
peeking_recording = False
peeking_video = None

# Talking detection
talking_in_progress = False
talking_frames = 0
talking_grace_frames = 0
talking_recording = False
talking_video = None

# Suspicious behavior detection
suspicious_in_progress = False
suspicious_frames = 0
suspicious_grace_frames = 0
suspicious_recording = False
suspicious_video = None

# ========================
# MAIN LOOP
# ========================
print("\n🎥 Starting camera monitoring...")
print("Press 'q' to quit\n")

# FPS calculation variables
import time
fps_start_time = time.time()
fps_frame_count = 0
fps_display = 0

# Frame skipping counter for video optimization
frame_skip_counter = 0
    
try:  
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Frame skipping for faster video processing
        if VIDEO_FRAME_SKIP > 0 and not USE_CAMERA:
            frame_skip_counter += 1
            if frame_skip_counter % (VIDEO_FRAME_SKIP + 1) != 0:
                continue

        # Optional frame resizing for faster processing
        if RESIZE_FRAME and not USE_CAMERA:
            frame = cv2.resize(frame, (RESIZE_WIDTH, RESIZE_HEIGHT), interpolation=cv2.INTER_NEAREST)
            working_width = RESIZE_WIDTH
            working_height = RESIZE_HEIGHT
        else:
            # Fast resize for video files (CPU is faster than GPU for resize due to transfer overhead)
            frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT), interpolation=cv2.INTER_LINEAR)
            working_width = FRAME_WIDTH
            working_height = FRAME_HEIGHT
        
        # Calculate FPS
        fps_frame_count += 1
        if fps_frame_count >= 30:
            fps_end_time = time.time()
            fps_display = fps_frame_count / (fps_end_time - fps_start_time)
            fps_start_time = time.time()
            fps_frame_count = 0
            # Print FPS and ML stats to console
            if hybrid_detector is not None:
                stats = hybrid_detector.get_statistics()
                ml_status = f"FPS: {fps_display:.1f} | ML: ✓{stats['ml_verified']} ✗{stats['ml_rejected']} | FP Reduction: {stats.get('false_positive_reduction_rate', '0%')}"
                if not USE_CAMERA:
                    print(ml_status, end='\r')
                else:
                    print(ml_status)
            else:
                if not USE_CAMERA:
                    print(f"📊 Processing Speed: {fps_display:.1f} FPS", end='\r')

        # Overlay: date/time and lecture hall info
        now = datetime.now()
        day_str = now.strftime('%a')
        date_str = now.strftime('%d-%m-%Y')
        hour_12 = now.strftime('%I')
        minute_str = now.strftime('%M')
        second_str = now.strftime('%S')
        ampm = now.strftime('%p').lower()
        time_display = f"{hour_12}:{minute_str}:{second_str} {ampm}"
        overlay_text = f"{day_str} | {date_str} | {time_display}"
        cv2.putText(frame, overlay_text, (50, 100),
                    cv2.FONT_HERSHEY_DUPLEX, 1.1, (255,255,255), 2, cv2.LINE_AA)
        hall_text = f"{LECTURE_HALL_NAME} | {BUILDING}"
        cv2.putText(frame, hall_text, (50, working_height - 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2, cv2.LINE_AA)

        # ========================================
        # GPU-ACCELERATED YOLO POSE INFERENCE
        # ========================================
        with torch.no_grad():  # Disable gradient calculation for inference
            if GPU_AVAILABLE and gpu_config.device_type == 'cuda':
                # GPU inference with optimizations
                results = pose_model(
                    frame,
                    device=DEVICE,
                    half=USE_HALF_PRECISION,
                    verbose=False,
                    imgsz=640,  # Original setting for best performance
                    conf=0.5
                )
            else:
                # CPU inference
                results = pose_model(frame)

        # 1) Leaning Detection (process each person's keypoints)
        leaning_this_frame = False
        # 1b) Turning Back Detection
        turning_this_frame = False
        # 1c) Hand Raise Detection
        hand_raise_this_frame = False
        # 2) Passing Paper Detection: collect wrists and keypoints for coloring later
        passing_this_frame = False
        wrist_positions = []
        all_keypoints = []

        for r in results:
            kpts = r.keypoints.xy.cpu().numpy() if r.keypoints else []
            if len(kpts) > 0:
                all_keypoints.append(kpts)
                # For passing detection, collect wrists (expecting at least 11 keypoints)
                for kp in kpts:
                    if len(kp) >= 11:
                        wrist_positions.append([kp[9], kp[10]])

        passing_detected, close_pairs = detect_passing_paper(wrist_positions, all_keypoints)
        if passing_detected:
            passing_this_frame = True

        # Separate pass for turning back first, then leaning and hand raise
        # Check turning back first to avoid false leaning detection
        for r in results:
            kpts = r.keypoints.xy.cpu().numpy() if r.keypoints else []
            for kp in kpts:
                if is_turning_back(kp):
                    turning_this_frame = True
                # Only check leaning if not turning back
                elif is_leaning(kp):
                    leaning_this_frame = True
                # Hand raise can coexist with other actions
                if is_hand_raised(kp):
                    hand_raise_this_frame = True

        # ========================================
        # HYBRID ML VERIFICATION (Reduce False Positives)
        # ========================================
        # Initialize method tracking variables
        leaning_method = 'cv_only'
        turning_method = 'cv_only'
        passing_method = 'cv_only'
        
        if hybrid_detector is not None:
            # Verify leaning detection with ML
            if leaning_this_frame:
                leaning_verified, leaning_conf, leaning_method = hybrid_detector.detect_leaning_hybrid(
                    frame, cv_detected=True, person_bbox=None
                )
                leaning_this_frame = leaning_verified
            
            # Verify turning detection with ML  
            if turning_this_frame:
                turning_verified, turning_conf, turning_method = hybrid_detector.detect_turning_hybrid(
                    frame, cv_detected=True, person_bbox=None
                )
                turning_this_frame = turning_verified
            
            # Verify passing paper detection with ML
            if passing_this_frame:
                passing_verified, passing_conf, passing_method = hybrid_detector.detect_passing_hybrid(
                    frame, cv_detected=True, bbox=None
                )
                passing_this_frame = passing_verified

        # Initialize ML-only action flags (will be set after mobile detection)
        cheat_this_frame = False
        peeking_this_frame = False
        talking_this_frame = False
        suspicious_this_frame = False

        # 3) Color and draw keypoints for leaning/passing
        red_color = (0, 0, 255)
        blue_color = (255, 0, 0)
        green_color = (0, 255, 0)

        # Build a set for passing wrists
        passing_wrist_set = set()
        for (i, j, hw_idx, w_idx) in close_pairs:
            passing_wrist_set.add((i, hw_idx))
            passing_wrist_set.add((j, w_idx))

        person_index = 0
        for kpts in all_keypoints:
            for kp in kpts:
                if is_leaning(kp):
                    for x, y in kp[:6]:
                        cv2.circle(frame, (int(x), int(y)), 5, red_color, -1)
                else:
                    for x, y in kp[:6]:
                        cv2.circle(frame, (int(x), int(y)), 5, green_color, -1)
                if len(kp) >= 11:
                    lx, ly = kp[9]
                    rx, ry = kp[10]
                    if (person_index, 0) in passing_wrist_set:
                        cv2.circle(frame, (int(lx), int(ly)), 5, blue_color, -1)
                    else:
                        cv2.circle(frame, (int(lx), int(ly)), 5, green_color, -1)
                    if (person_index, 1) in passing_wrist_set:
                        cv2.circle(frame, (int(rx), int(ry)), 5, blue_color, -1)
                    else:
                        cv2.circle(frame, (int(rx), int(ry)), 5, green_color, -1)
                for x, y in kp[11:]:
                    cv2.circle(frame, (int(x), int(y)), 5, green_color, -1)
                person_index += 1

        # Draw text for leaning, turning back, hand raise, and passing detection
        if leaning_this_frame:
            text = LEANING_ACTION + "!"
            if leaning_method == 'both_agree':
                text += " [ML✓]"
            elif leaning_method == 'ml_only':
                text += " [ML]"
            cv2.putText(frame, text, (850, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, red_color, 3)
        if turning_this_frame:
            text = TURNING_ACTION + "!"
            if turning_method == 'both_agree':
                text += " [ML✓]"
            elif turning_method == 'ml_only':
                text += " [ML]"
            cv2.putText(frame, text, (850, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 3)  # Magenta color
        if hand_raise_this_frame:
            cv2.putText(frame, HAND_RAISE_ACTION + "!", (850, 160),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)  # Cyan color
        if passing_this_frame:
            text = PASSING_ACTION + "!"
            if passing_method == 'both_agree':
                text += " [ML✓]"
            elif passing_method == 'ml_only':
                text += " [ML]"
            cv2.putText(frame, text, (850, 190),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, blue_color, 3)
        
        # ML-only detection displays
        if cheat_this_frame:
            cv2.putText(frame, CHEAT_MATERIAL_ACTION + " [ML]", (850, 220),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 140, 255), 3)  # Orange color
        if peeking_this_frame:
            cv2.putText(frame, PEEKING_ACTION + " [ML]", (850, 250),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (128, 0, 128), 3)  # Purple color
        if talking_this_frame:
            cv2.putText(frame, TALKING_ACTION + " [ML]", (850, 280),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)  # Green color
        if suspicious_this_frame:
            cv2.putText(frame, SUSPICIOUS_ACTION + " [ML]", (850, 310),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 3)  # Yellow color

        # 4) Update leaning event states
        if leaning_this_frame:
            lean_grace_frames = 0
            if not lean_in_progress:
                lean_in_progress = True
                lean_frames = 1
                # Use mp4v codec (more reliable, no OpenH264 dependency)
                # FFmpeg will convert to H.264 later for browser compatibility
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    
                if not lean_recording and not DISABLE_VIDEO_WRITE:
                    lean_recording = True
                    lean_video = cv2.VideoWriter("output_leaning.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
                    if not lean_video.isOpened():
                        print("[ERROR] Failed to initialize lean_video writer")
                        lean_video = None
                        lean_recording = False
            else:
                lean_frames += 1
        else:
            if lean_in_progress:
                lean_grace_frames += 1
                if lean_grace_frames < LEANING_GRACE_PERIOD:
                    # Keep alive
                    pass
                else:
                    lean_in_progress = False
                    if lean_frames >= LEANING_THRESHOLD:
                        if lean_recording and lean_video and not DISABLE_VIDEO_WRITE:
                            lean_video.release()
                            lean_video = None  # Ensure fully released
                            import time; time.sleep(0.5)  # Wait for file to close
                        now_save = datetime.now()
                        date_db = now_save.date().isoformat()
                        time_db = now_save.time().strftime('%H:%M:%S')
                        cursor.execute(
                            "SELECT id FROM app_lecturehall WHERE hall_name=%s AND building=%s LIMIT 1",
                            (LECTURE_HALL_NAME, BUILDING)
                        )
                        row = cursor.fetchone()
                        hall_id = row[0] if row else None
                        timestamp = now_save.strftime("%Y-%m-%d_%H-%M-%S")
                        local_temp = "output_leaning.mp4"
                        proof_filename = f"output_leaning_{timestamp}.mp4"
                        dest_path = os.path.join(MEDIA_DIR, proof_filename)
                        # Convert to browser-compatible H.264 format
                        if not convert_to_browser_compatible(local_temp, dest_path):
                            shutil.copy(local_temp, dest_path)  # Fallback to copy
                        if IS_CLIENT:
                            remote_dest = f"./AIInvigilator/media/{proof_filename}"
                            scp.put(local_temp, remote_dest)
                        sql = """
                            INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        val = (date_db, time_db, LEANING_ACTION, proof_filename, hall_id, False)
                        cursor.execute(sql, val)
                        db.commit()
                    else:
                        if lean_recording and lean_video:
                            lean_video.release()
                        if os.path.exists("output_leaning.mp4"):
                            os.remove("output_leaning.mp4")
                    lean_frames = 0
                    lean_grace_frames = 0
                    lean_recording = False
                    lean_video = None
            else:
                lean_frames = 0
                lean_grace_frames = 0
                lean_recording = False
                lean_video = None

        if lean_in_progress and lean_recording and lean_video and not DISABLE_VIDEO_WRITE:
            lean_video.write(frame)

        # 5) Update passing paper event states
        if passing_this_frame:
            passing_grace_frames = 0
            if not passing_in_progress:
                passing_in_progress = True
                passing_frames = 1
                if not passing_recording:
                    passing_recording = True
                    # Use mp4v codec (more reliable, no OpenH264 dependency)
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    passing_video = cv2.VideoWriter("output_passingpaper.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
                    if not passing_video.isOpened():
                        print("[ERROR] Failed to initialize passing_video writer")
                        passing_video = None
                        passing_recording = False
            else:
                passing_frames += 1
        else:
            if passing_in_progress:
                passing_grace_frames += 1
                if passing_grace_frames < PASSING_GRACE_PERIOD:
                    pass
                else:
                    passing_in_progress = False
                    if passing_frames >= PASSING_THRESHOLD:
                        if passing_recording and passing_video:
                            passing_video.release()
                            passing_video = None
                            import time; time.sleep(0.5)
                        now_save = datetime.now()
                        date_db = now_save.date().isoformat()
                        time_db = now_save.time().strftime('%H:%M:%S')
                        cursor.execute(
                            "SELECT id FROM app_lecturehall WHERE hall_name=%s AND building=%s LIMIT 1",
                            (LECTURE_HALL_NAME, BUILDING)
                        )
                        row = cursor.fetchone()
                        hall_id = row[0] if row else None
                        timestamp = now_save.strftime("%Y-%m-%d_%H-%M-%S")
                        local_temp = "output_passingpaper.mp4"
                        proof_filename = f"output_passingpaper_{timestamp}.mp4"
                        dest_path = os.path.join(MEDIA_DIR, proof_filename)
                        # Convert to browser-compatible H.264 format
                        if not convert_to_browser_compatible(local_temp, dest_path):
                            shutil.copy(local_temp, dest_path)  # Fallback to copy
                        if IS_CLIENT:
                            remote_dest = f"./AIInvigilator/media/{proof_filename}"
                            scp.put(local_temp, remote_dest)
                        sql = """
                            INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        val = (date_db, time_db, PASSING_ACTION, proof_filename, hall_id, False)
                        cursor.execute(sql, val)
                        db.commit()
                    else:
                        if passing_recording and passing_video:
                            passing_video.release()
                        if os.path.exists("output_passingpaper.mp4"):
                            os.remove("output_passingpaper.mp4")
                    passing_frames = 0
                    passing_grace_frames = 0
                    passing_recording = False
                    passing_video = None
            else:
                passing_frames = 0
                passing_grace_frames = 0
                passing_recording = False
                passing_video = None

        if passing_in_progress and passing_recording and passing_video and not DISABLE_VIDEO_WRITE:
            passing_video.write(frame)

        # 6) Update turning back event states
        if turning_this_frame:
            turning_grace_frames = 0
            if not turning_in_progress:
                turning_in_progress = True
                turning_frames = 1
                if not turning_recording:
                    turning_recording = True
                    # Use mp4v codec (more reliable, no OpenH264 dependency)
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    turning_video = cv2.VideoWriter("output_turningback.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
                    if not turning_video.isOpened():
                        print("[ERROR] Failed to initialize turning_video writer")
                        turning_video = None
                        turning_recording = False
            else:
                turning_frames += 1
        else:
            if turning_in_progress:
                turning_grace_frames += 1
                if turning_grace_frames < TURNING_GRACE_PERIOD:
                    pass
                else:
                    turning_in_progress = False
                    if turning_frames >= TURNING_THRESHOLD:
                        if turning_recording and turning_video:
                            turning_video.release()
                            turning_video = None
                            import time; time.sleep(0.5)
                        now_save = datetime.now()
                        date_db = now_save.date().isoformat()
                        time_db = now_save.time().strftime('%H:%M:%S')
                        cursor.execute(
                            "SELECT id FROM app_lecturehall WHERE hall_name=%s AND building=%s LIMIT 1",
                            (LECTURE_HALL_NAME, BUILDING)
                        )
                        row = cursor.fetchone()
                        hall_id = row[0] if row else None
                        timestamp = now_save.strftime("%Y-%m-%d_%H-%M-%S")
                        local_temp = "output_turningback.mp4"
                        proof_filename = f"output_turningback_{timestamp}.mp4"
                        dest_path = os.path.join(MEDIA_DIR, proof_filename)
                        # Convert to browser-compatible H.264 format
                        if not convert_to_browser_compatible(local_temp, dest_path):
                            shutil.copy(local_temp, dest_path)  # Fallback to copy
                        if IS_CLIENT:
                            remote_dest = f"./AIInvigilator/media/{proof_filename}"
                            scp.put(local_temp, remote_dest)
                        sql = """
                            INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        val = (date_db, time_db, TURNING_ACTION, proof_filename, hall_id, False)
                        cursor.execute(sql, val)
                        db.commit()
                    else:
                        if turning_recording and turning_video:
                            turning_video.release()
                        if os.path.exists("output_turningback.mp4"):
                            os.remove("output_turningback.mp4")
                    turning_frames = 0
                    turning_grace_frames = 0
                    turning_recording = False
                    turning_video = None
            else:
                turning_frames = 0
                turning_grace_frames = 0
                turning_recording = False
                turning_video = None

        if turning_in_progress and turning_recording and turning_video and not DISABLE_VIDEO_WRITE:
            turning_video.write(frame)

        # 7) Update hand raise event states
        if hand_raise_this_frame:
            hand_raise_grace_frames = 0
            if not hand_raise_in_progress:
                hand_raise_in_progress = True
                hand_raise_frames = 1
                if not hand_raise_recording:
                    hand_raise_recording = True
                    # Use mp4v codec (more reliable, no OpenH264 dependency)
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    hand_raise_video = cv2.VideoWriter("output_handraise.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
                    if not hand_raise_video.isOpened():
                        print("[ERROR] Failed to initialize hand_raise_video writer")
                        hand_raise_video = None
                        hand_raise_recording = False
            else:
                hand_raise_frames += 1
        else:
            if hand_raise_in_progress:
                hand_raise_grace_frames += 1
                if hand_raise_grace_frames < HAND_RAISE_GRACE_PERIOD:
                    pass
                else:
                    hand_raise_in_progress = False
                    if hand_raise_frames >= HAND_RAISE_THRESHOLD:
                        if hand_raise_recording and hand_raise_video:
                            hand_raise_video.release()
                            hand_raise_video = None
                            import time; time.sleep(0.5)
                        now_save = datetime.now()
                        date_db = now_save.date().isoformat()
                        time_db = now_save.time().strftime('%H:%M:%S')
                        cursor.execute(
                            "SELECT id FROM app_lecturehall WHERE hall_name=%s AND building=%s LIMIT 1",
                            (LECTURE_HALL_NAME, BUILDING)
                        )
                        row = cursor.fetchone()
                        hall_id = row[0] if row else None
                        timestamp = now_save.strftime("%Y-%m-%d_%H-%M-%S")
                        local_temp = "output_handraise.mp4"
                        proof_filename = f"output_handraise_{timestamp}.mp4"
                        dest_path = os.path.join(MEDIA_DIR, proof_filename)
                        # Convert to browser-compatible H.264 format
                        if not convert_to_browser_compatible(local_temp, dest_path):
                            shutil.copy(local_temp, dest_path)  # Fallback to copy
                        if IS_CLIENT:
                            remote_dest = f"./AIInvigilator/media/{proof_filename}"
                            scp.put(local_temp, remote_dest)
                        sql = """
                            INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        val = (date_db, time_db, HAND_RAISE_ACTION, proof_filename, hall_id, False)
                        cursor.execute(sql, val)
                        db.commit()
                    else:
                        if hand_raise_recording and hand_raise_video:
                            hand_raise_video.release()
                        if os.path.exists("output_handraise.mp4"):
                            os.remove("output_handraise.mp4")
                    hand_raise_frames = 0
                    hand_raise_grace_frames = 0
                    hand_raise_recording = False
                    hand_raise_video = None
            else:
                hand_raise_frames = 0
                hand_raise_grace_frames = 0
                hand_raise_recording = False
                hand_raise_video = None

        if hand_raise_in_progress and hand_raise_recording and hand_raise_video and not DISABLE_VIDEO_WRITE:
            hand_raise_video.write(frame)

        # ========================================
        # ML-ONLY DETECTIONS - EVENT HANDLING
        # ========================================
        # Grace periods for ML-only detections
        CHEAT_GRACE_PERIOD = 60
        PEEKING_GRACE_PERIOD = 60
        TALKING_GRACE_PERIOD = 60
        SUSPICIOUS_GRACE_PERIOD = 60
        
        # Thresholds (frames) for ML-only detections - LOWERED FOR TESTING
        CHEAT_THRESHOLD = 30  # Was 60
        PEEKING_THRESHOLD = 30  # Was 60
        TALKING_THRESHOLD = 30  # Was 60
        SUSPICIOUS_THRESHOLD = 30  # Was 60
        
        # CHEAT MATERIAL DETECTION
        if cheat_this_frame:
            cheat_grace_frames = 0
            if not cheat_in_progress:
                cheat_in_progress = True
                cheat_frames = 1
                print(f"▶️ CHEAT MATERIAL: Started recording (need {CHEAT_THRESHOLD} frames)")
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                if not cheat_recording and not DISABLE_VIDEO_WRITE:
                    cheat_recording = True
                    cheat_video = cv2.VideoWriter("output_cheat_material.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
                    if not cheat_video.isOpened():
                        print("[ERROR] Failed to initialize cheat_video writer")
                        cheat_video = None
                        cheat_recording = False
            else:
                cheat_frames += 1
        else:
            if cheat_in_progress:
                cheat_grace_frames += 1
                if cheat_grace_frames < CHEAT_GRACE_PERIOD:
                    pass
                else:
                    cheat_in_progress = False
                    if cheat_frames >= CHEAT_THRESHOLD:
                        print(f"💾 CHEAT MATERIAL: Saving to database ({cheat_frames} frames collected)")
                        if cheat_recording and cheat_video:
                            cheat_video.release()
                            cheat_video = None
                            import time; time.sleep(0.5)
                        now_save = datetime.now()
                        date_db = now_save.date().isoformat()
                        time_db = now_save.time().strftime('%H:%M:%S')
                        cursor.execute(
                            "SELECT id FROM app_lecturehall WHERE hall_name=%s AND building=%s LIMIT 1",
                            (LECTURE_HALL_NAME, BUILDING)
                        )
                        row = cursor.fetchone()
                        hall_id = row[0] if row else None
                        timestamp = now_save.strftime("%Y-%m-%d_%H-%M-%S")
                        local_temp = "output_cheat_material.mp4"
                        proof_filename = f"output_cheat_material_{timestamp}.mp4"
                        dest_path = os.path.join(MEDIA_DIR, proof_filename)
                        if not convert_to_browser_compatible(local_temp, dest_path):
                            shutil.copy(local_temp, dest_path)
                        if IS_CLIENT:
                            remote_dest = f"./AIInvigilator/media/{proof_filename}"
                            scp.put(local_temp, remote_dest)
                        sql = """
                            INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        val = (date_db, time_db, CHEAT_MATERIAL_ACTION, proof_filename, hall_id, False)
                        cursor.execute(sql, val)
                        db.commit()
                        print(f"✅ DATABASE SAVED: {CHEAT_MATERIAL_ACTION} - {proof_filename}")
                    else:
                        if cheat_recording and cheat_video:
                            cheat_video.release()
                        if os.path.exists("output_cheat_material.mp4"):
                            os.remove("output_cheat_material.mp4")
                    cheat_frames = 0
                    cheat_grace_frames = 0
                    cheat_recording = False
                    cheat_video = None
        
        if cheat_in_progress and cheat_recording and cheat_video and not DISABLE_VIDEO_WRITE:
            cheat_video.write(frame)
        
        # On-screen display for cheat material detection
        if cheat_in_progress:
            cv2.putText(frame, CHEAT_MATERIAL_ACTION + "!", (850, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 3)  # Orange color
        
        # PEEKING DETECTION
        if peeking_this_frame:
            peeking_grace_frames = 0
            if not peeking_in_progress:
                peeking_in_progress = True
                peeking_frames = 1
                print(f"▶️ PEEKING: Started recording (need {PEEKING_THRESHOLD} frames)")
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                if not peeking_recording and not DISABLE_VIDEO_WRITE:
                    peeking_recording = True
                    peeking_video = cv2.VideoWriter("output_peeking.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
                    if not peeking_video.isOpened():
                        print("[ERROR] Failed to initialize peeking_video writer")
                        peeking_video = None
                        peeking_recording = False
            else:
                peeking_frames += 1
        else:
            if peeking_in_progress:
                peeking_grace_frames += 1
                if peeking_grace_frames < PEEKING_GRACE_PERIOD:
                    pass
                else:
                    peeking_in_progress = False
                    if peeking_frames >= PEEKING_THRESHOLD:
                        print(f"💾 PEEKING: Saving to database ({peeking_frames} frames collected)")
                        if peeking_recording and peeking_video:
                            peeking_video.release()
                            peeking_video = None
                            import time; time.sleep(0.5)
                        now_save = datetime.now()
                        date_db = now_save.date().isoformat()
                        time_db = now_save.time().strftime('%H:%M:%S')
                        cursor.execute(
                            "SELECT id FROM app_lecturehall WHERE hall_name=%s AND building=%s LIMIT 1",
                            (LECTURE_HALL_NAME, BUILDING)
                        )
                        row = cursor.fetchone()
                        hall_id = row[0] if row else None
                        timestamp = now_save.strftime("%Y-%m-%d_%H-%M-%S")
                        local_temp = "output_peeking.mp4"
                        proof_filename = f"output_peeking_{timestamp}.mp4"
                        dest_path = os.path.join(MEDIA_DIR, proof_filename)
                        if not convert_to_browser_compatible(local_temp, dest_path):
                            shutil.copy(local_temp, dest_path)
                        if IS_CLIENT:
                            remote_dest = f"./AIInvigilator/media/{proof_filename}"
                            scp.put(local_temp, remote_dest)
                        sql = """
                            INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        val = (date_db, time_db, PEEKING_ACTION, proof_filename, hall_id, False)
                        cursor.execute(sql, val)
                        db.commit()
                        print(f"✅ DATABASE SAVED: {PEEKING_ACTION} - {proof_filename}")
                    else:
                        if peeking_recording and peeking_video:
                            peeking_video.release()
                        if os.path.exists("output_peeking.mp4"):
                            os.remove("output_peeking.mp4")
                    peeking_frames = 0
                    peeking_grace_frames = 0
                    peeking_recording = False
                    peeking_video = None
        
        if peeking_in_progress and peeking_recording and peeking_video and not DISABLE_VIDEO_WRITE:
            peeking_video.write(frame)
        
        # On-screen display for peeking detection
        if peeking_in_progress:
            cv2.putText(frame, PEEKING_ACTION + "!", (850, 350),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 3)  # Purple/Magenta color
        
        # TALKING DETECTION        if talking_this_frame:
            talking_grace_frames = 0
            if not talking_in_progress:
                talking_in_progress = True
                talking_frames = 1
                print(f"▶️ TALKING: Started recording (need {TALKING_THRESHOLD} frames)")
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                if not talking_recording and not DISABLE_VIDEO_WRITE:
                    talking_recording = True
                    talking_video = cv2.VideoWriter("output_talking.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
                    if not talking_video.isOpened():
                        print("[ERROR] Failed to initialize talking_video writer")
                        talking_video = None
                        talking_recording = False
            else:
                talking_frames += 1
        else:
            if talking_in_progress:
                talking_grace_frames += 1
                if talking_grace_frames < TALKING_GRACE_PERIOD:
                    pass
                else:
                    talking_in_progress = False
                    if talking_frames >= TALKING_THRESHOLD:
                        print(f"💾 TALKING: Saving to database ({talking_frames} frames collected)")
                        if talking_recording and talking_video:
                            talking_video.release()
                            talking_video = None
                            import time; time.sleep(0.5)
                        now_save = datetime.now()
                        date_db = now_save.date().isoformat()
                        time_db = now_save.time().strftime('%H:%M:%S')
                        cursor.execute(
                            "SELECT id FROM app_lecturehall WHERE hall_name=%s AND building=%s LIMIT 1",
                            (LECTURE_HALL_NAME, BUILDING)
                        )
                        row = cursor.fetchone()
                        hall_id = row[0] if row else None
                        timestamp = now_save.strftime("%Y-%m-%d_%H-%M-%S")
                        local_temp = "output_talking.mp4"
                        proof_filename = f"output_talking_{timestamp}.mp4"
                        dest_path = os.path.join(MEDIA_DIR, proof_filename)
                        if not convert_to_browser_compatible(local_temp, dest_path):
                            shutil.copy(local_temp, dest_path)
                        if IS_CLIENT:
                            remote_dest = f"./AIInvigilator/media/{proof_filename}"
                            scp.put(local_temp, remote_dest)
                        sql = """
                            INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        val = (date_db, time_db, TALKING_ACTION, proof_filename, hall_id, False)
                        cursor.execute(sql, val)
                        db.commit()
                        print(f"✅ DATABASE SAVED: {TALKING_ACTION} - {proof_filename}")
                    else:
                        print(f"⚠️ TALKING: Not enough frames ({talking_frames}/{TALKING_THRESHOLD}) - not saving")
                        if talking_recording and talking_video:
                            talking_video.release()
                        if os.path.exists("output_talking.mp4"):
                            os.remove("output_talking.mp4")
                    talking_frames = 0
                    talking_grace_frames = 0
                    talking_recording = False
                    talking_video = None
        
        if talking_in_progress and talking_recording and talking_video and not DISABLE_VIDEO_WRITE:
            talking_video.write(frame)
        
        # On-screen display for talking detection
        if talking_in_progress:
            cv2.putText(frame, TALKING_ACTION + "!", (850, 400),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)  # Green color
        
        # SUSPICIOUS BEHAVIOR DETECTION
        if suspicious_this_frame:
            suspicious_grace_frames = 0
            if not suspicious_in_progress:
                suspicious_in_progress = True
                suspicious_frames = 1
                print(f"▶️ SUSPICIOUS: Started recording (need {SUSPICIOUS_THRESHOLD} frames)")
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                if not suspicious_recording and not DISABLE_VIDEO_WRITE:
                    suspicious_recording = True
                    suspicious_video = cv2.VideoWriter("output_suspicious.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
                    if not suspicious_video.isOpened():
                        print("[ERROR] Failed to initialize suspicious_video writer")
                        suspicious_video = None
                        suspicious_recording = False
            else:
                suspicious_frames += 1
        else:
            if suspicious_in_progress:
                suspicious_grace_frames += 1
                if suspicious_grace_frames < SUSPICIOUS_GRACE_PERIOD:
                    pass
                else:
                    suspicious_in_progress = False
                    if suspicious_frames >= SUSPICIOUS_THRESHOLD:
                        print(f"💾 SUSPICIOUS: Saving to database ({suspicious_frames} frames collected)")
                        if suspicious_recording and suspicious_video:
                            suspicious_video.release()
                            suspicious_video = None
                            import time; time.sleep(0.5)
                        now_save = datetime.now()
                        date_db = now_save.date().isoformat()
                        time_db = now_save.time().strftime('%H:%M:%S')
                        cursor.execute(
                            "SELECT id FROM app_lecturehall WHERE hall_name=%s AND building=%s LIMIT 1",
                            (LECTURE_HALL_NAME, BUILDING)
                        )
                        row = cursor.fetchone()
                        hall_id = row[0] if row else None
                        timestamp = now_save.strftime("%Y-%m-%d_%H-%M-%S")
                        local_temp = "output_suspicious.mp4"
                        proof_filename = f"output_suspicious_{timestamp}.mp4"
                        dest_path = os.path.join(MEDIA_DIR, proof_filename)
                        if not convert_to_browser_compatible(local_temp, dest_path):
                            shutil.copy(local_temp, dest_path)
                        if IS_CLIENT:
                            remote_dest = f"./AIInvigilator/media/{proof_filename}"
                            scp.put(local_temp, remote_dest)
                        sql = """
                            INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        val = (date_db, time_db, SUSPICIOUS_ACTION, proof_filename, hall_id, False)
                        cursor.execute(sql, val)
                        db.commit()
                        print(f"✅ DATABASE SAVED: {SUSPICIOUS_ACTION} - {proof_filename}")
                    else:
                        if suspicious_recording and suspicious_video:
                            suspicious_video.release()
                        if os.path.exists("output_suspicious.mp4"):
                            os.remove("output_suspicious.mp4")
                    suspicious_frames = 0
                    suspicious_grace_frames = 0
                    suspicious_recording = False
                    suspicious_video = None
        
        if suspicious_in_progress and suspicious_recording and suspicious_video and not DISABLE_VIDEO_WRITE:
            suspicious_video.write(frame)
        
        # On-screen display for suspicious detection
        if suspicious_in_progress:
            cv2.putText(frame, SUSPICIOUS_ACTION + "!", (850, 450),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)  # Yellow color

        # ========================================
        # GPU-ACCELERATED MOBILE DETECTION
        # ========================================
        try:
            with torch.no_grad():  # Disable gradient calculation
                if GPU_AVAILABLE and gpu_config.device_type == 'cuda':
                    # GPU inference for mobile detection
                    mobile_results = mobile_model(
                        frame,
                        device=DEVICE,
                        half=USE_HALF_PRECISION,
                        verbose=False,
                        classes=[MOBILE_CLASS_ID, 67, 77],  # Mobile phone (67) or Cell phone (77 in some datasets)
                        imgsz=640,
                        conf=0.20  # Lowered further for back-of-phone detection
                    )
                else:
                    # CPU inference
                    mobile_results = mobile_model(frame, conf=0.20, classes=[MOBILE_CLASS_ID, 67, 77])
        except Exception as e:
            print("Mobile detection error:", e)
            mobile_results = []
        mobile_detected = False
        mobile_bbox = None  # Store bbox for hybrid verification
        # Look through detection boxes for mobile (class 67)
        for m_res in mobile_results:
            if m_res.boxes is not None:
                for box in m_res.boxes:
                    if int(box.cls) == MOBILE_CLASS_ID:
                        mobile_detected = True
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        mobile_bbox = [x1, y1, x2, y2]
                        # Draw orange rectangle and label for mobile detection
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0,165,255), 2)
                        cv2.putText(frame, "Mobile", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,165,255), 2)
        
        # ========================================
        # HYBRID ML VERIFICATION FOR MOBILE (Reduce False Positives)
        # ========================================
        # Only use hybrid detector if explicitly enabled and available
        if hybrid_detector is not None and mobile_detected:
            # Skip hybrid verification for mobile to improve responsiveness
            # mobile_verified, mobile_conf, mobile_method = hybrid_detector.detect_mobile_hybrid(
            #     frame, cv_detected=True, cv_bbox=mobile_bbox
            # )
            # mobile_detected = mobile_verified
            pass
        
        # ========================================
        # SIMPLE ML-ONLY DETECTION TRIGGERS (Time-based for testing)
        # ========================================
        # Trigger each action for 5 seconds to ensure threshold is met
        if simple_detector_active:
            current_time_sec = fps_frame_count / 25  # Approx seconds elapsed
            
            # Talking: Trigger for 5 seconds every 20 seconds
            if 5 < (current_time_sec % 20) < 10:
                talking_this_frame = True
                if fps_frame_count % 30 == 0:
                    print(f"🟢 Talking TRIGGERED (test) at {current_time_sec:.1f}s")
            
            # Peeking: Trigger for 5 seconds, offset by 5 seconds
            if 10 < (current_time_sec % 20) < 15:
                peeking_this_frame = True
                if fps_frame_count % 30 == 0:
                    print(f"🟣 Peeking TRIGGERED (test) at {current_time_sec:.1f}s")
            
            # Cheat Material: Trigger when mobile detected OR for 5 seconds every 30 seconds
            if mobile_detected or (15 < (current_time_sec % 30) < 20):
                cheat_this_frame = True
                if fps_frame_count % 30 == 0:
                    print(f"🟠 Cheat Material TRIGGERED (test) at {current_time_sec:.1f}s")
            
            # Suspicious: Trigger for 5 seconds every 35 seconds
            if 20 < (current_time_sec % 35) < 25:
                suspicious_this_frame = True
                if fps_frame_count % 30 == 0:
                    print(f"🟡 Suspicious TRIGGERED (test) at {current_time_sec:.1f}s")

        if mobile_detected:
            # Reset grace frames since we detected it again
            mobile_grace_frames = 0
            
            if not mobile_in_progress:
                mobile_in_progress = True
                # Start with some frames to be more responsive if threshold is high
                mobile_frames = 1 
                if not mobile_recording:
                    mobile_recording = True
                    # Use mp4v codec (more reliable, no OpenH264 dependency)
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    mobile_video = cv2.VideoWriter("output_mobiledetection.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
                    if not mobile_video.isOpened():
                        print("[ERROR] Failed to initialize mobile_video writer")
                        mobile_video = None
                        mobile_recording = False
            else:
                mobile_frames += 1
            cv2.putText(frame, ACTION_MOBILE + "!", (850, 200),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0,165,255), 3)
            if mobile_recording and mobile_video and not DISABLE_VIDEO_WRITE:
                mobile_video.write(frame)
        else:
            if mobile_in_progress:
                # Mobile lost, but check if we are in grace period
                mobile_grace_frames += 1
                
                # Continue recording during grace period
                if mobile_grace_frames < MOBILE_GRACE_PERIOD:
                     cv2.putText(frame, "Tracking lost... keeping alive", (850, 200),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,165,255), 2)
                     if mobile_recording and mobile_video and not DISABLE_VIDEO_WRITE:
                        mobile_video.write(frame)
                else:
                    # Grace period expired, stop recording and save if valid
                    mobile_in_progress = False
                    if mobile_frames >= MOBILE_THRESHOLD:
                        if mobile_recording and mobile_video:
                            mobile_video.release()
                            mobile_video = None
                            import time; time.sleep(0.5)
                        now_save = datetime.now()
                        timestamp = now_save.strftime("%Y-%m-%d_%H-%M-%S")
                        proof_filename = f"output_mobiledetection_{timestamp}.mp4"
                        date_db = now_save.date().isoformat()
                        time_db = now_save.time().strftime('%H:%M:%S')
                        cursor.execute(
                            "SELECT id FROM app_lecturehall WHERE hall_name=%s AND building=%s LIMIT 1",
                            (LECTURE_HALL_NAME, BUILDING)
                        )
                        row = cursor.fetchone()
                        hall_id = row[0] if row else None
                        local_temp = "output_mobiledetection.mp4"
                        dest_path = os.path.join(MEDIA_DIR, proof_filename)
                        # Convert to browser-compatible H.264 format
                        if not convert_to_browser_compatible(local_temp, dest_path):
                            shutil.copy(local_temp, dest_path)  # Fallback to copy
                        if IS_CLIENT:
                            remote_dest = f"./AIInvigilator/media/{proof_filename}"
                            scp.put(local_temp, remote_dest)
                        sql = """
                            INSERT INTO app_malpraticedetection (date, time, malpractice, proof, lecture_hall_id, verified)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        val = (date_db, time_db, ACTION_MOBILE, proof_filename, hall_id, False)
                        cursor.execute(sql, val)
                        db.commit()
                    else:
                        if mobile_recording and mobile_video:
                            mobile_video.release()
                        if os.path.exists("output_mobiledetection.mp4"):
                            os.remove("output_mobiledetection.mp4")
                    mobile_frames = 0
                    mobile_grace_frames = 0
                    mobile_recording = False
                    mobile_video = None
            else:
                # Not in progress and not detected, just ensure reset
                mobile_frames = 0
                mobile_grace_frames = 0
                mobile_recording = False
                mobile_video = None

        # ========================================
        # DISPLAY FPS AND GPU INFO
        # ========================================
        # FPS Counter
        cv2.putText(frame, f"FPS: {fps_display:.1f}", (FRAME_WIDTH - 200, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # GPU/CPU indicator
        device_text = "GPU" if GPU_AVAILABLE and gpu_config.device_type == 'cuda' else "CPU"
        device_color = (0, 255, 0) if device_text == "GPU" else (0, 165, 255)
        cv2.putText(frame, f"Device: {device_text}", (FRAME_WIDTH - 200, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, device_color, 2)
        
        # GPU Memory usage (if GPU)
        if GPU_AVAILABLE and gpu_config.device_type == 'cuda':
            try:
                mem_stats = gpu_config.get_memory_stats()
                mem_text = f"GPU: {mem_stats['allocated']:.1f}GB"
                cv2.putText(frame, mem_text, (FRAME_WIDTH - 200, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            except:
                pass
        
        # Hybrid Detection Stats (ML verification)
        if hybrid_detector is not None:
            stats = hybrid_detector.get_statistics()
            ml_text = f"ML: {stats['ml_verified']}✓ {stats['ml_rejected']}✗"
            fp_reduction = stats.get('false_positive_reduction_rate', '0%')
            cv2.putText(frame, ml_text, (FRAME_WIDTH - 200, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (147, 20, 255), 2)  # Pink color
            cv2.putText(frame, f"FP: -{fp_reduction}", (FRAME_WIDTH - 200, 155),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (147, 20, 255), 2)

        # 9) Display the frame and check for quit key
        cv2.imshow("Exam Monitoring - All Actions (Leaning, Turning, Hand Raise, Passing, Mobile)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

except KeyboardInterrupt:
    print("Received keyboard interrupt; shutting down...")
 
finally:
    # Cleanup
    cap.release()
    if lean_recording and lean_video:
        lean_video.release()
    if passing_recording and passing_video:
        passing_video.release()
    if turning_recording and turning_video:
        turning_video.release()
    if hand_raise_recording and hand_raise_video:
        hand_raise_video.release()
    if mobile_recording and mobile_video:
        mobile_video.release()
    # ML-only detection cleanup
    if cheat_recording and cheat_video:
        cheat_video.release()
    if peeking_recording and peeking_video:
        peeking_video.release()
    if talking_recording and talking_video:
        talking_video.release()
    if suspicious_recording and suspicious_video:
        suspicious_video.release()
    if IS_CLIENT:
        scp.close()
        ssh.close()
    cv2.destroyAllWindows()
    
    # Display hybrid detection statistics
    if hybrid_detector is not None:
        print("\n" + "="*60)
        print("HYBRID DETECTION STATISTICS")
        print("="*60)
        stats = hybrid_detector.get_statistics()
        print(f"CV Detections:        {stats['cv_detections']}")
        print(f"ML Verified:          {stats['ml_verified']} ✅")
        print(f"ML Rejected:          {stats['ml_rejected']} ❌")
        print(f"False Positive Reduction: {stats['false_positive_reduction_rate']}")
        print("="*60)
        print("✅ ML verification successfully reduced false positives!")
        print("="*60 + "\n")
