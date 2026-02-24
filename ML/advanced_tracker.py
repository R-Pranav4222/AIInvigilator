"""
Advanced Multi-Person Tracking with Behavior Analysis
======================================================

This module tracks individual students and analyzes their behavior over time.

Features:
- 🎯 Multi-person tracking with persistent IDs
- 📊 Temporal behavior analysis (actions over time)
- 🧠 Individual student profiles
- 🚨 Smart alert system based on behavior patterns
- 📈 Confidence scoring per tracked individual

Uses:
1. YOLO11 with built-in BoT-SORT tracking (person tracking)
2. YOLOv8-Pose for pose/posture analysis
3. Optional: Custom model trained on filtered_malpractice dataset
"""

import cv2
import numpy as np
from ultralytics import YOLO
import torch
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json


class StudentTracker:
    """
    Tracks individual students and their behavior over time
    """
    
    def __init__(self, track_id):
        self.track_id = track_id
        self.first_seen = datetime.now()
        self.last_seen = datetime.now()
        self.total_frames = 0
        
        # Behavior history (stores last N detections)
        self.behavior_history = deque(maxlen=300)  # Last 10 seconds at 30fps
        
        # Malpractice incidents
        self.incidents = []
        
        # Behavior counters
        self.behavior_counts = defaultdict(int)
        
        # Current state
        self.current_behavior = "normal"
        self.suspicious_frames = 0
        
        # Confidence tracking
        self.avg_confidence = 0.0
        self.confidence_samples = []
        
    def update(self, frame_num, behavior, confidence, bbox=None):
        """Update tracker with new detection"""
        self.last_seen = datetime.now()
        self.total_frames += 1
        
        # Store behavior
        self.behavior_history.append({
            'frame': frame_num,
            'behavior': behavior,
            'confidence': confidence,
            'bbox': bbox,
            'timestamp': datetime.now()
        })
        
        # Update counters
        self.behavior_counts[behavior] += 1
        
        # Update confidence
        self.confidence_samples.append(confidence)
        if len(self.confidence_samples) > 100:
            self.confidence_samples.pop(0)
        self.avg_confidence = np.mean(self.confidence_samples)
        
        # Check for suspicious patterns
        if behavior not in ['normal', 'sitting', 'writing']:
            self.suspicious_frames += 1
        else:
            self.suspicious_frames = max(0, self.suspicious_frames - 1)
        
        self.current_behavior = behavior
        
    def detect_incident(self, threshold_frames=15):
        """
        Detect if recent behavior constitutes a malpractice incident
        
        Args:
            threshold_frames: Number of consecutive suspicious frames to trigger incident
            
        Returns:
            (bool, str): (incident_detected, behavior_type)
        """
        if self.suspicious_frames >= threshold_frames:
            return True, self.current_behavior
        return False, None
    
    def get_behavior_summary(self, recent_frames=300):
        """Get summary of recent behaviors"""
        recent = list(self.behavior_history)[-recent_frames:]
        if not recent:
            return {}
        
        summary = defaultdict(int)
        for entry in recent:
            summary[entry['behavior']] += 1
        
        # Convert to percentages
        total = len(recent)
        return {behavior: (count / total * 100) for behavior, count in summary.items()}
    
    def get_timeline(self):
        """Get complete behavior timeline"""
        return list(self.behavior_history)
    
    def to_dict(self):
        """Export tracker data as dictionary"""
        return {
            'track_id': self.track_id,
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'total_frames': self.total_frames,
            'duration_seconds': (self.last_seen - self.first_seen).total_seconds(),
            'current_behavior': self.current_behavior,
            'behavior_summary': dict(self.behavior_counts),
            'average_confidence': float(self.avg_confidence),
            'incidents': self.incidents,
            'suspicious_frames': self.suspicious_frames
        }


