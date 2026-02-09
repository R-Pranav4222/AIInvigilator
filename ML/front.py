# front.py
import cv2
import os
import shutil
import numpy as np
import mysql.connector
from datetime import datetime
from ultralytics import YOLO

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
POSE_MODEL_PATH = "yolov8n-pose.pt"
# Mobile model (for mobile phone detection)
MOBILE_MODEL_PATH = "yolo11n.pt"

MEDIA_DIR = "../media/"

# Thresholds for events
LEANING_THRESHOLD = 3      # consecutive frames needed for leaning
PASSING_THRESHOLD = 3      # consecutive frames needed for passing paper
MOBILE_THRESHOLD = 3       # consecutive frames needed for mobile phone detection
TURNING_THRESHOLD = 3      # consecutive frames needed for turning back
HAND_RAISE_THRESHOLD = 5   # consecutive frames needed for hand raise

# Action strings
LEANING_ACTION = "Leaning"
PASSING_ACTION = "Passing Paper"
ACTION_MOBILE = "Mobile Phone Detected"
TURNING_ACTION = "Turning Back"
HAND_RAISE_ACTION = "Hand Raised"

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
    # Sweet spot: catches back-turning without false positives on frontal faces
    is_back = eye_ratio < 0.17
    
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
    
    # Check if all required keypoints are visible
    if any(pt is None or pt[0] == 0.0 for pt in [l_shoulder, r_shoulder, l_elbow, r_elbow, l_wrist, r_wrist]):
        return False

    # Shoulder height threshold (30 pixels above shoulder)
    threshold = min(l_shoulder[1], r_shoulder[1]) + 30

    # If either wrist is above shoulder threshold, hand is raised
    if l_wrist[1] < threshold or r_wrist[1] < threshold:
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
# LOAD MODELS
# ========================
pose_model = YOLO(POSE_MODEL_PATH)
mobile_model = YOLO(MOBILE_MODEL_PATH)

# ========================
# VIDEO SOURCE
# ========================
cap = cv2.VideoCapture(CAMERA_INDEX if USE_CAMERA else VIDEO_PATH)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

# ========================
# PER-EVENT STATE VARIABLES
# ========================
# Leaning detection states
lean_in_progress = False
lean_frames = 0
lean_recording = False
lean_video = None

# Passing paper detection states
passing_in_progress = False
passing_frames = 0
passing_recording = False
passing_video = None

# Mobile phone detection states
mobile_in_progress = False
mobile_frames = 0
mobile_recording = False
mobile_video = None

# Turning back detection states
turning_in_progress = False
turning_frames = 0
turning_recording = False
turning_video = None

# Hand raise detection states
hand_raise_in_progress = False
hand_raise_frames = 0
hand_raise_recording = False
hand_raise_video = None

# ========================
# MAIN LOOP
# ========================
    
