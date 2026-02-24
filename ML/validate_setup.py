"""
Pre-Training Validation Script
Validates system setup before starting training
Author: AI Invigilator System
"""

import sys
import subprocess
from pathlib import Path


def print_section(title):
    """Print section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def check_python_version():
    """Check Python version"""
    print("\n🐍 Python Version:")
    version = sys.version_info
    print(f"   {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("   ❌ Python 3.8 or higher required!")
        return False
    else:
        print("   ✅ Compatible")
        return True


def check_dependencies():
    """Check required dependencies"""
    print("\n📦 Required Dependencies:")
    
    required = {
        'torch': 'PyTorch',
        'ultralytics': 'Ultralytics YOLO',
        'tqdm': 'Progress bars',
        'yaml': 'PyYAML',
        'psutil': 'System utilities',
        'pandas': 'Data processing'
    }
    
    all_installed = True
    
    for module, name in required.items():
        try:
            __import__(module)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ❌ {name} - NOT INSTALLED")
            all_installed = False
    
    return all_installed


def check_gpu():
    """Check GPU availability"""
    print("\n🎮 GPU Check:")
    
    try:
        import torch
        
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            
            print(f"   ✅ GPU Available")
            print(f"   📛 Name: {gpu_name}")
            print(f"   💾 VRAM: {vram:.1f} GB")
            
            if vram < 4:
                print(f"   ⚠️  Low VRAM - reduce batch size to 4-8")
            elif vram < 6:
                print(f"   ⚠️  Moderate VRAM - batch size 8-12 recommended")
            else:
                print(f"   ✅ Good VRAM - batch size 16+ supported")
            
            return True
        else:
            print("   ❌ GPU not available")
            print("   ⚠️  Training will be VERY slow on CPU")
            return False
            
    except ImportError:
        print("   ❌ PyTorch not installed")
        return False


def check_dataset():
    """Check dataset availability"""
    print("\n📁 Dataset Check:")
    
    # Check source dataset
    source_dataset = Path('../../Dataset/major-aast-dataset2.v1i.yolov8')
    if source_dataset.exists():
        print(f"   ✅ Source Dataset: {source_dataset.name}")
        
        # Count files
        total = 0
        for split in ['train', 'valid', 'test']:
            split_path = source_dataset / split / 'images'
            if split_path.exists():
                count = len(list(split_path.glob('*.*')))
                total += count
                print(f"      {split.capitalize():8s}: {count:,} images")
        print(f"      Total:    {total:,} images")
    else:
        print(f"   ❌ Source Dataset not found!")
        print(f"   📍 Expected: {source_dataset.absolute()}")
        return False
    
    # Check filtered dataset
    filtered_dataset = Path('../../Dataset/custom_filtered_dataset')
    if filtered_dataset.exists():
        print(f"\n   ✅ Filtered Dataset: {filtered_dataset.name}")
        print(f"   💡 Dataset already filtered - ready for training!")
    else:
        print(f"\n   ℹ️  Filtered Dataset: Not created yet")
        print(f"   💡 Run 'filter_dataset_with_progress.py' to create it")
    
    return True


def check_disk_space():
    """Check available disk space"""
    print("\n💾 Disk Space:")
    
    try:
        import psutil
        
        # Check current drive
        current_drive = Path.cwd().anchor
        usage = psutil.disk_usage(current_drive)
        
        free_gb = usage.free / 1024**3
        total_gb = usage.total / 1024**3
        used_percent = usage.percent
        
        print(f"   Drive: {current_drive}")
        print(f"   Free: {free_gb:.1f} GB / {total_gb:.1f} GB ({100-used_percent:.1f}% available)")
        
        if free_gb < 10:
            print(f"   ❌ Low disk space! At least 50GB recommended")
            return False
        elif free_gb < 30:
            print(f"   ⚠️  Limited disk space - monitoring recommended")
            return True
        else:
            print(f"   ✅ Sufficient disk space")
            return True
            
    except ImportError:
        print("   ⚠️  Cannot check (psutil not installed)")
        return True


def check_config():
    """Check configuration files"""
    print("\n⚙️  Configuration Files:")
    
    config_file = Path('training_config.yaml')
    if config_file.exists():
        print(f"   ✅ {config_file.name}")
    else:
        print(f"   ⚠️  {config_file.name} not found (will be created)")
    
    return True


def install_missing_dependencies():
    """Offer to install missing dependencies"""
    print("\n📦 Installing Missing Dependencies:")
    print("─"*70)
    
    response = input("Install missing packages now? (y/n): ").strip().lower()
    
    if response == 'y':
        print("\nInstalling...")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install',
                'torch', 'torchvision', 'ultralytics', 
                'tqdm', 'PyYAML', 'psutil', 'pandas'
            ])
            print("\n✅ Dependencies installed successfully!")
            return True
        except subprocess.CalledProcessError:
            print("\n❌ Installation failed!")
            print("   Try manually: pip install -r requirements.txt")
            return False
    
    return False


def main():
    """Main validation"""
    print("\n" + "🔷"*35)
    print("  AI INVIGILATOR - PRE-TRAINING VALIDATION")
    print("🔷"*35)
    
    print_section("SYSTEM VALIDATION")
    
    checks = {
        'Python Version': check_python_version(),
        'Dependencies': check_dependencies(),
        'GPU': check_gpu(),
        'Dataset': check_dataset(),
        'Disk Space': check_disk_space(),
        'Configuration': check_config()
    }
    
    print_section("VALIDATION SUMMARY")
    
    print()
    passed = 0
    failed = 0
    
    for check_name, result in checks.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {check_name:20s}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n  Total: {passed} passed, {failed} failed")
    print("="*70)
    
    # Recommendations
    if failed > 0:
        print("\n⚠️  RECOMMENDATIONS:")
        print("─"*70)
        
        if not checks['Python Version']:
            print("  • Upgrade Python to 3.8 or higher")
        
        if not checks['Dependencies']:
            print("  • Install missing dependencies:")
            print("    pip install -r requirements.txt")
            install_missing_dependencies()
        
        if not checks['GPU']:
            print("  • Install CUDA and PyTorch with GPU support")
            print("    Visit: https://pytorch.org/get-started/locally/")
        
        if not checks['Dataset']:
            print("  • Download the major-aast-dataset from Roboflow")
            print("  • Extract to: Dataset/major-aast-dataset2.v1i.yolov8/")
        
        if not checks['Disk Space']:
            print("  • Free up disk space (50GB+ recommended)")
        
        print("─"*70)
        print("\n❌ System not ready for training!")
        print("   Fix the issues above and run this script again.\n")
        
    else:
        print("\n✅ SYSTEM READY!")
        print("─"*70)
        print("  Your system is properly configured for training.")
        print()
        print("  Next steps:")
        print("  1️⃣  Run: python estimate_processing_time.py")
        print("  2️⃣  Run: python filter_dataset_with_progress.py")
        print("  3️⃣  Run: python train_with_checkpointing.py")
        print()
        print("  Or use the quick start launcher:")
        print("  🚀 Run: python quick_start.py")
        print("─"*70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user\n")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
