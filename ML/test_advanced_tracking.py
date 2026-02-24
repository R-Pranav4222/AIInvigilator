"""
Test Custom Model with Advanced Tracking
=========================================

This script demonstrates the complete system:
1. Person detection + tracking (YOLO11)
2. Pose analysis (YOLOv8-Pose)
3. Behavior classification (Custom trained model)
4. Temporal behavior analysis
5. Incident detection & alerts
"""

import cv2
import torch
from advanced_tracker import AdvancedBehaviorTracker
import argparse
from pathlib import Path

def test_on_video(video_path, 
                  custom_model_path=None,
                  output_path=None,
                  show_display=True,
                  save_summary=True):
    """
    Test the complete tracking system on a video
    
    Args:
        video_path: Path to input video
        custom_model_path: Path to trained custom model (optional)
        output_path: Path to save output video (optional)
        show_display: Show real-time display
        save_summary: Save tracking summary JSON
    """
    
    print("=" * 70)
    print("🎥 Advanced Behavior Tracking System - Video Test")
    print("=" * 70)
    
    # Check if video exists
    if not Path(video_path).exists():
        print(f"❌ Video not found: {video_path}")
        return
    
    print(f"\n📹 Input Video: {video_path}")
    if custom_model_path:
        print(f"🎯 Custom Model: {custom_model_path}")
    else:
        print(f"ℹ️  No custom model - using pose-based detection")
    
    # Initialize tracker
    print("\n🚀 Initializing tracker...")
    tracker = AdvancedBehaviorTracker(
        detection_model_path="yolo11n.pt",
        pose_model_path="yolov8n-pose.pt",
        custom_model_path=custom_model_path,
        device='cuda' if torch.cuda.is_available() else 'cpu',
        tracker_type='botsort',
        confidence_threshold=0.5
    )
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Could not open video: {video_path}")
        return
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"\n📊 Video Info:")
    print(f"   Resolution: {width}x{height}")
    print(f"   FPS: {fps}")
    print(f"   Total Frames: {total_frames}")
    print(f"   Duration: {total_frames/fps:.2f} seconds")
    
    # Setup video writer if output path is specified
    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        print(f"\n💾 Output will be saved to: {output_path}")
    
    print("\n▶️  Processing video... (Press 'q' to quit, 'p' to pause)\n")
    print("=" * 70)
    
    frame_count = 0
    paused = False
    
    try:
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                
                # Track and analyze
                annotated_frame, tracking_data = tracker.track_and_analyze(frame)
                
                # Print progress
                if frame_count % 30 == 0:  # Every second
                    progress = (frame_count / total_frames) * 100
                    print(f"📊 Progress: {progress:.1f}% | "
                          f"Frame: {frame_count}/{total_frames} | "
                          f"Active: {tracking_data['stats']['active_tracks']} | "
                          f"Incidents: {tracking_data['stats']['incidents_detected']}")
                
                # Write frame
                if writer:
                    writer.write(annotated_frame)
                
                # Display
                if show_display:
                    cv2.imshow('Advanced Tracking', annotated_frame)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        print("\n⏹️  Stopped by user")
                        break
                    elif key == ord('p'):
                        paused = not paused
                        print("\n⏸️  Paused" if paused else "\n▶️  Resumed")
            else:
                # Paused - just handle keyboard
                key = cv2.waitKey(100) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('p'):
                    paused = False
                    print("\n▶️  Resumed")
        
        print("\n" + "=" * 70)
        print("✅ Processing completed!")
        print("=" * 70)
        
        # Display summary
        print("\n📊 Session Summary:")
        print(f"   Frames Processed: {frame_count}")
        print(f"   Total Tracks: {tracker.stats['total_tracks']}")
        print(f"   Incidents Detected: {tracker.stats['incidents_detected']}")
        
        # Per-student summary
        print("\n👥 Individual Student Reports:")
        print("   " + "-" * 66)
        for track_id, data in tracker.get_all_trackers().items():
            duration = data['duration_seconds']
            incidents = len(data['incidents'])
            print(f"   Track #{track_id:3d} | Duration: {duration:6.1f}s | "
                  f"Incidents: {incidents} | Behavior: {data['current_behavior']}")
            
            # Show incident details
            if incidents > 0:
                for incident in data['incidents']:
                    print(f"             └─ {incident['type']} at frame {incident['start_frame']} "
                          f"(conf: {incident['confidence']:.2f})")
        
        # Save summary
        if save_summary:
            summary_path = Path(video_path).stem + "_tracking_summary.json"
            tracker.export_summary(summary_path)
            print(f"\n💾 Summary saved to: {summary_path}")
        
        print("\n" + "=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    
    finally:
        # Cleanup
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()
        print("\n🏁 Test completed")


def test_on_webcam(custom_model_path=None):
    """Test the system on webcam feed"""
    
    print("=" * 70)
    print("📹 Advanced Behavior Tracking System - Webcam Test")
    print("=" * 70)
    
    # Initialize tracker
    print("\n🚀 Initializing tracker...")
    tracker = AdvancedBehaviorTracker(
        detection_model_path="yolo11n.pt",
        pose_model_path="yolov8n-pose.pt",
        custom_model_path=custom_model_path,
        device='cuda' if torch.cuda.is_available() else 'cpu',
        tracker_type='botsort',
        confidence_threshold=0.5
    )
    
    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Could not open webcam")
        return
    
    print("\n📹 Webcam opened successfully")
    print("   Press 'q' to quit, 's' to save summary\n")
    print("=" * 70)
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Track and analyze
            annotated_frame, tracking_data = tracker.track_and_analyze(frame)
            
            # Display
            cv2.imshow('Webcam - Advanced Tracking', annotated_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                summary_path = f"webcam_summary_{tracker.frame_count}.json"
                tracker.export_summary(summary_path)
                print(f"\n💾 Summary saved to: {summary_path}")
        
        print("\n✅ Test completed")
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    
    finally:
        cap.release()
        cv2.destroyAllWindows()


def test_with_custom_model():
    """Test with trained custom model"""
    
    print("🎯 Looking for trained custom model...")
    
    # Look for trained model
    model_dir = Path("models/custom")
    if not model_dir.exists():
        print("❌ No custom model found")
        print("   Train a model first using: python train_malpractice_detector.py")
        return
    
    # Find best.pt in most recent training
    trained_models = list(model_dir.glob("*/weights/best.pt"))
    if not trained_models:
        print("❌ No trained model found")
        return
    
    # Use most recent
    latest_model = max(trained_models, key=lambda p: p.stat().st_mtime)
    print(f"✅ Found model: {latest_model}\n")
    
    # Ask for video source
    print("Select test source:")
    print("1. Test video file")
    print("2. Webcam")
    
    choice = input("\nEnter choice (1 or 2): ")
    
    if choice == "1":
        video_path = input("Enter video path: ")
        output_path = Path(video_path).stem + "_tracked.mp4"
        test_on_video(video_path, str(latest_model), output_path)
    elif choice == "2":
        test_on_webcam(str(latest_model))
    else:
        print("Invalid choice")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Test Advanced Tracking System'
    )
    parser.add_argument('--mode', type=str, default='menu',
                       choices=['menu', 'video', 'webcam', 'custom'],
                       help='Test mode')
    parser.add_argument('--video', type=str, help='Video file path')
    parser.add_argument('--model', type=str, help='Custom model path')
    parser.add_argument('--output', type=str, help='Output video path')
    parser.add_argument('--no-display', action='store_true',
                       help='Disable display (faster processing)')
    
    args = parser.parse_args()
    
    if args.mode == 'menu':
        print("\n" + "=" * 70)
        print("🎯 Advanced Behavior Tracking System - Test Menu")
        print("=" * 70)
        print("\n1. Test with video file")
        print("2. Test with webcam")
        print("3. Test with custom trained model")
        print("4. Exit")
        
        choice = input("\nEnter choice (1-4): ")
        
        if choice == "1":
            video_path = input("Enter video path: ")
            output = Path(video_path).stem + "_tracked.mp4"
            test_on_video(video_path, output_path=output)
        
        elif choice == "2":
            test_on_webcam()
        
        elif choice == "3":
            test_with_custom_model()
        
        else:
            print("Goodbye!")
    
    elif args.mode == 'video':
        if not args.video:
            print("❌ Please specify --video path")
        else:
            test_on_video(
                args.video,
                custom_model_path=args.model,
                output_path=args.output,
                show_display=not args.no_display
            )
    
    elif args.mode == 'webcam':
        test_on_webcam(custom_model_path=args.model)
    
    elif args.mode == 'custom':
        test_with_custom_model()
