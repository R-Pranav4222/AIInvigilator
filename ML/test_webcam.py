"""
Test Custom Malpractice Detection Model on Webcam
Real-time detection on webcam feed with class labels
"""

from ultralytics import YOLO
import cv2

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

def main():
    print("\n" + "="*80)
    print("📹 WEBCAM TEST - CUSTOM MALPRACTICE DETECTION MODEL")
    print("="*80)
    print("🎯 Loading model: runs/train/malpractice_detector/weights/best.pt")
    print("="*80 + "\n")
    
    # Load your custom trained model
    model = YOLO('runs/train/malpractice_detector/weights/best.pt')
    
    print("✅ Model loaded successfully!")
    print(f"📊 Detecting {len(CLASS_NAMES)} classes:")
    for i, name in enumerate(CLASS_NAMES):
        print(f"   {i}: {name}")
    
    print("\n" + "="*80)
    print("🎥 Starting webcam feed...")
    print("💡 Press 'q' to quit")
    print("💡 Press 's' to save screenshot")
    print("="*80 + "\n")
    
    # Open webcam (0 = default camera)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Error: Could not open webcam!")
        return
    
    frame_count = 0
    screenshot_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to grab frame")
            break
        
        # Run detection on frame
        results = model(frame, conf=0.3, verbose=False)
        
        # Draw results on frame
        annotated_frame = results[0].plot()
        
        # Add info overlay
        cv2.putText(annotated_frame, f"FPS: {int(cap.get(cv2.CAP_PROP_FPS))}", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(annotated_frame, "Press 'q' to quit | 's' to save", 
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Display detections info
        detections = results[0].boxes
        if len(detections) > 0:
            cv2.putText(annotated_frame, f"Detections: {len(detections)}", 
                        (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Resize for display if needed (fit to screen)
        display_frame = annotated_frame
        height, width = annotated_frame.shape[:2]
        max_width, max_height = 1280, 720
        if width > max_width or height > max_height:
            scale = min(max_width / width, max_height / height)
            new_width, new_height = int(width * scale), int(height * scale)
            display_frame = cv2.resize(annotated_frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Show frame
        cv2.imshow('Malpractice Detection - Webcam', display_frame)
        
        # Handle keyboard input
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("\n✅ Quitting...")
            break
        elif key == ord('s'):
            screenshot_name = f'webcam_detection_{screenshot_count}.jpg'
            cv2.imwrite(screenshot_name, annotated_frame)
            print(f"📸 Screenshot saved: {screenshot_name}")
            screenshot_count += 1
        
        frame_count += 1
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    
    print("\n" + "="*80)
    print(f"✅ WEBCAM TEST COMPLETED")
    print(f"📊 Total frames processed: {frame_count}")
    print(f"📸 Screenshots saved: {screenshot_count}")
    print("="*80 + "\n")

if __name__ == '__main__':
    main()
