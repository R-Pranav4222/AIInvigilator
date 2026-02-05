"""
GPU Configuration Module for AIInvigilator
Handles GPU setup, optimization, and device management
"""

import torch
import os
from pathlib import Path

# Add parent directory to path to import from app
import sys
sys.path.append(str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ python-dotenv not installed, using default values")

class GPUConfig:
    """Configure GPU settings for optimal performance"""
    
    def __init__(self):
        # Read from environment variables
        self.use_gpu = os.getenv('USE_GPU', 'True').lower() == 'true'
        self.device_id = int(os.getenv('GPU_DEVICE_ID', '0'))
        self.half_precision = os.getenv('USE_HALF_PRECISION', 'True').lower() == 'true'
        self.batch_size = int(os.getenv('BATCH_SIZE', '1'))
        self.tensorrt = os.getenv('TENSORRT_ENABLED', 'False').lower() == 'true'
        self.cuda_benchmark = os.getenv('CUDA_BENCHMARK', 'True').lower() == 'true'
        
        # Setup device
        self.device = self._setup_device()
        self.device_type = 'cuda' if 'cuda' in str(self.device) else 'cpu'
    
    def _setup_device(self):
        """Setup and configure CUDA device"""
        if not self.use_gpu or not torch.cuda.is_available():
            print("⚠️ GPU not available or disabled, using CPU")
            print("   For GPU acceleration, install: pip install torch --index-url https://download.pytorch.org/whl/cu118")
            return 'cpu'
        
        try:
            # Set the device
            device = f'cuda:{self.device_id}'
            torch.cuda.set_device(self.device_id)
            
            # Enable optimizations
            if self.cuda_benchmark:
                torch.backends.cudnn.benchmark = True
                torch.backends.cudnn.enabled = True
            
            # Print GPU info
            print("\n" + "="*60)
            print("🚀 GPU ACCELERATION ENABLED")
            print("="*60)
            print(f"   Device: {torch.cuda.get_device_name(self.device_id)}")
            print(f"   CUDA Version: {torch.version.cuda}")
            print(f"   Total Memory: {torch.cuda.get_device_properties(self.device_id).total_memory / 1e9:.2f} GB")
            print(f"   Half Precision (FP16): {'Enabled' if self.half_precision else 'Disabled'}")
            print(f"   CUDA Benchmark: {'Enabled' if self.cuda_benchmark else 'Disabled'}")
            print(f"   Batch Size: {self.batch_size}")
            print("="*60 + "\n")
            
            return device
            
        except Exception as e:
            print(f"⚠️ Error setting up GPU: {e}")
            print("   Falling back to CPU")
            return 'cpu'
    
    def get_model_kwargs(self):
        """Get kwargs for YOLO model inference"""
        kwargs = {
            'device': self.device,
            'verbose': False
        }
        
        # Add half precision only for CUDA
        if self.half_precision and self.device_type == 'cuda':
            kwargs['half'] = True
        
        return kwargs
    
    def optimize_model(self, model):
        """Optimize a YOLO model for GPU inference"""
        try:
            # Move model to device
            model.to(self.device)
            
            # Enable half precision for faster inference
            if self.half_precision and self.device_type == 'cuda':
                model.half()
                print(f"✅ Model converted to FP16 for faster inference")
            
            return model
        except Exception as e:
            print(f"⚠️ Error optimizing model: {e}")
            return model
    
    def get_memory_stats(self):
        """Get current GPU memory usage"""
        if self.device_type == 'cuda':
            return {
                'allocated': torch.cuda.memory_allocated(self.device_id) / 1e9,
                'reserved': torch.cuda.memory_reserved(self.device_id) / 1e9,
                'total': torch.cuda.get_device_properties(self.device_id).total_memory / 1e9
            }
        return {'allocated': 0, 'reserved': 0, 'total': 0}
    
    def clear_cache(self):
        """Clear GPU cache to free memory"""
        if self.device_type == 'cuda':
            torch.cuda.empty_cache()
            print("🗑️  GPU cache cleared")

# Global configuration instance
gpu_config = GPUConfig()

# Export commonly used attributes
DEVICE = gpu_config.device
USE_HALF_PRECISION = gpu_config.half_precision and gpu_config.device_type == 'cuda'

if __name__ == "__main__":
    # Test GPU configuration
    print("\nGPU Configuration Test")
    print(f"Device: {gpu_config.device}")
    print(f"Device Type: {gpu_config.device_type}")
    print(f"Half Precision: {gpu_config.half_precision}")
    
    if gpu_config.device_type == 'cuda':
        stats = gpu_config.get_memory_stats()
        print(f"\nMemory Stats:")
        print(f"  Allocated: {stats['allocated']:.2f} GB")
        print(f"  Reserved: {stats['reserved']:.2f} GB")
        print(f"  Total: {stats['total']:.2f} GB")
