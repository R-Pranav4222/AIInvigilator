"""
Test GPU availability in front.py context
"""
import sys
import os

print("="*60)
print("GPU DETECTION TEST")
print("="*60)

# Test 1: GPU Config Import
print("\n1. Testing GPU Config Import...")
try:
    from gpu_config import gpu_config, DEVICE, USE_HALF_PRECISION
    GPU_AVAILABLE = True
    print(f"   ✅ Import successful")
    print(f"   DEVICE: {DEVICE}")
    print(f"   GPU_AVAILABLE: {GPU_AVAILABLE}")
    print(f"   device_type: {gpu_config.device_type}")
except ImportError as e:
    print(f"   ❌ Import failed: {e}")
    GPU_AVAILABLE = False
    DEVICE = 'cpu'
    USE_HALF_PRECISION = False
except Exception as e:
    print(f"   ❌ Exception: {e}")
    GPU_AVAILABLE = False
    DEVICE = 'cpu'
    USE_HALF_PRECISION = False

# Test 2: Check variables
print("\n2. Variable Check:")
print(f"   GPU_AVAILABLE = {GPU_AVAILABLE}")
print(f"   DEVICE = {DEVICE}")

# Test 3: Display logic
print("\n3. Display Logic Test:")
try:
    device_text = "GPU" if GPU_AVAILABLE and gpu_config.device_type == 'cuda' else "CPU"
    print(f"   device_text = {device_text}")
    print(f"   Condition 1 (GPU_AVAILABLE): {GPU_AVAILABLE}")
    print(f"   Condition 2 (gpu_config.device_type == 'cuda'): {gpu_config.device_type == 'cuda'}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: YOLO Model Load
print("\n4. Testing YOLO Model Load...")
try:
    from ultralytics import YOLO
    import torch
    
    # Check if GPU available
    print(f"   torch.cuda.is_available(): {torch.cuda.is_available()}")
    
    # Try loading a model
    model = YOLO("yolo11n.pt")
    print(f"   Model loaded successfully")
    print(f"   Model device: {model.device}")
    
    # Try moving to GPU
    if GPU_AVAILABLE:
        print(f"   Moving model to {DEVICE}...")
        model.to(DEVICE)
        print(f"   Model device after .to(): {model.device}")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)
