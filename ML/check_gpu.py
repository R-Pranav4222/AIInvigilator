"""
GPU Availability Check Script
Run this to verify CUDA and GPU setup before running the main application
"""

import torch
import sys

def check_cuda_installation():
    """Check if CUDA is properly installed and accessible"""
    
    print("\n" + "="*70)
    print("GPU AVAILABILITY CHECK")
    print("="*70 + "\n")
    
    # 1. PyTorch version
    print(f"✓ PyTorch version: {torch.__version__}")
    
    # 2. CUDA availability
    cuda_available = torch.cuda.is_available()
    if cuda_available:
        print(f"✓ CUDA available: YES")
        print(f"✓ CUDA version: {torch.version.cuda}")
    else:
        print(f"✗ CUDA available: NO")
        print("\n⚠️  GPU acceleration not available!")
        print("   To enable GPU support:")
        print("   1. Ensure you have an NVIDIA GPU")
        print("   2. Install CUDA toolkit from: https://developer.nvidia.com/cuda-downloads")
        print("   3. Install GPU-enabled PyTorch:")
        print("      pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
        return False
    
    # 3. Number of GPUs
    gpu_count = torch.cuda.device_count()
    print(f"✓ Number of GPUs: {gpu_count}")
    
    # 4. GPU details
    print("\nGPU Details:")
    print("-" * 70)
    for i in range(gpu_count):
        print(f"\nGPU {i}:")
        print(f"  Name: {torch.cuda.get_device_name(i)}")
        props = torch.cuda.get_device_properties(i)
        print(f"  Total Memory: {props.total_memory / 1e9:.2f} GB")
        print(f"  Compute Capability: {props.major}.{props.minor}")
        print(f"  Multi-Processor Count: {props.multi_processor_count}")
    
    # 5. Test GPU operation
    print("\n" + "-" * 70)
    print("Testing GPU operations...")
    try:
        # Create a tensor on GPU
        x = torch.rand(1000, 1000).cuda()
        y = torch.rand(1000, 1000).cuda()
        z = x @ y  # Matrix multiplication on GPU
        print("✓ GPU tensor operations: SUCCESS")
        
        # Test memory allocation
        allocated = torch.cuda.memory_allocated(0) / 1e9
        reserved = torch.cuda.memory_reserved(0) / 1e9
        print(f"✓ GPU Memory - Allocated: {allocated:.3f} GB, Reserved: {reserved:.3f} GB")
        
        # Clean up
        del x, y, z
        torch.cuda.empty_cache()
        
    except Exception as e:
        print(f"✗ GPU operations failed: {e}")
        return False
    
    # 6. CuDNN status
    print(f"✓ CuDNN enabled: {torch.backends.cudnn.enabled}")
    print(f"✓ CuDNN version: {torch.backends.cudnn.version()}")
    
    # 7. Summary
    print("\n" + "="*70)
    print("🚀 GPU SETUP: READY FOR HIGH-PERFORMANCE INFERENCE!")
    print("="*70)
    print(f"\nRecommended settings for your GPU:")
    print(f"  USE_GPU=True")
    print(f"  USE_HALF_PRECISION=True")
    print(f"  CUDA_BENCHMARK=True")
    print("\nExpected performance improvement: 6-10x faster than CPU")
    print("="*70 + "\n")
    
    return True

def check_opencv_cuda():
    """Check if OpenCV has CUDA support (optional)"""
    try:
        import cv2
        print("\nOpenCV CUDA Support:")
        print("-" * 70)
        cuda_enabled = cv2.cuda.getCudaEnabledDeviceCount() > 0
        if cuda_enabled:
            print(f"✓ OpenCV built with CUDA: YES")
            print(f"✓ CUDA devices available: {cv2.cuda.getCudaEnabledDeviceCount()}")
        else:
            print("✗ OpenCV built with CUDA: NO")
            print("  (Optional - not required for YOLO GPU inference)")
    except:
        print("✗ OpenCV CUDA not available (Optional)")

def check_ultralytics_gpu():
    """Check if Ultralytics YOLO can use GPU"""
    try:
        from ultralytics import YOLO
        print("\nYOLO GPU Support:")
        print("-" * 70)
        print("✓ Ultralytics YOLO installed")
        print("  Testing YOLO model on GPU...")
        
        # Quick test with a small model
        model = YOLO('yolov8n.pt')
        model.to('cuda:0')
        print("✓ YOLO model successfully moved to GPU")
        
        return True
    except Exception as e:
        print(f"✗ YOLO GPU test failed: {e}")
        return False

if __name__ == "__main__":
    print("\n🔍 Starting GPU diagnostics...\n")
    
    # Main CUDA check
    cuda_ok = check_cuda_installation()
    
    if cuda_ok:
        # Optional checks
        check_opencv_cuda()
        check_ultralytics_gpu()
    else:
        print("\n⚠️  Your system will use CPU for inference.")
        print("   The system will still work but will be slower (5-10 FPS instead of 30-60 FPS)\n")
        sys.exit(1)
