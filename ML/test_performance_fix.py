"""
Quick Performance Test - Verify the Fix
Run this to confirm FPS is restored
"""

import cv2
import time
import torch
from ultralytics import YOLO

def test_model_loading():
    """Test how many models are loaded"""
    print("\n" + "="*70)
    print("🔬 MODEL LOADING TEST")
    print("="*70)
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")
    
    if device == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"Initial VRAM: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
    
    models = []
    
    # Simulate front.py loading
    print("\n1️⃣ Loading pose_model...")
    pose_model = YOLO("yolov8n-pose.pt")
    pose_model.to(device)
    models.append(('pose_model', pose_model))
    if device == 'cuda':
        print(f"   VRAM after pose: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
    
    print("\n2️⃣ Loading mobile_model...")
    mobile_model = YOLO("yolo11n.pt")
    mobile_model.to(device)
    models.append(('mobile_model', mobile_model))
    if device == 'cuda':
        print(f"   VRAM after mobile: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
    
    print("\n3️⃣ Testing LIGHTWEIGHT hybrid detector...")
    try:
        from lightweight_hybrid_detector import HybridDetector
        hybrid = HybridDetector(
            ml_model_path=None,
            pose_model_path=None,
            use_ml_verification=True,
            ml_confidence_threshold=0.25,
            device=device
        )
        if device == 'cuda':
            print(f"   VRAM after lightweight hybrid: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
        print("   ✅ Lightweight detector loaded!")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)
    if device == 'cuda':
        total_vram = torch.cuda.memory_allocated(0) / 1024**3
        print(f"Total VRAM used: {total_vram:.2f} GB")
        print(f"VRAM available: {torch.cuda.get_device_properties(0).total_memory / 1024**3 - total_vram:.2f} GB")
        
        if total_vram < 3.5:
            print("\n✅ EXCELLENT: Low memory usage, should run at 23-26 FPS")
        elif total_vram < 5.0:
            print("\n⚠️  MODERATE: Acceptable usage, should run at 15-20 FPS")
        else:
            print("\n❌ HIGH: Too much memory, might have duplicate models!")
    else:
        print("Running on CPU (slower)")
    print("="*70 + "\n")

def test_inference_speed():
    """Test inference FPS"""
    print("\n" + "="*70)
    print("⚡ INFERENCE SPEED TEST")
    print("="*70)
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    # Load lightweight hybrid
    try:
        from lightweight_hybrid_detector import HybridDetector
        hybrid = HybridDetector(
            use_ml_verification=True,
            device=device
        )
        
        # Create test frame
        import numpy as np
        test_frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
        
        # Warm up
        print("\n🔥 Warming up GPU...")
        for _ in range(5):
            detected, conf, method = hybrid.verify_detection(
                frame=test_frame,
                detection_type='passing',
                cv_detected=True
            )
        
        # Time 100 inferences
        print("⏱️  Running 100 inferences...")
        start = time.time()
        for _ in range(100):
            detected, conf, method = hybrid.verify_detection(
                frame=test_frame,
                detection_type='passing',
                cv_detected=True
            )
        elapsed = time.time() - start
        
        fps = 100 / elapsed
        
        print("\n" + "="*70)
        print("📊 RESULTS")
        print("="*70)
        print(f"Time for 100 frames: {elapsed:.2f} seconds")
        print(f"Average FPS: {fps:.1f}")
        
        if fps > 20:
            print("\n✅ EXCELLENT: Fast enough for real-time (23-26 FPS expected)")
        elif fps > 10:
            print("\n⚠️  MODERATE: Slower than expected (should be 20+ FPS)")
        else:
            print("\n❌ SLOW: Something wrong, check GPU usage")
        
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🚀 PERFORMANCE FIX VERIFICATION")
    print("="*70)
    print("This will test if the lightweight detector fixed the FPS issue")
    print("="*70)
    
    # Test 1: Model loading
    test_model_loading()
    
    # Test 2: Inference speed
    test_inference_speed()
    
    print("\n" + "="*70)
    print("✅ TESTING COMPLETE")
    print("="*70)
    print("\n💡 Next steps:")
    print("   1. If tests passed: Run front.py and check FPS")
    print("   2. If FPS still low: Check console for 'Lightweight' message")
    print("   3. Monitor GPU: nvidia-smi -l 1")
    print("\n")

if __name__ == '__main__':
    main()