try:  
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

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
        cv2.putText(frame, hall_text, (50, FRAME_HEIGHT - 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2, cv2.LINE_AA)

        # YOLO pose inference for leaning & passing paper
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
            cv2.putText(frame, LEANING_ACTION + "!", (850, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, red_color, 3)
        if turning_this_frame:
            cv2.putText(frame, TURNING_ACTION + "!", (850, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 3)  # Magenta color
        if hand_raise_this_frame:
            cv2.putText(frame, HAND_RAISE_ACTION + "!", (850, 160),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)  # Cyan color
        if passing_this_frame:
            cv2.putText(frame, PASSING_ACTION + "!", (850, 190),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, blue_color, 3)

        # 4) Update leaning event states
        if leaning_this_frame:
            if not lean_in_progress:
                lean_in_progress = True
                lean_frames = 1
                if not lean_recording:
                    lean_recording = True
                    fourcc = cv2.VideoWriter_fourcc(*"avc1")  # H.264 codec
                    lean_video = cv2.VideoWriter("output_leaning.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
            else:
                lean_frames += 1
        else:
            if lean_in_progress:
                lean_in_progress = False
                if lean_frames >= LEANING_THRESHOLD:
                    if lean_recording and lean_video:
                        lean_video.release()
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
                    shutil.copy(local_temp, dest_path)
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
                lean_recording = False
                lean_video = None

        if lean_in_progress and lean_recording and lean_video:
            lean_video.write(frame)

        # 5) Update passing paper event states
        if passing_this_frame:
            if not passing_in_progress:
                passing_in_progress = True
                passing_frames = 1
                if not passing_recording:
                    passing_recording = True
                    fourcc = cv2.VideoWriter_fourcc(*"avc1")  # H.264 codec
                    passing_video = cv2.VideoWriter("output_passingpaper.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
            else:
                passing_frames += 1
        else:
            if passing_in_progress:
                passing_in_progress = False
                if passing_frames >= PASSING_THRESHOLD:
                    if passing_recording and passing_video:
                        passing_video.release()
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
                    shutil.copy(local_temp, dest_path)
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
                passing_recording = False
                passing_video = None

        if passing_in_progress and passing_recording and passing_video:
            passing_video.write(frame)

        # 6) Update turning back event states
        if turning_this_frame:
            if not turning_in_progress:
                turning_in_progress = True
                turning_frames = 1
                if not turning_recording:
                    turning_recording = True
                    fourcc = cv2.VideoWriter_fourcc(*"avc1")  # H.264 codec
                    turning_video = cv2.VideoWriter("output_turningback.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
            else:
                turning_frames += 1
        else:
            if turning_in_progress:
                turning_in_progress = False
                if turning_frames >= TURNING_THRESHOLD:
                    if turning_recording and turning_video:
                        turning_video.release()
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
                    shutil.copy(local_temp, dest_path)
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
                turning_recording = False
                turning_video = None

        if turning_in_progress and turning_recording and turning_video:
            turning_video.write(frame)

        # 7) Update hand raise event states
        if hand_raise_this_frame:
            if not hand_raise_in_progress:
                hand_raise_in_progress = True
                hand_raise_frames = 1
                if not hand_raise_recording:
                    hand_raise_recording = True
                    fourcc = cv2.VideoWriter_fourcc(*"avc1")  # H.264 codec
                    hand_raise_video = cv2.VideoWriter("output_handraise.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
            else:
                hand_raise_frames += 1
        else:
            if hand_raise_in_progress:
                hand_raise_in_progress = False
                if hand_raise_frames >= HAND_RAISE_THRESHOLD:
                    if hand_raise_recording and hand_raise_video:
                        hand_raise_video.release()
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
                    shutil.copy(local_temp, dest_path)
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
                hand_raise_recording = False
                hand_raise_video = None

        if hand_raise_in_progress and hand_raise_recording and hand_raise_video:
            hand_raise_video.write(frame)

        # 8) MOBILE PHONE DETECTION
        try:
            mobile_results = mobile_model(frame)
        except Exception as e:
            print("Mobile detection error:", e)
            mobile_results = []
        mobile_detected = False
        # Look through detection boxes for mobile (class 67)
        for m_res in mobile_results:
            if m_res.boxes is not None:
                for box in m_res.boxes:
                    if int(box.cls) == 67:
                        mobile_detected = True
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        # Draw orange rectangle and label for mobile detection
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0,165,255), 2)
                        cv2.putText(frame, "Mobile", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,165,255), 2)
        if mobile_detected:
            if not mobile_in_progress:
                mobile_in_progress = True
                mobile_frames = 1
                if not mobile_recording:
                    mobile_recording = True
                    fourcc = cv2.VideoWriter_fourcc(*"avc1")  # H.264 codec
                    mobile_video = cv2.VideoWriter("output_mobiledetection.mp4", fourcc, 30, (FRAME_WIDTH, FRAME_HEIGHT))
            else:
                mobile_frames += 1
            cv2.putText(frame, ACTION_MOBILE + "!", (850, 200),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0,165,255), 3)
            if mobile_recording and mobile_video:
                mobile_video.write(frame)
        else:
            if mobile_in_progress:
                mobile_in_progress = False
                if mobile_frames >= MOBILE_THRESHOLD:
                    if mobile_recording and mobile_video:
                        mobile_video.release()
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
                    shutil.copy(local_temp, dest_path)
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
                mobile_recording = False
                mobile_video = None

        # 9) Display the frame and check for quit key
        cv2.imshow("Exam Monitoring - All Actions (Leaning, Turning, Hand Raise, Passing, Mobile)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

except KeyboardInterrupt:
    print("Received keybaord interrupt; shutting down...")
 
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
    if IS_CLIENT:
        scp.close()
        ssh.close()
    cv2.destroyAllWindows()