class AdvancedBehaviorTracker:
    """
    Advanced tracking system that combines:
    - Multi-person tracking (YOLO11 with BoT-SORT)
    - Pose estimation (YOLOv8-Pose)
    - Behavior classification (Custom model or rule-based)
    """
    
    def __init__(self, 
                 detection_model_path="yolo11n.pt",
                 pose_model_path="yolov8n-pose.pt",
                 custom_model_path=None,  # Path to model trained on filtered_malpractice
                 device='cuda' if torch.cuda.is_available() else 'cpu',
                 tracker_type='botsort',  # 'botsort' or 'bytetrack'
                 confidence_threshold=0.5):
        """
        Initialize advanced tracking system
        
        Args:
            detection_model_path: Path to YOLO detection model
            pose_model_path: Path to YOLO pose model
            custom_model_path: Path to custom trained model (optional)
            device: 'cuda' or 'cpu'
            tracker_type: 'botsort' or 'bytetrack'
            confidence_threshold: Minimum detection confidence
        """
        
        print(f"🚀 Initializing Advanced Behavior Tracker...")
        print(f"   Device: {device}")
        print(f"   Tracker: {tracker_type}")
        
        self.device = device
        self.tracker_type = tracker_type
        self.conf_threshold = confidence_threshold
        
        # Load detection model with tracking
        print(f"📦 Loading detection model: {detection_model_path}")
        self.detection_model = YOLO(detection_model_path)
        self.detection_model.to(device)
        
        # Load pose model
        print(f"🧍 Loading pose model: {pose_model_path}")
        try:
            self.pose_model = YOLO(pose_model_path)
            self.pose_model.to(device)
            self.use_pose = True
        except Exception as e:
            print(f"⚠️  Pose model not available: {e}")
            self.use_pose = False
        
        # Load custom model if provided
        if custom_model_path:
            print(f"🎯 Loading custom model: {custom_model_path}")
            try:
                self.custom_model = YOLO(custom_model_path)
                self.custom_model.to(device)
                self.use_custom = True
                print("✅ Custom model loaded - will use for behavior classification")
            except Exception as e:
                print(f"⚠️  Custom model not available: {e}")
                self.use_custom = False
        else:
            self.use_custom = False
            print("ℹ️  No custom model - using rule-based behavior detection")
        
        # Student trackers dictionary {track_id: StudentTracker}
        self.trackers = {}
        
        # Frame counter
        self.frame_count = 0
        
        # Statistics
        self.stats = {
            'total_tracks': 0,
            'active_tracks': 0,
            'incidents_detected': 0,
            'frames_processed': 0
        }
        
        print("✅ Tracker initialized!\n")
    
    def analyze_pose(self, keypoints):
        """
        Analyze pose from YOLO keypoints to detect behaviors
        
        COCO Keypoints (17 points):
        0: nose, 1-2: eyes, 3-4: ears, 5-6: shoulders,
        7-8: elbows, 9-10: wrists, 11-12: hips,
        13-14: knees, 15-16: ankles
        
        Returns:
            behavior (str): Detected behavior from pose
        """
        if keypoints is None or len(keypoints) == 0:
            return "unknown"
        
        # Extract key points
        try:
            nose = keypoints[0]
            left_shoulder = keypoints[5]
            right_shoulder = keypoints[6]
            left_wrist = keypoints[9]
            right_wrist = keypoints[10]
            
            # Hand raise detection
            if (left_wrist[1] < left_shoulder[1] - 50 or 
                right_wrist[1] < right_shoulder[1] - 50):
                return "hand_raise"
            
            # Leaning detection (shoulder tilt)
            shoulder_diff = abs(left_shoulder[1] - right_shoulder[1])
            if shoulder_diff > 30:
                return "leaning"
            
            # Turning back detection (nose position relative to shoulders)
            shoulder_center_x = (left_shoulder[0] + right_shoulder[0]) / 2
            nose_offset = abs(nose[0] - shoulder_center_x)
            shoulder_width = abs(left_shoulder[0] - right_shoulder[0])
            
            if nose_offset > shoulder_width * 0.8:
                return "turning_back"
            
            return "normal"
            
        except Exception as e:
            return "unknown"
    
    def track_and_analyze(self, frame, draw_annotations=True):
        """
        Main tracking and analysis function
        
        Args:
            frame: Video frame (BGR)
            draw_annotations: Whether to draw bounding boxes and labels
            
        Returns:
            annotated_frame: Frame with annotations
            tracking_data: Dictionary with tracking information
        """
        self.frame_count += 1
        annotated_frame = frame.copy()
        
        # Step 1: Run detection with tracking
        # persist=True enables tracking across frames
        results = self.detection_model.track(
            frame,
            persist=True,  # Enable tracking
            tracker=f"{self.tracker_type}.yaml",  # Use specified tracker
            conf=self.conf_threshold,
            device=self.device,
            verbose=False,
            classes=[0]  # Only track persons (class 0 in COCO)
        )
        
        current_tracks = []
        
        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.cpu().numpy().astype(int)
            confidences = results[0].boxes.conf.cpu().numpy()
            
            # Step 2: Process each tracked person
            for box, track_id, conf in zip(boxes, track_ids, confidences):
                x1, y1, x2, y2 = map(int, box)
                
                # Initialize tracker if new
                if track_id not in self.trackers:
                    self.trackers[track_id] = StudentTracker(track_id)
                    self.stats['total_tracks'] += 1
                    print(f"🆕 New student tracked: ID #{track_id}")
                
                tracker = self.trackers[track_id]
                
                # Extract ROI for detailed analysis
                roi = frame[y1:y2, x1:x2]
                
                # Step 3: Behavior classification
                behavior = "normal"
                behavior_conf = conf
                
                # Option A: Use custom model (if available)
                if self.use_custom:
                    custom_results = self.custom_model(roi, device=self.device, verbose=False)
                    if custom_results[0].boxes is not None and len(custom_results[0].boxes) > 0:
                        # Get highest confidence detection
                        best_idx = custom_results[0].boxes.conf.argmax()
                        behavior_conf = float(custom_results[0].boxes.conf[best_idx])
                        class_id = int(custom_results[0].boxes.cls[best_idx])
                        
                        # Map class ID to behavior name
                        # These should match your filtered_malpractice dataset classes
                        class_names = {
                            0: 'phone', 1: 'cheat_material', 2: 'peeking',
                            3: 'turning_back', 4: 'hand_raise', 5: 'passing',
                            6: 'talking', 7: 'cheating', 8: 'suspicious', 9: 'normal'
                        }
                        behavior = class_names.get(class_id, 'unknown')
                
                # Option B: Use pose analysis (if custom model not available or as supplement)
                elif self.use_pose:
                    pose_results = self.pose_model(roi, device=self.device, verbose=False)
                    if pose_results[0].keypoints is not None:
                        keypoints = pose_results[0].keypoints.xy.cpu().numpy()[0]
                        behavior = self.analyze_pose(keypoints)
                
                # Step 4: Update tracker
                tracker.update(self.frame_count, behavior, behavior_conf, box)
                
                # Step 5: Check for incidents
                incident, incident_type = tracker.detect_incident(threshold_frames=15)
                if incident:
                    if not tracker.incidents or tracker.incidents[-1]['type'] != incident_type:
                        # New incident
                        tracker.incidents.append({
                            'type': incident_type,
                            'start_frame': self.frame_count,
                            'confidence': behavior_conf,
                            'timestamp': datetime.now().isoformat()
                        })
                        self.stats['incidents_detected'] += 1
                        print(f"🚨 INCIDENT DETECTED: Track #{track_id} - {incident_type} (conf: {behavior_conf:.2f})")
                
                # Step 6: Draw annotations
                if draw_annotations:
                    # Color based on behavior
                    color = self._get_behavior_color(behavior)
                    
                    # Draw bounding box
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                    
                    # Draw label
                    label = f"ID#{track_id} | {behavior} ({behavior_conf:.2f})"
                    label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    cv2.rectangle(annotated_frame, 
                                (x1, y1 - label_size[1] - 10),
                                (x1 + label_size[0], y1),
                                color, -1)
                    cv2.putText(annotated_frame, label, 
                              (x1, y1 - 5),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    
                    # Draw incident indicator
                    if len(tracker.incidents) > 0:
                        cv2.circle(annotated_frame, (x2 - 15, y1 + 15), 10, (0, 0, 255), -1)
                
                current_tracks.append({
                    'track_id': track_id,
                    'behavior': behavior,
                    'confidence': float(behavior_conf),
                    'bbox': box.tolist(),
                    'incidents': len(tracker.incidents)
                })
        
        # Step 7: Update stats
        self.stats['active_tracks'] = len(current_tracks)
        self.stats['frames_processed'] = self.frame_count
        
        # Step 8: Draw overall statistics
        if draw_annotations:
            self._draw_stats(annotated_frame)
        
        tracking_data = {
            'frame_number': self.frame_count,
            'active_tracks': current_tracks,
            'total_incidents': self.stats['incidents_detected'],
            'stats': self.stats
        }
        
        return annotated_frame, tracking_data
    
    def _get_behavior_color(self, behavior):
        """Get color for behavior visualization"""
        colors = {
            'normal': (0, 255, 0),        # Green
            'hand_raise': (255, 255, 0),  # Yellow
            'leaning': (255, 128, 0),     # Orange
            'turning_back': (255, 0, 0),  # Red
            'phone': (0, 0, 255),         # Red
            'passing': (255, 0, 255),     # Magenta
            'peeking': (128, 0, 255),     # Purple
            'talking': (255, 128, 128),   # Pink
            'cheating': (0, 0, 128),      # Dark Red
            'suspicious': (255, 128, 0),  # Orange
        }
        return colors.get(behavior, (128, 128, 128))  # Gray for unknown
    
    def _draw_stats(self, frame):
        """Draw statistics overlay"""
        # Create semi-transparent overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (400, 120), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        # Draw text
        stats_text = [
            f"Frame: {self.frame_count}",
            f"Active Tracks: {self.stats['active_tracks']}",
            f"Total Tracks: {self.stats['total_tracks']}",
            f"Incidents: {self.stats['incidents_detected']}"
        ]
        
        y = 30
        for text in stats_text:
            cv2.putText(frame, text, (20, y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y += 25
    
    def get_tracker_data(self, track_id):
        """Get complete data for a specific tracker"""
        if track_id in self.trackers:
            return self.trackers[track_id].to_dict()
        return None
    
    def get_all_trackers(self):
        """Get data for all trackers"""
        return {tid: tracker.to_dict() for tid, tracker in self.trackers.items()}
    
    def export_summary(self, filename="tracking_summary.json"):
        """Export complete tracking summary"""
        summary = {
            'session_stats': self.stats,
            'frame_count': self.frame_count,
            'trackers': self.get_all_trackers(),
            'export_time': datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📊 Summary exported to {filename}")
        return summary


# Example usage
if __name__ == "__main__":
    print("Advanced Behavior Tracker - Example Usage\n")
    
    # Initialize tracker
    tracker = AdvancedBehaviorTracker(
        detection_model_path="yolo11n.pt",
        pose_model_path="yolov8n-pose.pt",
        custom_model_path=None,  # Set path to your trained model here
        device='cuda' if torch.cuda.is_available() else 'cpu',
        tracker_type='botsort',
        confidence_threshold=0.5
    )
    
    # Open video source
    cap = cv2.VideoCapture(0)  # Use 0 for webcam or provide video path
    
    print("🎥 Starting tracking... Press 'q' to quit\n")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Track and analyze
        annotated_frame, tracking_data = tracker.track_and_analyze(frame)
        
        # Display
        cv2.imshow('Advanced Behavior Tracking', annotated_frame)
        
        # Print incidents in real-time
        for track_info in tracking_data['active_tracks']:
            if track_info['incidents'] > 0:
                print(f"⚠️  Track #{track_info['track_id']}: {track_info['behavior']} "
                      f"(Incidents: {track_info['incidents']})")
        
        # Quit on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    
    # Export summary
    summary = tracker.export_summary("exam_tracking_summary.json")
    
    print("\n📊 Session Summary:")
    print(f"   Total Tracks: {summary['session_stats']['total_tracks']}")
    print(f"   Incidents Detected: {summary['session_stats']['incidents_detected']}")
    print(f"   Frames Processed: {summary['frame_count']}")
