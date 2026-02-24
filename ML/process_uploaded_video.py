# process_uploaded_video.py
# Video processor for uploaded videos (headless mode)
import sys
import os
import cv2
import numpy as np
import mysql.connector
from datetime import datetime
import torch

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

# Thresholds
LEANING_THRESHOLD = 30
PASSING_THRESHOLD = 30
MOBILE_THRESHOLD = 30
TURNING_THRESHOLD = 30
HAND_RAISE_THRESHOLD = 30
CHEAT_THRESHOLD = 30
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


def get_lecture_hall_id(hall_name_or_id):
    """Get lecture hall ID from name or ID"""
    db = mysql.connector.connect(
        host="localhost",
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = db.cursor()
    
    try:
        # Try as ID first
        cursor.execute("SELECT id FROM app_lecturehall WHERE id = %s", (hall_name_or_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        
        # Try as name
        cursor.execute("SELECT id FROM app_lecturehall WHERE name = %s", (hall_name_or_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        
        # Default to 1
        return 1
    finally:
        cursor.close()
        db.close()


def save_to_database(action, proof_filepath, lecture_hall_id):
    """Save detection to database"""
    db = mysql.connector.connect(
        host="localhost",
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = db.cursor()
    
    try:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        
        # Extract just the filename for database
        proof_filename = os.path.basename(proof_filepath)
        
        sql = """INSERT INTO app_malpraticedetection 
                 (date, time, malpractice, proof, lecture_hall_id, verified) 
                 VALUES (%s, %s, %s, %s, %s, %s)"""
        
        cursor.execute(sql, (date_str, time_str, action, proof_filename, lecture_hall_id, False))
        db.commit()
        
        print(f"✅ DATABASE SAVED: {action} - {proof_filename}")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    finally:
        cursor.close()
        db.close()


def is_leaning(keypoints, frame_width, frame_height):
    """Check if person is leaning (rule-based)"""
    try:
        # Get nose (0), left shoulder (5), right shoulder (6)
        nose = keypoints[0]
        left_shoulder = keypoints[5]
        right_shoulder = keypoints[6]
        
        if nose[2] < 0.5 or left_shoulder[2] < 0.5 or right_shoulder[2] < 0.5:
            return False
        
        # Calculate center of shoulders
        shoulder_center_x = (left_shoulder[0] + right_shoulder[0]) / 2
        
        # Check if nose is significantly offset from shoulder center
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
        
        # Check if either wrist is above nose
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
        left_elbow = keypoints[7]
        right_elbow = keypoints[8]
        left_wrist = keypoints[9]
        right_wrist = keypoints[10]
        
        # Check if arms are extended
        valid_points = all(kp[2] > 0.5 for kp in [left_shoulder, right_shoulder, left_wrist, right_wrist])
        
        if valid_points:
            # Calculate arm extension
            left_arm_length = np.linalg.norm(np.array(left_shoulder[:2]) - np.array(left_wrist[:2]))
            right_arm_length = np.linalg.norm(np.array(right_shoulder[:2]) - np.array(right_wrist[:2]))
            shoulder_width = np.linalg.norm(np.array(left_shoulder[:2]) - np.array(right_shoulder[:2]))
            
            if shoulder_width > 0:
                # Arms extended if length > 1.5x shoulder width
                return (left_arm_length / shoulder_width > 1.5) or (right_arm_length / shoulder_width > 1.5)
        
        return False
    except:
        return False


def process_video_file(video_path, lecture_hall_id):
    """Process uploaded video file"""
    print(f"\n{'='*60}")
    print(f"🎬 VIDEO PROCESSOR STARTED")
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
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Error: Cannot open video {video_path}")
        return
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    
    print(f"📹 Video Info:")
    print(f"   FPS: {fps}")
    print(f"   Total Frames: {total_frames}")
    print(f"   Duration: {duration:.1f} seconds")
    print(f"\n▶️ Processing started...\n")
    
    # Initialize counters
    frame_count = 0
    leaning_frames = 0
    passing_frames = 0
    mobile_frames = 0
    turning_frames = 0
    hand_raise_frames = 0
    cheat_frames = 0
    peeking_frames = 0
    talking_frames = 0
    suspicious_frames = 0
    
    # Recording states
    leaning_recording = False
    passing_recording = False
    mobile_recording = False
    turning_recording = False
    hand_raise_recording = False
    cheat_recording = False
    peeking_recording = False
    talking_recording = False
    suspicious_recording = False
    
    # Video writers
    leaning_writer = None
    passing_writer = None
    mobile_writer = None
    turning_writer = None
    hand_raise_writer = None
    cheat_writer = None
    peeking_writer = None
    talking_writer = None
    suspicious_writer = None
    
    # Time-based triggers for ML-only actions (testing)
    last_trigger_time = datetime.now()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        current_time = frame_count / fps if fps > 0 else 0
        current_time_sec = int(current_time) % 20  # 20-second cycle
        
        # Progress indicator
        if frame_count % 30 == 0:  # Every second
            progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
            print(f"⏱️ Processing: {progress:.1f}% ({frame_count}/{total_frames} frames)")
        
        # Initialize detection flags
        leaning_this_frame = False
        passing_this_frame = False
        mobile_this_frame = False
        turning_this_frame = False
        hand_raise_this_frame = False
        
        # ML-only triggers (time-based for testing)
        talking_this_frame = False
        peeking_this_frame = False
        cheat_this_frame = False
        suspicious_this_frame = False
        
        # Time-based triggers (staggered every 5 seconds within 20-second cycle)
        if 5 < current_time_sec < 10:
            talking_this_frame = True
        if 10 < current_time_sec < 15:
            peeking_this_frame = True
        if 15 < current_time_sec < 20:
            cheat_this_frame = True
        if 0 < current_time_sec < 5:
            suspicious_this_frame = True
        
        # Run pose detection
        pose_results = pose_model(frame, verbose=False)
        
        for result in pose_results:
            if result.keypoints is not None and len(result.keypoints) > 0:
                for keypoints in result.keypoints.data:
                    keypoints_np = keypoints.cpu().numpy()
                    
                    # Check all behaviors
                    if is_leaning(keypoints_np, frame.shape[1], frame.shape[0]):
                        leaning_this_frame = True
                    if is_turning_back(keypoints_np):
                        turning_this_frame = True
                    if is_hand_raised(keypoints_np):
                        hand_raise_this_frame = True
                    if is_passing_paper(keypoints_np):
                        passing_this_frame = True
        
        # Run mobile detection
        mobile_results = mobile_model(frame, verbose=False)
        for result in mobile_results:
            if result.boxes is not None:
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    if class_id == MOBILE_CLASS_ID and box.conf[0] > 0.5:
                        mobile_this_frame = True
        
        # Update frame counters
        leaning_frames = leaning_frames + 1 if leaning_this_frame else 0
        passing_frames = passing_frames + 1 if passing_this_frame else 0
        mobile_frames = mobile_frames + 1 if mobile_this_frame else 0
        turning_frames = turning_frames + 1 if turning_this_frame else 0
        hand_raise_frames = hand_raise_frames + 1 if hand_raise_this_frame else 0
        cheat_frames = cheat_frames + 1 if cheat_this_frame else 0
        peeking_frames = peeking_frames + 1 if peeking_this_frame else 0
        talking_frames = talking_frames + 1 if talking_this_frame else 0
        suspicious_frames = suspicious_frames + 1 if suspicious_this_frame else 0
        
        # Handle video recording and database saves
        # Leaning
        if leaning_frames >= LEANING_THRESHOLD and not leaning_recording:
            leaning_recording = True
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"leaning_{timestamp}.mp4"
            video_filepath = os.path.join(MEDIA_DIR, video_filename)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            leaning_writer = cv2.VideoWriter(video_filepath, fourcc, fps, (frame.shape[1], frame.shape[0]))
            print(f"▶️ LEANING: Started recording")
        
        if leaning_recording:
            if leaning_writer:
                leaning_writer.write(frame)
            
            if leaning_frames == 0:  # Stopped leaning, save
                if leaning_writer:
                    leaning_writer.release()
                save_to_database(LEANING_ACTION, video_filepath, lecture_hall_id)
                leaning_recording = False
        
        # Mobile (similar pattern)
        if mobile_frames >= MOBILE_THRESHOLD and not mobile_recording:
            mobile_recording = True
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"mobile_{timestamp}.mp4"
            video_filepath = os.path.join(MEDIA_DIR, video_filename)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            mobile_writer = cv2.VideoWriter(video_filepath, fourcc, fps, (frame.shape[1], frame.shape[0]))
            print(f"▶️ MOBILE: Started recording")
        
        if mobile_recording:
            if mobile_writer:
                mobile_writer.write(frame)
            
            if mobile_frames == 0:
                if mobile_writer:
                    mobile_writer.release()
                save_to_database(ACTION_MOBILE, video_filepath, lecture_hall_id)
                mobile_recording = False
        
        # Turning back
        if turning_frames >= TURNING_THRESHOLD and not turning_recording:
            turning_recording = True
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"turning_{timestamp}.mp4"
            video_filepath = os.path.join(MEDIA_DIR, video_filename)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            turning_writer = cv2.VideoWriter(video_filepath, fourcc, fps, (frame.shape[1], frame.shape[0]))
            print(f"▶️ TURNING BACK: Started recording")
        
        if turning_recording:
            if turning_writer:
                turning_writer.write(frame)
            
            if turning_frames == 0:
                if turning_writer:
                    turning_writer.release()
                save_to_database(TURNING_ACTION, video_filepath, lecture_hall_id)
                turning_recording = False
        
        # Talking (ML-only)
        if talking_frames >= TALKING_THRESHOLD and not talking_recording:
            talking_recording = True
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"talking_{timestamp}.mp4"
            video_filepath = os.path.join(MEDIA_DIR, video_filename)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            talking_writer = cv2.VideoWriter(video_filepath, fourcc, fps, (frame.shape[1], frame.shape[0]))
            print(f"▶️ TALKING: Started recording")
        
        if talking_recording:
            if talking_writer:
                talking_writer.write(frame)
            
            if talking_frames == 0:
                if talking_writer:
                    talking_writer.release()
                save_to_database(TALKING_ACTION, video_filepath, lecture_hall_id)
                talking_recording = False
        
        # Peeking (ML-only)
        if peeking_frames >= PEEKING_THRESHOLD and not peeking_recording:
            peeking_recording = True
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"peeking_{timestamp}.mp4"
            video_filepath = os.path.join(MEDIA_DIR, video_filename)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            peeking_writer = cv2.VideoWriter(video_filepath, fourcc, fps, (frame.shape[1], frame.shape[0]))
            print(f"▶️ PEEKING: Started recording")
        
        if peeking_recording:
            if peeking_writer:
                peeking_writer.write(frame)
            
            if peeking_frames == 0:
                if peeking_writer:
                    peeking_writer.release()
                save_to_database(PEEKING_ACTION, video_filepath, lecture_hall_id)
                peeking_recording = False
    
    # Clean up
    cap.release()
    if leaning_writer:
        leaning_writer.release()
    if mobile_writer:
        mobile_writer.release()
    if turning_writer:
        turning_writer.release()
    if talking_writer:
        talking_writer.release()
    if peeking_writer:
        peeking_writer.release()
    
    print(f"\n{'='*60}")
    print(f"✅ VIDEO PROCESSING COMPLETE")
    print(f"📊 Processed {frame_count} frames")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # Test mode
    test_video = "test_videos/Leaning.mp4"
    if os.path.exists(test_video):
        process_video_file(test_video, 1)
    else:
        print(f"❌ Test video not found: {test_video}")
