"""
Test ML-only detection capabilities
"""
import cv2
from ultralytics import YOLO
import torch

print("="*60)
print("TESTING ML-ONLY DETECTION")
print("="*60)

# Load the custom model
model_path = "runs/train/malpractice_detector/weights/best.pt"
print(f"\nLoading model: {model_path}")

try:
    model = YOLO(model_path)
    print("✅ Model loaded successfully")
    
    # Check device
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")
    model.to(device)
    
    # Get model class names
    print(f"\n📋 Model Classes ({len(model.names)}):")
    for idx, name in model.names.items():
        print(f"   {idx}: {name}")
    
    # Open camera
    print("\n📷 Opening camera...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Cannot open camera")
        exit(1)
    
    print("✅ Camera opened")
    print("\nRunning detection with LOW threshold (0.25)...")
    print("Press 'q' to quit\n")
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Run detection with low threshold
        results = model(frame, conf=0.25, verbose=False)
        
        # Process detections
        detections_found = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = model.names[cls_id]
                
                # Draw detection
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{class_name} {conf:.2f}", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                detections_found.append((class_name, conf))
        
        # Print detections every 30 frames
        if frame_count % 30 == 0 and detections_found:
            print(f"\n[Frame {frame_count}] Detections:")
            for class_name, conf in detections_found:
                emoji = {
                    'cheat_material': '🟠',
                    'peeking': '🟣',
                    'talking': '🟢',
                    'suspicious': '🟡',
                    'phone': '📱',
                    'passing': '📄',
                    'turning_back': '↩️',
                    'hand_raise': '✋',
                    'cheating': '❌',
                    'normal': '✅'
                }.get(class_name, '🔵')
                print(f"  {emoji} {class_name}: {conf:.2f}")
        
        # Show frame
        cv2.imshow('ML Detection Test', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
