"""
Time Estimation & System Benchmark Tool
Provides accurate time estimates for dataset filtering and model training
Author: AI Invigilator System
"""

import torch
import time
from pathlib import Path
from ultralytics import YOLO
import yaml
from datetime import timedelta
import platform
import psutil


class SystemBenchmark:
    """Benchmark system and estimate processing times"""
    
    def __init__(self):
        self.system_info = self.get_system_info()
        self.gpu_info = self.get_gpu_info()
    
    def get_system_info(self):
        """Get system information"""
        return {
            'platform': platform.system(),
            'processor': platform.processor(),
            'ram_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'python_version': platform.python_version(),
        }
    
    def get_gpu_info(self):
        """Get GPU information"""
        if not torch.cuda.is_available():
            return None
        
        return {
            'available': True,
            'name': torch.cuda.get_device_name(0),
            'vram_gb': round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2),
            'cuda_version': torch.version.cuda,
            'compute_capability': torch.cuda.get_device_capability(0)
        }
    
    def print_system_info(self):
        """Print system information"""
        print("\n" + "="*80)
        print("💻 SYSTEM INFORMATION")
        print("="*80)
        print(f"🖥️  Platform:     {self.system_info['platform']}")
        print(f"⚙️  Processor:    {self.system_info['processor']}")
        print(f"💾 RAM:          {self.system_info['ram_gb']} GB")
        print(f"🐍 Python:       {self.system_info['python_version']}")
        
        if self.gpu_info:
            print(f"\n🎮 GPU Information:")
            print(f"   Name:         {self.gpu_info['name']}")
            print(f"   VRAM:         {self.gpu_info['vram_gb']} GB")
            print(f"   CUDA:         {self.gpu_info['cuda_version']}")
            print(f"   Compute:      {'.'.join(map(str, self.gpu_info['compute_capability']))}")
        else:
            print(f"\n⚠️  GPU:          Not available (CPU mode)")
        
        print("="*80 + "\n")
    
    def estimate_dataset_filtering_time(self, dataset_path):
        """Estimate time for dataset filtering"""
        print("⏱️  DATASET FILTERING TIME ESTIMATE")
        print("─"*80)
        
        dataset_path = Path(dataset_path)
        
        # Count files in original dataset
        total_files = 0
        for split in ['train', 'valid', 'test']:
            split_path = dataset_path / split / 'labels'
            if split_path.exists():
                files = list(split_path.glob('*.txt'))
                total_files += len(files)
                print(f"  {split.capitalize():8s}: {len(files):,} files")
        
        print(f"  {'Total':8s}: {total_files:,} files")
        
        # Benchmark file processing speed
        print(f"\n🔬 Running benchmark...")
        
        test_split = dataset_path / 'train' / 'labels'
        test_files = list(test_split.glob('*.txt'))[:100]  # Test on 100 files
        
        start = time.time()
        for f in test_files:
            with open(f, 'r') as file:
                lines = file.readlines()
                # Simulate processing
                for line in lines:
                    parts = line.strip().split()
        elapsed = time.time() - start
        
        files_per_second = len(test_files) / elapsed
        estimated_seconds = total_files / files_per_second
        
        print(f"  Processing Speed: {files_per_second:.1f} files/second")
        print(f"  Estimated Time:   {timedelta(seconds=int(estimated_seconds))}")
        print("─"*80 + "\n")
        
        return estimated_seconds
    
    def estimate_training_time(self, dataset_yaml, model_name='yolo11n.pt', epochs=100, batch=16):
        """Estimate training time by running a quick benchmark"""
        print("⏱️  TRAINING TIME ESTIMATE")
        print("─"*80)
        
        if not self.gpu_info:
            print("⚠️  GPU not available - training will be extremely slow on CPU")
            print("   CPU Training: Not recommended (could take days)")
            print("─"*80 + "\n")
            return None
        
        # Check if dataset yaml exists
        if not Path(dataset_yaml).exists():
            print("⚠️  Filtered dataset not created yet")
            print("   📋 Run 'filter_dataset_with_progress.py' first to create the dataset")
            print("   💡 Using approximate estimates based on source dataset size...")
            print("─"*80 + "\n")
            
            # Provide rough estimate based on GPU VRAM
            if self.gpu_info['vram_gb'] <= 6:
                # RTX 3050 / RTX 2060 class
                estimated_hours = 8
            elif self.gpu_info['vram_gb'] <= 8:
                # RTX 3060 / RTX 2070 class
                estimated_hours = 6
            else:
                # RTX 3080+ class
                estimated_hours = 4
            
            estimated_total_time = estimated_hours * 3600
            print(f"  Estimated Training Time: ~{estimated_hours} hours")
            print(f"  (This is approximate - accurate estimate requires filtered dataset)")
            print("─"*80 + "\n")
            return estimated_total_time
        
        # Load dataset info
        with open(dataset_yaml, 'r') as f:
            data = yaml.safe_load(f)
        
        # Count training images
        train_path = Path(data['path']) / data['train']
        if not train_path.exists():
            train_path = Path(dataset_yaml).parent / data['train']
        
        train_images = len(list(train_path.glob('*.jpg'))) + len(list(train_path.glob('*.png')))
        
        print(f"  Model:           {model_name}")
        print(f"  Training Images: {train_images:,}")
        print(f"  Epochs:          {epochs}")
        print(f"  Batch Size:      {batch}")
        print(f"  Image Size:      640x640")
        
        print(f"\n🔬 Running benchmark (1 epoch on 10% of data)...")
        
        try:
            # Create a small benchmark
            model = YOLO(model_name)
            
            # Run 1 epoch benchmark on small subset
            start = time.time()
            results = model.train(
                data=dataset_yaml,
                epochs=1,
                imgsz=640,
                batch=batch,
                device=0,
                verbose=False,
                plots=False,
                save=False,
                fraction=0.1  # Use only 10% of data for benchmark
            )
            elapsed = time.time() - start
            
            # Estimate full training time
            # Adjust for full dataset (10x) and number of epochs
            estimated_epoch_time = elapsed * 10
            estimated_total_time = estimated_epoch_time * epochs
            
            # Add 20% overhead for validation, checkpointing, etc.
            estimated_total_time *= 1.2
            
            print(f"\n  ✅ Benchmark completed!")
            print(f"  Estimated Time per Epoch: {timedelta(seconds=int(estimated_epoch_time))}")
            print(f"  Estimated Total Time:     {timedelta(seconds=int(estimated_total_time))}")
            
            # Provide time ranges based on GPU performance
            min_time = estimated_total_time * 0.8
            max_time = estimated_total_time * 1.5
            
            print(f"\n  📊 Time Range:")
            print(f"     Best case:   {timedelta(seconds=int(min_time))}")
            print(f"     Expected:    {timedelta(seconds=int(estimated_total_time))}")
            print(f"     Worst case:  {timedelta(seconds=int(max_time))}")
            
            # Provide guidance based on GPU
            if self.gpu_info['vram_gb'] <= 6:
                print(f"\n  💡 Tips for RTX 3050 (6GB VRAM):")
                print(f"     • Batch size {batch} is optimal")
                print(f"     • Close other GPU applications")
                print(f"     • Enable power saving mode OFF")
                print(f"     • Ensure good laptop cooling")
            
            print("─"*80 + "\n")
            
            return estimated_total_time
            
        except Exception as e:
            print(f"\n  ⚠️  Benchmark failed: {str(e)}")
            print(f"  Using fallback estimates...")
            
            # Fallback estimates based on GPU specs
            if self.gpu_info['vram_gb'] <= 6:
                # RTX 3050 / RTX 2060 class
                seconds_per_image = 0.15
            elif self.gpu_info['vram_gb'] <= 8:
                # RTX 3060 / RTX 2070 class
                seconds_per_image = 0.10
            else:
                # RTX 3080+ class
                seconds_per_image = 0.05
            
            iterations = (train_images / batch) * epochs
            estimated_total_time = iterations * seconds_per_image * batch
            
            print(f"\n  Estimated Total Time: {timedelta(seconds=int(estimated_total_time))}")
            print("─"*80 + "\n")
            
            return estimated_total_time
    
    def generate_full_estimate(self, source_dataset, target_dataset, dataset_yaml, epochs=100):
        """Generate complete time estimate for the entire process"""
        print("\n" + "="*80)
        print("🎯 COMPLETE PROCESS TIME ESTIMATE")
        print("="*80 + "\n")
        
        # Dataset filtering time
        filtering_time = self.estimate_dataset_filtering_time(source_dataset)
        
        # Training time
        training_time = self.estimate_training_time(dataset_yaml, epochs=epochs)
        
        # Total time
        print("="*80)
        print("📊 TOTAL TIME ESTIMATE")
        print("="*80)
        print(f"  Dataset Filtering: {timedelta(seconds=int(filtering_time))}")
        if training_time:
            print(f"  Model Training:    {timedelta(seconds=int(training_time))}")
            total = filtering_time + training_time
            print(f"  ────────────────────────────────")
            print(f"  TOTAL:             {timedelta(seconds=int(total))}")
            
            # Break down into human-readable format
            hours = int(total // 3600)
            minutes = int((total % 3600) // 60)
            
            print(f"\n  ⏰ Human-readable: ~{hours} hours {minutes} minutes")
            
            if hours < 8:
                print(f"  💡 Recommendation: Can be completed in one session")
            elif hours < 24:
                print(f"  💡 Recommendation: Plan for {hours//8 + 1} working sessions")
            else:
                days = hours // 24
                remaining_hours = hours % 24
                print(f"  💡 Recommendation: Will take ~{days} day(s) {remaining_hours} hour(s)")
                print(f"     Consider training overnight with auto-resume enabled")
        else:
            print(f"  Model Training:    (Requires filtered dataset)")
            print(f"  ────────────────────────────────")
            print(f"  💡 Run filter_dataset_with_progress.py first, then re-run this script")
            print(f"     for accurate training time estimates")
        
        print("="*80 + "\n")
        
        print("⚠️  IMPORTANT NOTES:")
        print("─"*80)
        print("  • Estimates are approximate and may vary ±30%")
        print("  • Auto-resume is enabled for power/internet interruptions")
        print("  • Progress is saved every 5 epochs automatically")
        print("  • You can safely Ctrl+C and resume later")
        print("  • Keep laptop plugged in and well-cooled")
        print("─"*80 + "\n")


def main():
    """Main entry point"""
    print("\n" + "🔷"*40)
    print("AI INVIGILATOR - TIME ESTIMATION TOOL")
    print("🔷"*40)
    
    # Initialize benchmark
    benchmark = SystemBenchmark()
    benchmark.print_system_info()
    
    # Paths
    source_dataset = Path(r"e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8")
    target_dataset = Path(r"e:\witcher\AIINVIGILATOR\Dataset\custom_filtered_dataset")
    dataset_yaml = target_dataset / 'data.yaml'
    
    # Check if source dataset exists
    if not source_dataset.exists():
        print(f"❌ Source dataset not found: {source_dataset}")
        print(f"   Please ensure the dataset is downloaded first")
        return
    
    # Estimate times
    print("🔍 Analyzing dataset and system capabilities...\n")
    
    if dataset_yaml.exists():
        print("✅ Filtered dataset already exists")
        print(f"   Location: {target_dataset}\n")
        
        # Only estimate training time
        benchmark.estimate_training_time(str(dataset_yaml), epochs=100)
    else:
        print("📋 Filtered dataset not created yet\n")
        
        # Generate full estimate (will handle missing filtered dataset gracefully)
        benchmark.generate_full_estimate(
            source_dataset,
            target_dataset,
            str(dataset_yaml),  # Will be checked inside the function
            epochs=100
        )
    
    print("\n✅ Time estimation complete!")
    print("💡 Run 'filter_dataset_with_progress.py' to start dataset filtering")
    print("💡 Run 'train_with_checkpointing.py' to start training")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
