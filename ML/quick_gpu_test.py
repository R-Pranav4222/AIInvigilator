"""
Quick GPU Test Script
Run this after PyTorch installation to verify GPU is working
"""

import torch
import time

print("\n" + "="*60)
print("QUICK GPU TEST")
print("="*60 + "\n")

# 1. Basic CUDA check
print("1. CUDA Available:", "YES ✓" if torch.cuda.is_available() else "NO ✗")

if torch.cuda.is_available():
    # 2. GPU Details
    print(f"2. GPU Name: {torch.cuda.get_device_name(0)}")
    print(f"3. CUDA Version: {torch.version.cuda}")
    
    # 3. Memory Info
    props = torch.cuda.get_device_properties(0)
    print(f"4. Total VRAM: {props.total_memory / 1e9:.2f} GB")
    
    # 4. Speed Test
    print("\n5. Running speed test...")
    
    # CPU test
    x_cpu = torch.randn(1000, 1000)
    y_cpu = torch.randn(1000, 1000)
    
    start = time.time()
    for _ in range(100):
        z_cpu = torch.matmul(x_cpu, y_cpu)
    cpu_time = time.time() - start
    print(f"   CPU: {cpu_time:.3f}s for 100 operations")
    
    # GPU test
    x_gpu = torch.randn(1000, 1000).cuda()
    y_gpu = torch.randn(1000, 1000).cuda()
    
    # Warmup
    for _ in range(10):
        z_gpu = torch.matmul(x_gpu, y_gpu)
    torch.cuda.synchronize()
    
    start = time.time()
    for _ in range(100):
        z_gpu = torch.matmul(x_gpu, y_gpu)
    torch.cuda.synchronize()
    gpu_time = time.time() - start
    print(f"   GPU: {gpu_time:.3f}s for 100 operations")
    
    speedup = cpu_time / gpu_time
    print(f"\n   🚀 GPU is {speedup:.1f}x faster than CPU!")
    
    print("\n" + "="*60)
    print("✅ GPU SETUP SUCCESSFUL - READY FOR HIGH-SPEED INFERENCE!")
    print("="*60 + "\n")
    
else:
    print("\n⚠️ GPU not available. Check installation.\n")
