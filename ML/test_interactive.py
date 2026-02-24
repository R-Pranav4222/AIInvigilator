"""
Interactive Model Testing - See All Classes in Real-Time
Test your custom model and see what it can detect
"""

from ultralytics import YOLO
import cv2
from pathlib import Path

# Class names for your custom model
CLASS_NAMES = [
    'phone',           # 0 - Using phone during exam
    'cheat_material',  # 1 - Cheat sheets, papers
    'peeking',         # 2 - Looking at others
    'turning_back',    # 3 - Turning around
    'hand_raise',      # 4 - Raising hand
    'passing',         # 5 - Passing objects
    'talking',         # 6 - Talking to others
    'cheating',        # 7 - Cheating behavior
    'suspicious',      # 8 - Suspicious activity
    'normal'           # 9 - Normal behavior
]

CLASS_COLORS = {
    'phone': (0, 0, 255),           # Red
    'cheat_material': (0, 0, 200),  # Dark Red
    'peeking': (0, 165, 255),       # Orange
    'turning_back': (0, 255, 255),  # Yellow
    'hand_raise': (0, 255, 0),      # Green
    'passing': (255, 0, 0),         # Blue
    'talking': (255, 0, 255),       # Magenta
    'cheating': (128, 0, 128),      # Purple
    'suspicious': (0, 140, 255),    # Dark Orange
    'normal': (255, 255, 255)       # White
}

def print_model_info():
    """Print model information and capabilities"""
    print("\n" + "="*80)
    print("🎯 CUSTOM MALPRACTICE DETECTION MODEL - INTERACTIVE TEST")
    print("="*80)
    print("📍 Model: runs/train/malpractice_detector/weights/best.pt")
    print("🎓 Training: 18 epochs, 159k annotations, 31.9% mAP50")
    print("="*80)
    print("\n📋 Detection Classes:")
    print("-"*80)
    for i, name in enumerate(CLASS_NAMES):
        description = {
            'phone': 'Using mobile phone',
            'cheat_material': 'Cheat sheets, papers',
            'peeking': 'Looking at neighbor\'s paper',
            'turning_back': 'Turning/looking backward',
            'hand_raise': 'Raising hand (asking question)',
            'passing': 'Passing papers/objects',
            'talking': 'Talking to others',
            'cheating': 'General cheating behavior',
            'suspicious': 'Suspicious movements',
            'normal': 'Normal exam behavior'
        }.get(name, '')
        print(f"  [{i}] {name:<18} - {description}")
    print("-"*80 + "\n")

def show_detection_stats(detections_stats):
    """Display detection statistics"""
    print("\n" + "="*80)
    print("📊 DETECTION STATISTICS")
    print("="*80)
    if sum(detections_stats.values()) == 0:
        print("   No detections yet...")
    else:
        sorted_stats = sorted(detections_stats.items(), key=lambda x: x[1], reverse=True)
        for class_name, count in sorted_stats:
            if count > 0:
                bar = '█' * min(count, 50)
                print(f"   {class_name:<18} | {bar} {count}")
    print("="*80 + "\n")

def test_source(source, source_type="webcam"):
    """
    Test model on webcam or video
    
    Args:
        source: 0 for webcam, or path to video file
        source_type: "webcam" or "video"
    """
    print_model_info()
    
    print(f"🔄 Loading model...")
    model = YOLO('runs/train/malpractice_detector/weights/best.pt')
    print("✅ Model loaded!\n")
    
    print("="*80)
    print(f"🎥 Starting {source_type} test...")
    print("="*80)
    print("💡 Controls:")
    print("   'q' - Quit")
    print("   's' - Save screenshot")
    print("   'r' - Reset statistics")
    print("   'i' - Show detection info")
    print("="*80 + "\n")
    
    # Open video source
    cap = cv2.VideoCapture(source if source_type == "webcam" else str(source))
    
    if not cap.isOpened():
        print(f"❌ Error: Could not open {source_type}")
        return
    
    frame_count = 0
    screenshot_count = 0
    detections_stats = {name: 0 for name in CLASS_NAMES}
    show_stats = False
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️  End of video or stream error")
            break
        
        # Run detection
        results = model(frame, conf=0.25, verbose=False)
        
        # Get detections
        detections = results[0].boxes
        
        # Draw results
        annotated_frame = results[0].plot()
        
        # Update statistics
        current_detections = {}
        if len(detections) > 0:
            for box in detections:
                class_id = int(box.cls[0])
                if class_id < len(CLASS_NAMES):
                    class_name = CLASS_NAMES[class_id]
                    detections_stats[class_name] += 1
                    current_detections[class_name] = current_detections.get(class_name, 0) + 1
        
        # Add overlay info
        height, width = annotated_frame.shape[:2]
        
        # Header
        cv2.rectangle(annotated_frame, (0, 0), (width, 120), (0, 0, 0), -1)
        cv2.putText(annotated_frame, "Malpractice Detection System", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"Frame: {frame_count} | Detections: {len(detections)}", 
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(annotated_frame, "q:Quit | s:Save | r:Reset | i:Info", 
                    (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Current frame detections
        if current_detections:
            y_offset = 110
            cv2.putText(annotated_frame, "Current Frame:", 
                        (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            y_offset += 20
            for class_name, count in sorted(current_detections.items()):
                color = CLASS_COLORS.get(class_name, (255, 255, 255))
                cv2.putText(annotated_frame, f"{class_name}: {count}", 
                            (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                y_offset += 20
        
        # Resize for display if needed (fit to screen)
        display_frame = annotated_frame
        max_width, max_height = 1280, 720
        if width > max_width or height > max_height:
            scale = min(max_width / width, max_height / height)
            new_width, new_height = int(width * scale), int(height * scale)
            display_frame = cv2.resize(annotated_frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Show frame
        cv2.imshow('Malpractice Detection - Interactive Test', display_frame)
        
        # Handle keyboard
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("\n✅ Quitting...")
            break
        elif key == ord('s'):
            screenshot_name = f'detection_screenshot_{screenshot_count}.jpg'
            cv2.imwrite(screenshot_name, annotated_frame)
            print(f"📸 Screenshot saved: {screenshot_name}")
            screenshot_count += 1
        elif key == ord('r'):
            detections_stats = {name: 0 for name in CLASS_NAMES}
            print("🔄 Statistics reset")
        elif key == ord('i'):
            show_detection_stats(detections_stats)
        
        frame_count += 1
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    
    # Final statistics
    print("\n" + "="*80)
    print("✅ TEST COMPLETED")
    print("="*80)
    print(f"📊 Frames processed: {frame_count}")
    print(f"📸 Screenshots saved: {screenshot_count}")
    show_detection_stats(detections_stats)

def main():
    """Interactive menu"""
    print("\n" + "="*80)
    print("🎯 INTERACTIVE MODEL TEST - MENU")
    print("="*80)
    print("Choose test mode:")
    print("  [1] Webcam (real-time)")
    print("  [2] Video file")
    print("  [3] Show model info only")
    print("="*80)
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == '1':
        test_source(0, "webcam")
    elif choice == '2':
        video_path = input("\n📁 Enter video path: ").strip().strip('"')
        if video_path and Path(video_path).exists():
            test_source(video_path, "video")
        else:
            print("❌ Invalid video path!")
    elif choice == '3':
        print_model_info()
    else:
        print("❌ Invalid choice!")

if __name__ == '__main__':
    main()
