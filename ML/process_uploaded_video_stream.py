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


def save_video_to_database(action, video_filepath, lecture_hall_id):
    """Save video clip to database - exactly like front.py"""
    try:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        
        # Extract just the filename for database
        proof_filename = os.path.basename(video_filepath)
        
        db = mysql.connector.connect(
            host="localhost",
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = db.cursor()
        
        sql = """INSERT INTO app_malpraticedetection 
                 (date, time, malpractice, proof, lecture_hall_id, verified) 
                 VALUES (%s, %s, %s, %s, %s, %s)"""
        
        cursor.execute(sql, (date_str, time_str, action, proof_filename, lecture_hall_id, False))
        db.commit()
        cursor.close()
        db.close()
        
        print(f"\n✅ SAVED TO DATABASE: {action}")
        print(f"   🎥 Video: {proof_filename}")
        print(f"   🕒 Time: {time_str}")
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


def is_passing_paper(keypoints):
    """Check if person is passing paper (extended arms)"""
    try:
        left_shoulder = keypoints[5]
        right_shoulder = keypoints[6]
        left_wrist = keypoints[9]
        right_wrist = keypoints[10]
        
        valid_points = all(kp[2] > 0.5 for kp in [left_shoulder, right_shoulder, left_wrist, right_wrist])
        
        if valid_points:
            left_arm_length = np.linalg.norm(np.array(left_shoulder[:2]) - np.array(left_wrist[:2]))
            right_arm_length = np.linalg.norm(np.array(right_shoulder[:2]) - np.array(right_wrist[:2]))
            shoulder_width = np.linalg.norm(np.array(left_shoulder[:2]) - np.array(right_shoulder[:2]))
            
            if shoulder_width > 0:
                return (left_arm_length / shoulder_width > 1.5) or (right_arm_length / shoulder_width > 1.5)
        
        return False
    except:
        return False


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
    """Process video and yield frames for streaming"""
    print(f"\n{'='*60}")
    print(f"🎬 STREAMING VIDEO PROCESSOR STARTED")
    print(f"📁 Video: {video_path}")
    print(f"🏛️ Lecture Hall ID: {lecture_hall_id}")
    print(f"🔧 Device: {DEVICE}")
    print(f"{'='*60}\n")
    
    # Load models
    print("📦 Loading models...")
    pose_model = YOLO(POSE_MODEL_PATH)
    mobile_model = YOLO(MOBILE_MODEL_PATH)
    
    if GPU_AVAILABLE:
        pose_model.to(DEVICE)
        mobile_model.to(DEVICE)
        print(f"✅ Models loaded on {DEVICE}")
    else:
        print("✅ Models loaded on CPU")
    
    print(f"\n⚙️ Detection Settings:")
    print(f"   Frame skip: Every 3rd frame (3x speed boost)")
    print(f"   Detection threshold: {LEANING_THRESHOLD} frames (~0.3 seconds)")
    print(f"   Grace period: {LEANING_GRACE_PERIOD} frames (~3 seconds after action stops)")
    print(f"   Pre-roll buffer: 2 seconds BEFORE detection (for clearer proof clips)")
    print(f"   Minimum clip length: ~6 seconds (2s before + action + 3s grace)")
    print(f"   Actions monitored: Leaning, Mobile, Passing Paper, Turning Back, Hand Raise")
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Error: Cannot open video {video_path}")
        return
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0
    
    # SPEED OPTIMIZATION: Resize to 720p for processing if video is larger
    # Handles ALL high-res videos (1080p, 2K, 4K, etc.) for faster processing
    MAX_WIDTH = 1280
    MAX_HEIGHT = 720
    
    if original_width > MAX_WIDTH or original_height > MAX_HEIGHT:
        # Calculate scaling factor to fit within 720p while maintaining aspect ratio
        width_scale = MAX_WIDTH / original_width
        height_scale = MAX_HEIGHT / original_height
        scale = min(width_scale, height_scale)  # Use smaller scale to fit within bounds
        
        frame_width = int(original_width * scale)
        frame_height = int(original_height * scale)
        
        print(f"📹 Original: {original_width}x{original_height} - RESIZING to {frame_width}x{frame_height} for speed")
        print(f"   Scale factor: {scale:.2f}x ({original_width*original_height/1000000:.1f}MP → {frame_width*frame_height/1000000:.1f}MP)")
        needs_resize = True
    else:
        frame_width = original_width
        frame_height = original_height
        print(f"📹 Video: {frame_width}x{frame_height} (no resize needed)")
        needs_resize = False
    
    print(f"📹 Video Info: {fps} FPS, {total_frames} frames, {duration:.1f}s")
    print(f"\n▶️ Processing started...\n")
    
    # Initialize counters (ONLY 5 CV-BASED DETECTIONS)
    frame_count = 0
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
    
    # Grace period counters (like front.py)
    leaning_grace_frames = 0
    passing_grace_frames = 0
    mobile_grace_frames = 0
    turning_grace_frames = 0
    hand_raise_grace_frames = 0
    
    # Recording states (like front.py)
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
    
    # Temporary video files (in ML directory for reliability)
    ml_dir = os.path.dirname(__file__)
    temp_leaning = os.path.join(ml_dir, "temp_leaning.mp4")
    temp_passing = os.path.join(ml_dir, "temp_passing.mp4")
    temp_mobile = os.path.join(ml_dir, "temp_mobile.mp4")
    temp_turning = os.path.join(ml_dir, "temp_turning.mp4")
    temp_hand_raise = os.path.join(ml_dir, "temp_hand_raise.mp4")
    
    # CIRCULAR BUFFER: Store last 2 seconds of frames for pre-roll (2 seconds = 2 * fps frames)
    # This allows us to record 2 seconds BEFORE action is detected
    buffer_size = int(2 * fps)  # 2 seconds worth of frames
    frame_buffer = deque(maxlen=buffer_size)  # Automatically removes oldest when full
    print(f"\n💾 Frame Buffer: Storing last {buffer_size} frames (2 seconds) for pre-roll")
    
    # Frame skip for faster processing
    frame_skip = 3
    frames_processed = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # SPEED OPTIMIZATION: Resize frame if needed (any video > 720p)
        if needs_resize:
            frame = cv2.resize(frame, (frame_width, frame_height))
        
        # Add frame to circular buffer (stores ALL frames for 2-second pre-roll)
        frame_buffer.append(frame.copy())
        
        # IMPORTANT: Write ALL frames to ongoing recordings for smooth playback (even skipped frames)
        # This ensures recorded videos are smooth, not choppy
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
        
        # SPEED OPTIMIZATION: Skip frames for faster DETECTION and STREAMING
        # (but we still wrote them to recordings above for smooth playback)
        if frame_count % frame_skip != 0:
            continue
        
        frames_processed += 1
        
        # Create display frame (overlay detections)
        display_frame = frame.copy()
        
        # Initialize detection flags (ONLY 5 CV-BASED DETECTIONS)
        leaning_this_frame = False
        passing_this_frame = False
        mobile_this_frame = False
        turning_this_frame = False
        hand_raise_this_frame = False
        
        # Run pose detection on full frame for accurate keypoint positions
        pose_results = pose_model(frame, verbose=False)
        
        for result in pose_results:
            if result.keypoints is not None and len(result.keypoints) > 0:
                for keypoints in result.keypoints.data:
                    keypoints_np = keypoints.cpu().numpy()
                    
                    # Draw skeleton on display frame
                    for i, (x, y, conf) in enumerate(keypoints_np):
                        if conf > 0.5:  # Only draw visible keypoints
                            cv2.circle(display_frame, (int(x), int(y)), 5, (0, 255, 0), -1)
                    
                    # Draw skeleton connections (COCO format)
                    skeleton_connections = [
                        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),  # Arms
                        (5, 11), (6, 12), (11, 12),  # Torso
                        (11, 13), (13, 15), (12, 14), (14, 16),  # Legs
                        (0, 1), (0, 2), (1, 3), (2, 4)  # Head
                    ]
                    for start_idx, end_idx in skeleton_connections:
                        if start_idx < len(keypoints_np) and end_idx < len(keypoints_np):
                            start_point = keypoints_np[start_idx]
                            end_point = keypoints_np[end_idx]
                            if start_point[2] > 0.5 and end_point[2] > 0.5:
                                cv2.line(display_frame, 
                                        (int(start_point[0]), int(start_point[1])),
                                        (int(end_point[0]), int(end_point[1])),
                                        (0, 255, 0), 2)
                    
                    # ONLY 5 CV-BASED DETECTIONS (using full frame dimensions)
                    if is_leaning(keypoints_np, frame_width, frame_height):
                        leaning_this_frame = True
                    if is_turning_back(keypoints_np):
                        turning_this_frame = True
                    if is_hand_raised(keypoints_np):
                        hand_raise_this_frame = True
                    if is_passing_paper(keypoints_np):
                        passing_this_frame = True
        
        # Run mobile detection on full frame
        mobile_results = mobile_model(frame, verbose=False)
        for result in mobile_results:
            if result.boxes is not None:
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    if class_id == MOBILE_CLASS_ID and box.conf[0] > 0.5:
                        mobile_this_frame = True
                        # Draw bounding box (coordinates are already in full frame scale)
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), COLOR_MOBILE, 3)
                        cv2.putText(display_frame, f"Mobile {box.conf[0]:.2f}", 
                                   (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_MOBILE, 2)
        
        # Update frame counters (ONLY 5 CV-BASED DETECTIONS)
        leaning_frames = leaning_frames + 1 if leaning_this_frame else 0
        passing_frames = passing_frames + 1 if passing_this_frame else 0
        mobile_frames = mobile_frames + 1 if mobile_this_frame else 0
        turning_frames = turning_frames + 1 if turning_this_frame else 0
        hand_raise_frames = hand_raise_frames + 1 if hand_raise_this_frame else 0
        
        # Track max frames for debugging
        max_leaning_frames = max(max_leaning_frames, leaning_frames)
        max_passing_frames = max(max_passing_frames, passing_frames)
        max_mobile_frames = max(max_mobile_frames, mobile_frames)
        max_turning_frames = max(max_turning_frames, turning_frames)
        max_hand_raise_frames = max(max_hand_raise_frames, hand_raise_frames)
        
        # Add detection overlays to display frame (ONLY 5 DETECTIONS)
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
        
        # Add progress bar at bottom (clamp to 100% when near end)
        progress = (frame_count / total_frames) if total_frames > 0 else 0
        # If we're within 5 frames of the end, show 100%
        if total_frames - frame_count <= 5:
            progress = 1.0
        bar_width = int(progress * frame_width)
        cv2.rectangle(display_frame, (0, frame_height - 20), (bar_width, frame_height), (0, 255, 0), -1)
        cv2.putText(display_frame, f"Processing: {progress*100:.1f}% | Frame: {frames_processed}", 
                   (10, frame_height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # VIDEO RECORDING & DATABASE SAVES - Exactly like front.py with grace period!
        # LEANING
        if leaning_frames >= LEANING_THRESHOLD:
            leaning_grace_frames = 0  # Reset grace period when action detected
            if not leaning_in_progress:
                leaning_in_progress = True
                leaning_recording = True
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                leaning_video = cv2.VideoWriter(temp_leaning, fourcc, fps, (frame_width, frame_height))
                
                # Write buffered frames (2 seconds BEFORE detection) for clearer proof
                print(f"\n▶️ LEANING detected! Writing {len(frame_buffer)} buffered frames (2s pre-roll)...")
                for buffered_frame in frame_buffer:
                    leaning_video.write(buffered_frame)
                print(f"   ✅ Buffer written, continuing live recording...")
        else:
            if leaning_in_progress:
                leaning_grace_frames += 1
                if leaning_grace_frames < LEANING_GRACE_PERIOD:
                    # Keep recording during grace period
                    pass
                else:
                    # Grace period expired, save and stop
                    leaning_in_progress = False
                    if leaning_recording and leaning_video:
                        leaning_video.release()
                        leaning_video = None
                        # Save to database IMMEDIATELY
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        final_filename = f"leaning_{timestamp}.mp4"
                        final_path = os.path.join(MEDIA_DIR, final_filename)
                        if os.path.exists(temp_leaning):
                            print(f"\n  💾 Grace period ended ({leaning_grace_frames} frames)")
                            print(f"  📁 Copying {os.path.basename(temp_leaning)} -> {final_filename}")
                            shutil.copy(temp_leaning, final_path)
                            print(f"  📊 Saving to database...")
                            save_video_to_database(LEANING_ACTION, final_path, lecture_hall_id)
                            detections_count['leaning'] += 1
                        else:
                            print(f"  ⚠️ Warning: {temp_leaning} not found!")
                        leaning_recording = False
                    leaning_grace_frames = 0
        
        # MOBILE
        if mobile_frames >= MOBILE_THRESHOLD:
            mobile_grace_frames = 0
            if not mobile_in_progress:
                mobile_in_progress = True
                mobile_recording = True
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                mobile_video = cv2.VideoWriter(temp_mobile, fourcc, fps, (frame_width, frame_height))
                
                # Write buffered frames (2 seconds BEFORE detection)
                print(f"\n▶️ MOBILE detected! Writing {len(frame_buffer)} buffered frames (2s pre-roll)...")
                for buffered_frame in frame_buffer:
                    mobile_video.write(buffered_frame)
                print(f"   ✅ Buffer written, continuing live recording...")
        else:
            if mobile_in_progress:
                mobile_grace_frames += 1
                if mobile_grace_frames < MOBILE_GRACE_PERIOD:
                    pass
                else:
                    mobile_in_progress = False
                    if mobile_recording and mobile_video:
                        mobile_video.release()
                        mobile_video = None
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        final_filename = f"mobile_{timestamp}.mp4"
                        final_path = os.path.join(MEDIA_DIR, final_filename)
                        if os.path.exists(temp_mobile):
                            print(f"\n  💾 Grace period ended ({mobile_grace_frames} frames)")
                            print(f"  📁 Copying {os.path.basename(temp_mobile)} -> {final_filename}")
                            shutil.copy(temp_mobile, final_path)
                            print(f"  📊 Saving to database...")
                            save_video_to_database(ACTION_MOBILE, final_path, lecture_hall_id)
                            detections_count['mobile'] += 1
                        else:
                            print(f"  ⚠️ Warning: {temp_mobile} not found!")
                        mobile_recording = False
                    mobile_grace_frames = 0
        
        # PASSING PAPER
        if passing_frames >= PASSING_THRESHOLD:
            passing_grace_frames = 0
            if not passing_in_progress:
                passing_in_progress = True
                passing_recording = True
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                passing_video = cv2.VideoWriter(temp_passing, fourcc, fps, (frame_width, frame_height))
                
                # Write buffered frames (2 seconds BEFORE detection)
                print(f"\n▶️ PASSING PAPER detected! Writing {len(frame_buffer)} buffered frames (2s pre-roll)...")
                for buffered_frame in frame_buffer:
                    passing_video.write(buffered_frame)
                print(f"   ✅ Buffer written, continuing live recording...")
        else:
            if passing_in_progress:
                passing_grace_frames += 1
                if passing_grace_frames < PASSING_GRACE_PERIOD:
                    pass
                else:
                    passing_in_progress = False
                    if passing_recording and passing_video:
                        passing_video.release()
                        passing_video = None
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        final_filename = f"passing_{timestamp}.mp4"
                        final_path = os.path.join(MEDIA_DIR, final_filename)
                        if os.path.exists(temp_passing):
                            print(f"\n  💾 Grace period ended ({passing_grace_frames} frames)")
                            print(f"  📁 Copying {os.path.basename(temp_passing)} -> {final_filename}")
                            shutil.copy(temp_passing, final_path)
                            print(f"  📊 Saving to database...")
                            save_video_to_database(PASSING_ACTION, final_path, lecture_hall_id)
                            detections_count['passing'] += 1
                        else:
                            print(f"  ⚠️ Warning: {temp_passing} not found!")
                        passing_recording = False
                    passing_grace_frames = 0
        
        # TURNING BACK
        if turning_frames >= TURNING_THRESHOLD:
            turning_grace_frames = 0
            if not turning_in_progress:
                turning_in_progress = True
                turning_recording = True
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                turning_video = cv2.VideoWriter(temp_turning, fourcc, fps, (frame_width, frame_height))
                
                # Write buffered frames (2 seconds BEFORE detection)
                print(f"\n▶️ TURNING BACK detected! Writing {len(frame_buffer)} buffered frames (2s pre-roll)...")
                for buffered_frame in frame_buffer:
                    turning_video.write(buffered_frame)
                print(f"   ✅ Buffer written, continuing live recording...")
        else:
            if turning_in_progress:
                turning_grace_frames += 1
                if turning_grace_frames < TURNING_GRACE_PERIOD:
                    pass
                else:
                    turning_in_progress = False
                    if turning_recording and turning_video:
                        turning_video.release()
                        turning_video = None
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        final_filename = f"turning_{timestamp}.mp4"
                        final_path = os.path.join(MEDIA_DIR, final_filename)
                        if os.path.exists(temp_turning):
                            print(f"\n  💾 Grace period ended ({turning_grace_frames} frames)")
                            print(f"  📁 Copying {os.path.basename(temp_turning)} -> {final_filename}")
                            shutil.copy(temp_turning, final_path)
                            print(f"  📊 Saving to database...")
                            save_video_to_database(TURNING_ACTION, final_path, lecture_hall_id)
                            detections_count['turning'] += 1
                        else:
                            print(f"  ⚠️ Warning: {temp_turning} not found!")
                        turning_recording = False
                    turning_grace_frames = 0
        
        # HAND RAISE
        if hand_raise_frames >= HAND_RAISE_THRESHOLD:
            hand_raise_grace_frames = 0
            if not hand_raise_in_progress:
                hand_raise_in_progress = True
                hand_raise_recording = True
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                hand_raise_video = cv2.VideoWriter(temp_hand_raise, fourcc, fps, (frame_width, frame_height))
                
                # Write buffered frames (2 seconds BEFORE detection)
                print(f"\n▶️ HAND RAISED detected! Writing {len(frame_buffer)} buffered frames (2s pre-roll)...")
                for buffered_frame in frame_buffer:
                    hand_raise_video.write(buffered_frame)
                print(f"   ✅ Buffer written, continuing live recording...")
        else:
            if hand_raise_in_progress:
                hand_raise_grace_frames += 1
                if hand_raise_grace_frames < HAND_RAISE_GRACE_PERIOD:
                    pass
                else:
                    hand_raise_in_progress = False
                    if hand_raise_recording and hand_raise_video:
                        hand_raise_video.release()
                        hand_raise_video = None
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        final_filename = f"hand_raise_{timestamp}.mp4"
                        final_path = os.path.join(MEDIA_DIR, final_filename)
                        if os.path.exists(temp_hand_raise):
                            print(f"\n  💾 Grace period ended ({hand_raise_grace_frames} frames)")
                            print(f"  📁 Copying {os.path.basename(temp_hand_raise)} -> {final_filename}")
                            shutil.copy(temp_hand_raise, final_path)
                            print(f"  📊 Saving to database...")
                            save_video_to_database(HAND_RAISE_ACTION, final_path, lecture_hall_id)
                            detections_count['hand_raise'] += 1
                        else:
                            print(f"  ⚠️ Warning: {temp_hand_raise} not found!")
                        hand_raise_recording = False
                    hand_raise_grace_frames = 0
        
        # Encode frame as JPEG and yield (lower quality for faster streaming)
        ret, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if ret:
            yield buffer.tobytes()
    
    print(f"\n{'='*60}")
    print(f"VIDEO ENDED - Saving any ongoing recordings...")
    print(f"{'='*60}")
    
    # CRITICAL: Save any ongoing recordings when video ends!
    # LEANING
    if leaning_in_progress and leaning_recording and leaning_video:
        print(f"\n💾 Saving incomplete LEANING recording...")
        leaning_video.release()
        leaning_video = None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"leaning_{timestamp}.mp4"
        final_path = os.path.join(MEDIA_DIR, final_filename)
        if os.path.exists(temp_leaning):
            shutil.copy(temp_leaning, final_path)
            save_video_to_database(LEANING_ACTION, final_path, lecture_hall_id)
            detections_count['leaning'] += 1
    
    # MOBILE
    if mobile_in_progress and mobile_recording and mobile_video:
        print(f"\n💾 Saving incomplete MOBILE recording...")
        mobile_video.release()
        mobile_video = None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"mobile_{timestamp}.mp4"
        final_path = os.path.join(MEDIA_DIR, final_filename)
        if os.path.exists(temp_mobile):
            shutil.copy(temp_mobile, final_path)
            save_video_to_database(ACTION_MOBILE, final_path, lecture_hall_id)
            detections_count['mobile'] += 1
    
    # PASSING PAPER
    if passing_in_progress and passing_recording and passing_video:
        print(f"\n💾 Saving incomplete PASSING PAPER recording...")
        passing_video.release()
        passing_video = None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"passing_{timestamp}.mp4"
        final_path = os.path.join(MEDIA_DIR, final_filename)
        if os.path.exists(temp_passing):
            shutil.copy(temp_passing, final_path)
            save_video_to_database(PASSING_ACTION, final_path, lecture_hall_id)
            detections_count['passing'] += 1
    
    # TURNING BACK
    if turning_in_progress and turning_recording and turning_video:
        print(f"\n💾 Saving incomplete TURNING BACK recording...")
        turning_video.release()
        turning_video = None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"turning_{timestamp}.mp4"
        final_path = os.path.join(MEDIA_DIR, final_filename)
        if os.path.exists(temp_turning):
            shutil.copy(temp_turning, final_path)
            save_video_to_database(TURNING_ACTION, final_path, lecture_hall_id)
            detections_count['turning'] += 1
    
    # HAND RAISE
    if hand_raise_in_progress and hand_raise_recording and hand_raise_video:
        print(f"\n💾 Saving incomplete HAND RAISE recording...")
        hand_raise_video.release()
        hand_raise_video = None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"hand_raise_{timestamp}.mp4"
        final_path = os.path.join(MEDIA_DIR, final_filename)
        if os.path.exists(temp_hand_raise):
            shutil.copy(temp_hand_raise, final_path)
            save_video_to_database(HAND_RAISE_ACTION, final_path, lecture_hall_id)
            detections_count['hand_raise'] += 1
    
    # Clean up - release any remaining video writers
    cap.release()
    if leaning_video:
        leaning_video.release()
    if mobile_video:
        mobile_video.release()
    if passing_video:
        passing_video.release()
    if turning_video:
        turning_video.release()
    if hand_raise_video:
        hand_raise_video.release()
    
    # Cleanup temporary video files
    for temp_file in [temp_leaning, temp_mobile, temp_passing, temp_turning, temp_hand_raise]:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                print(f"🗑️ Deleted temp file: {temp_file}")
            except:
                pass
    
    print(f"\n{'='*60}")
    print(f"✅ VIDEO PROCESSING COMPLETE")
    
    # Debug: Show max consecutive frames detected for each action
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
        print(f"      - Detections didn't reach threshold ({LEANING_THRESHOLD} frames = ~0.3 seconds)")
        print(f"      - No suspicious behavior detected in the video")
        print(f"      - Check console output above for detection attempts")
    
    print(f"{'='*60}\n")
    
    # Create completion frame to show in the video stream
    completion_frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
    completion_frame[:] = (40, 40, 40)  # Dark gray background
    
    # Main title (use SIMPLEX with thick stroke to simulate bold)
    title = "PROCESSING COMPLETE"
    title_size = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 4)[0]
    title_x = (frame_width - title_size[0]) // 2
    cv2.putText(completion_frame, title, (title_x, 100), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 4)
    
    # Draw checkmark icon
    center_x = frame_width // 2
    cv2.circle(completion_frame, (center_x, 200), 60, (0, 255, 0), 5)
    cv2.putText(completion_frame, "✓", (center_x - 30, 220), 
                cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 0), 6)
    
    # Detection summary
    y_pos = 320
    if detections_found:
        summary_title = f"📊 {total_detections} Malpractice(s) Detected & Saved"
        summary_size = cv2.getTextSize(summary_title, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)[0]
        summary_x = (frame_width - summary_size[0]) // 2
        cv2.putText(completion_frame, summary_title, (summary_x, y_pos), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        
        y_pos += 60
        # List each detection type
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
    
    # Instructions
    y_pos += 40
    instruction = "View details in Malpractice Logs section"
    instruction_size = cv2.getTextSize(instruction, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
    instruction_x = (frame_width - instruction_size[0]) // 2
    cv2.putText(completion_frame, instruction, (instruction_x, y_pos), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 200, 255), 2)
    
    # Green progress bar (100% complete)
    cv2.rectangle(completion_frame, (0, frame_height - 20), (frame_width, frame_height), (0, 255, 0), -1)
    cv2.putText(completion_frame, "Processing: 100.0% | Complete", 
               (10, frame_height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Yield completion frame for 3 seconds (simulate ~3 second display)
    for _ in range(15):  # Show completion screen for ~1.5 seconds
        ret, buffer = cv2.imencode('.jpg', completion_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            yield buffer.tobytes()
