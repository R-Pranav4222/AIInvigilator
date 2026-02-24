"""
Test Hybrid Detection - Compare Rule-Based vs ML vs Combined
Shows the power of hybrid detection!
"""

from enhanced_hybrid_detector import EnhancedHybridDetector
import cv2
from pathlib import Path

def test_hybrid_video(video_path, voting_mode='any', show_comparison=True):
    """
    Test hybrid detection on video
    
    Args:
        video_path: Path to test video
        voting_mode: 'any' (either), 'majority', 'all' (both)
        show_comparison: Show side-by-side comparison
    """
    print("\n" + "="*80)
    print("🔬 HYBRID DETECTION TEST")
    print("="*80)
    print(f"📁 Video: {video_path}")
    print(f"🗳️  Voting mode: {voting_mode.upper()}")
    print("="*80 + "\n")
    
    # Initialize hybrid detector
    detector = EnhancedHybridDetector(
        custom_model_path="runs/train/malpractice_detector/weights/best.pt",
        use_custom_model=True,
        custom_threshold=0.25,
        voting_mode=voting_mode
    )
    
    # Open video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("❌ Could not open video")
        return
    
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"📹 Video: {width}x{height}, {fps} FPS, {total_frames} frames\n")
    print("🎬 Processing... Press 'q' to quit\n")
    
    frame_count = 0
    detections_by_method = {
        'both_agree': [],
        'cv_only': [],
        'ml_only': [],
    }
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Run ML detection on full frame
        ml_detections = detector.run_full_detection(frame, conf_threshold=0.25)
        
        # Draw detections
        annotated_frame = frame.copy()
        
        # Simulate CV detection (you can integrate actual CV rules here)
        cv_detected = False  # Placeholder - integrate your CV rules
        
        # Track unique detections in this frame
        detections_text = []
        
        # Draw ML detections
        for det in ml_detections:
            x1, y1, x2, y2 = map(int, det['bbox'])
            class_name = det['class']
            conf = det['confidence']
            
            # Color based on class (matching front.py style)
            color_map = {
                'phone': (0, 0, 255),           # Red (like front.py mobile)
                'passing': (255, 0, 0),         # Blue (like front.py passing)
                'cheating': (128, 0, 128),      # Purple
                'turning_back': (255, 0, 255),  # Magenta (like front.py)
                'hand_raise': (0, 255, 255),    # Cyan (like front.py)
                'suspicious': (0, 140, 255),    # Orange
                'leaning': (0, 0, 255),         # Red (like front.py)
            }
            color = color_map.get(class_name, (255, 255, 255))
            
            # Draw box
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label on box
            label = f"{class_name} {conf:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated_frame, (x1, y1 - 20), (x1 + label_size[0], y1), color, -1)
            cv2.putText(annotated_frame, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Add to detections list (avoid duplicates)
            action_text = class_name.upper().replace('_', ' ')
            if action_text not in detections_text:
                detections_text.append((action_text, color))
        
        # Draw big detection text on right side (like front.py)
        y_offset = 100
        for action_text, color in detections_text:
            cv2.putText(annotated_frame, f"{action_text}!", (850, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)
            y_offset += 40
        
        # Add frame info
        info_text = f"Frame: {frame_count}/{total_frames} | Detections: {len(ml_detections)}"
        cv2.putText(annotated_frame, info_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Resize for display
        display_frame = annotated_frame
        if width > 1280 or height > 720:
            scale = min(1280 / width, 720 / height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            display_frame = cv2.resize(annotated_frame, (new_width, new_height))
        
        # Show frame
        cv2.imshow('Hybrid Detection', display_frame)
        
        # Handle keyboard
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        
        # Progress
        if frame_count % max(1, total_frames // 10) == 0:
            progress = (frame_count / total_frames) * 100
            print(f"   Progress: {progress:.1f}%")
    
    cap.release()
    cv2.destroyAllWindows()
    
    # Print statistics
    detector.print_stats()
    
    print("\n" + "="*80)
    print("✅ HYBRID TEST COMPLETED")
    print("="*80 + "\n")

def compare_modes():
    """Compare different voting modes on same video"""
    print("\n" + "="*80)
    print("📊 VOTING MODE COMPARISON")
    print("="*80)
    print("Testing three voting strategies:")
    print("  1. ANY: Rule-based OR ML detects (most sensitive)")
    print("  2. MAJORITY: At least one detects (balanced)")
    print("  3. ALL: Both must agree (most accurate)")
    print("="*80 + "\n")
    
    video_path = input("📁 Enter video path: ").strip().strip('"')
    if not video_path or not Path(video_path).exists():
        print("❌ Invalid video path")
        return
    
    modes = ['any', 'majority', 'all']
    results = {}
    
    for mode in modes:
        print(f"\n{'='*80}")
        print(f"🗳️  Testing mode: {mode.upper()}")
        print(f"{'='*80}\n")
        
        detector = EnhancedHybridDetector(
            custom_model_path="runs/train/malpractice_detector/weights/best.pt",
            voting_mode=mode
        )
        
        # Quick test
        cap = cv2.VideoCapture(str(video_path))
        frame_count = 0
        detections = 0
        
        while frame_count < 300:  # Test first 10 seconds
            ret, frame = cap.read()
            if not ret:
                break
            
            ml_dets = detector.run_full_detection(frame, conf_threshold=0.25)
            detections += len(ml_dets)
            frame_count += 1
        
        cap.release()
        
        results[mode] = {
            'frames': frame_count,
            'detections': detections,
            'stats': detector.get_stats()
        }
        
        print(f"✅ {mode.upper()}: {detections} detections in {frame_count} frames\n")
    
    # Summary
    print("\n" + "="*80)
    print("📊 COMPARISON SUMMARY")
    print("="*80)
    for mode, data in results.items():
        print(f"\n{mode.upper()} mode:")
        print(f"  Detections: {data['detections']}")
        print(f"  Detection rate: {data['detections']/data['frames']*100:.1f}%")
    print("="*80 + "\n")
    
    print("💡 Recommendation:")
    print("  - Use 'ANY' for testing/development (catch everything)")
    print("  - Use 'MAJORITY' for production (balanced)")
    print("  - Use 'ALL' for high-stakes exams (minimize false positives)")
    print("")

def main():
    """Main menu"""
    print("\n" + "="*80)
    print("🔬 HYBRID DETECTION TESTING SUITE")
    print("="*80)
    print("Choose test mode:")
    print("  [1] Test video with hybrid detection")
    print("  [2] Compare voting modes (ANY vs MAJORITY vs ALL)")
    print("  [3] Quick test on passing paper video")
    print("="*80)
    
    choice = input("\nChoice (1-3): ").strip()
    
    if choice == '1':
        video_path = input("\n📁 Enter video path: ").strip().strip('"')
        if video_path and Path(video_path).exists():
            mode = input("🗳️  Voting mode (any/majority/all) [any]: ").strip() or 'any'
            test_hybrid_video(video_path, voting_mode=mode)
        else:
            print("❌ Invalid video path")
    
    elif choice == '2':
        compare_modes()
    
    elif choice == '3':
        # Quick test on passing paper video
        video_path = r"E:\witcher\[1]Passing paper - Subtle.mp4"
        if Path(video_path).exists():
            print(f"\n🎯 Quick test on: {video_path}\n")
            test_hybrid_video(video_path, voting_mode='any', show_comparison=True)
        else:
            print("❌ Passing paper video not found")
            video_path = input("\n📁 Enter video path: ").strip().strip('"')
            if video_path and Path(video_path).exists():
                test_hybrid_video(video_path, voting_mode='any')
    
    else:
        print("❌ Invalid choice")

if __name__ == '__main__':
    main()
