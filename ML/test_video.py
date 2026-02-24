"""
Test Custom Malpractice Detection Model on Video File
Process exam videos and save results
"""

from ultralytics import YOLO
import cv2
from pathlib import Path
import time

# Class names for your custom model
CLASS_NAMES = [
    'phone',           # 0
    'cheat_material',  # 1
    'peeking',         # 2
    'turning_back',    # 3
    'hand_raise',      # 4
    'passing',         # 5
    'talking',         # 6
    'cheating',        # 7
    'suspicious',      # 8
    'normal'           # 9
]

def test_video(video_path, save_output=True, conf_threshold=0.3, inference_size=640, speed_mode=True):
    """
    Test model on video file
    
    Args:
        video_path: Path to video file
        save_output: Whether to save annotated video
        conf_threshold: Detection confidence threshold (0-1)
        inference_size: YOLO inference image size (640=fast, 1280=accurate)
        speed_mode: If True, process every 2nd frame for 2x speed
    """
    print("\n" + "="*80)
    print("🎬 VIDEO TEST - CUSTOM MALPRACTICE DETECTION MODEL")
    print("="*80)
    print(f"📁 Video: {video_path}")
    print(f"🎯 Model: runs/train/malpractice_detector/weights/best.pt")
    print(f"📊 Confidence threshold: {conf_threshold}")
    print(f"⚡ Inference size: {inference_size}px")
    print(f"🚀 Speed mode: {'ON (skip frames)' if speed_mode else 'OFF'}")
    print("="*80 + "\n")
    
    # Load your custom trained model
    model = YOLO('runs/train/malpractice_detector/weights/best.pt')
    
    print("✅ Model loaded successfully!")
    print(f"📊 Detecting {len(CLASS_NAMES)} classes\n")
    
    # Check if video exists
    video_file = Path(video_path)
    if not video_file.exists():
        print(f"❌ Error: Video file not found: {video_path}")
        return
    
    # Open video
    cap = cv2.VideoCapture(str(video_file))
    
    if not cap.isOpened():
        print(f"❌ Error: Could not open video file")
        return
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"📹 Video info:")
    print(f"   Resolution: {width}x{height}")
    print(f"   FPS: {fps}")
    print(f"   Total frames: {total_frames}")
    print(f"   Duration: {total_frames/fps:.1f} seconds\n")
    
    # Setup output video writer if saving
    if save_output:
        output_path = f"output_detection_{video_file.stem}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        print(f"💾 Output will be saved to: {output_path}\n")
    
    print("🎥 Processing video...")
    print("💡 Press 'q' to stop early, 's' to save current frame\n")
    
    frame_count = 0
    detection_count = 0
    detections_by_class = {name: 0 for name in CLASS_NAMES}
    start_time = time.time()
    screenshot_count = 0
    annotated_frame = None
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Speed mode: skip every other frame
        if speed_mode and frame_count % 2 == 0:
            if save_output and annotated_frame is not None:
                # Just copy previous annotated frame
                out.write(annotated_frame)
            continue
        
        # Run detection with specified inference size
        results = model(frame, conf=conf_threshold, verbose=False, imgsz=inference_size)
        
        # Draw results on frame
        annotated_frame = results[0].plot()
        
        # Count detections
        detections = results[0].boxes
        if len(detections) > 0:
            detection_count += len(detections)
            for box in detections:
                class_id = int(box.cls[0])
                if class_id < len(CLASS_NAMES):
                    detections_by_class[CLASS_NAMES[class_id]] += 1
        
        # Add progress info
        progress = (frame_count / total_frames) * 100
        cv2.putText(annotated_frame, f"Frame: {frame_count}/{total_frames} ({progress:.1f}%)", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"Detections: {len(detections)}", 
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Save frame if requested (at original resolution)
        if save_output:
            out.write(annotated_frame)
        
        # Resize frame for display if too large (fit to screen)
        display_frame = annotated_frame
        max_display_width = 1280
        max_display_height = 720
        if width > max_display_width or height > max_display_height:
            # Calculate scaling factor to fit screen
            scale_w = max_display_width / width
            scale_h = max_display_height / height
            scale = min(scale_w, scale_h)
            new_width = int(width * scale)
            new_height = int(height * scale)
            display_frame = cv2.resize(annotated_frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Display resized frame
        cv2.imshow('Malpractice Detection - Video', display_frame)
        
        # Handle keyboard
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("\n⚠️  Processing stopped by user")
            break
        elif key == ord('s'):
            screenshot_name = f'video_frame_{frame_count}.jpg'
            cv2.imwrite(screenshot_name, annotated_frame)
            print(f"📸 Frame {frame_count} saved: {screenshot_name}")
            screenshot_count += 1
        
        # Print progress every 10%
        if frame_count % max(1, total_frames // 10) == 0:
            print(f"   Progress: {progress:.1f}% ({frame_count}/{total_frames} frames)")
    
    # Calculate stats
    processing_time = time.time() - start_time
    avg_fps = frame_count / processing_time if processing_time > 0 else 0
    
    # Cleanup
    cap.release()
    if save_output:
        out.release()
    cv2.destroyAllWindows()
    
    # Print summary
    print("\n" + "="*80)
    print("✅ VIDEO PROCESSING COMPLETED")
    print("="*80)
    print(f"📊 Statistics:")
    print(f"   Frames processed: {frame_count}/{total_frames}")
    print(f"   Processing time: {processing_time:.1f} seconds")
    print(f"   Average FPS: {avg_fps:.1f}")
    print(f"   Total detections: {detection_count}")
    print(f"\n📋 Detections by class:")
    for class_name, count in sorted(detections_by_class.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"   {class_name}: {count}")
    if save_output:
        print(f"\n💾 Output saved: {output_path}")
    if screenshot_count > 0:
        print(f"📸 Screenshots saved: {screenshot_count}")
    print("="*80 + "\n")

def main():
    """Interactive video selection"""
    print("\n" + "="*80)
    print("🎬 VIDEO TEST MENU")
    print("="*80)
    print("Enter video file path (or drag & drop video file here):")
    print("Example: exam_video.mp4")
    print("="*80)
    settings
    print("\n⚡ Fast mode? (2x faster, slightly less accurate)")
    fast = input("Use fast mode? (Y/n): ").strip().lower()
    speed_mode = fast != 'n'
    
    print("\n📊 Confidence threshold (0.1-0.5, default 0.25):")
    conf_input = input("Confidence: ").strip()
    conf_threshold = 0.25
    if conf_input:
        try:
            conf_threshold = float(conf_input)
            conf_threshold = max(0.1, min(0.9, conf_threshold))
        except ValueError:
            print("⚠️  Invalid input, using default 0.25")
    
    # Run test
    test_video(video_path, save_output=True, conf_threshold=conf_threshold, 
               inference_size=640, speed_mode=speed_mode)

if __name__ == '__main__':
    main()
