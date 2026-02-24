"""
Hybrid Detection System Verifier
Quickly check if both rule-based CV and custom ML model are working
"""

import os
import torch
from pathlib import Path
from colorama import init, Fore, Style
init(autoreset=True)

def check_gpu():
    """Check GPU availability"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN + Style.BRIGHT}🖥️  GPU CHECK")
    print(f"{Fore.CYAN}{'='*70}")
    
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"{Fore.GREEN}✅ GPU Available: {gpu_name}")
        print(f"{Fore.GREEN}   Memory: {gpu_memory:.2f} GB")
        print(f"{Fore.GREEN}   CUDA Version: {torch.version.cuda}")
        return True
    else:
        print(f"{Fore.RED}❌ No GPU detected - will run on CPU (slower)")
        return False

def check_custom_model():
    """Check if custom trained model exists"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN + Style.BRIGHT}🤖 CUSTOM MODEL CHECK")
    print(f"{Fore.CYAN}{'='*70}")
    
    model_paths = [
        "runs/train/malpractice_detector/weights/best.pt",
        "ML/runs/train/malpractice_detector/weights/best.pt",
        "../ML/runs/train/malpractice_detector/weights/best.pt",
    ]
    
    for path in model_paths:
        if os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"{Fore.GREEN}✅ Custom model found: {path}")
            print(f"{Fore.GREEN}   Size: {size_mb:.2f} MB")
            
            # Check model info
            try:
                from ultralytics import YOLO
                model = YOLO(path)
                print(f"{Fore.GREEN}   Classes: {len(model.names)}")
                print(f"{Fore.GREEN}   Names: {', '.join(list(model.names.values())[:5])}...")
                return True
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  Model found but couldn't load: {e}")
                return False
    
    print(f"{Fore.RED}❌ Custom model not found!")
    print(f"{Fore.YELLOW}   Searched paths:")
    for path in model_paths:
        print(f"{Fore.YELLOW}   - {path}")
    return False

def check_hybrid_detector():
    """Check if hybrid detector module is available"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN + Style.BRIGHT}🔄 HYBRID DETECTOR CHECK")
    print(f"{Fore.CYAN}{'='*70}")
    
    try:
        from lightweight_hybrid_detector import HybridDetector, LightweightHybridDetector
        print(f"{Fore.GREEN}✅ Lightweight Hybrid Detector available")
        print(f"{Fore.GREEN}   Module: lightweight_hybrid_detector.py")
        print(f"{Fore.GREEN}   Classes: HybridDetector, LightweightHybridDetector")
        return True
    except ImportError as e:
        try:
            from hybrid_detector import HybridDetector
            print(f"{Fore.YELLOW}⚠️  Using old hybrid_detector (slower)")
            print(f"{Fore.YELLOW}   Recommendation: Use lightweight_hybrid_detector")
            return True
        except ImportError:
            print(f"{Fore.RED}❌ Hybrid detector not found!")
            print(f"{Fore.RED}   Error: {e}")
            return False

def check_rule_based_cv():
    """Check if CV libraries are available"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN + Style.BRIGHT}👁️  RULE-BASED CV CHECK")
    print(f"{Fore.CYAN}{'='*70}")
    
    issues = []
    
    # Check OpenCV
    try:
        import cv2
        print(f"{Fore.GREEN}✅ OpenCV: {cv2.__version__}")
    except ImportError:
        print(f"{Fore.RED}❌ OpenCV not installed")
        issues.append("opencv-python")
    
    # Check Ultralytics (YOLO)
    try:
        from ultralytics import YOLO
        print(f"{Fore.GREEN}✅ Ultralytics YOLO available")
    except ImportError:
        print(f"{Fore.RED}❌ Ultralytics not installed")
        issues.append("ultralytics")
    
    # Check NumPy
    try:
        import numpy as np
        print(f"{Fore.GREEN}✅ NumPy: {np.__version__}")
    except ImportError:
        print(f"{Fore.RED}❌ NumPy not installed")
        issues.append("numpy")
    
    if issues:
        print(f"\n{Fore.YELLOW}Install missing packages:")
        print(f"{Fore.YELLOW}   pip install {' '.join(issues)}")
        return False
    
    return True

def check_dataset_classes():
    """Check dataset configuration"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN + Style.BRIGHT}📊 DATASET CLASSES")
    print(f"{Fore.CYAN}{'='*70}")
    
    dataset_path = "../../Dataset/filtered_malpractice_dataset/data.yaml"
    
    if not os.path.exists(dataset_path):
        # Try alternate paths
        alt_paths = [
            "../Dataset/filtered_malpractice_dataset/data.yaml",
            "Dataset/filtered_malpractice_dataset/data.yaml",
        ]
        for path in alt_paths:
            if os.path.exists(path):
                dataset_path = path
                break
    
    if os.path.exists(dataset_path):
        try:
            import yaml
            with open(dataset_path, 'r') as f:
                data = yaml.safe_load(f)
            
            print(f"{Fore.GREEN}✅ Dataset config found")
            print(f"{Fore.GREEN}   Classes ({data['nc']}): {', '.join(data['names'])}")
            return True
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Dataset config found but couldn't parse: {e}")
            return False
    else:
        print(f"{Fore.YELLOW}⚠️  Dataset config not found (optional)")
        return True

def print_system_summary(gpu_ok, model_ok, hybrid_ok, cv_ok):
    """Print overall system summary"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN + Style.BRIGHT}📋 SYSTEM SUMMARY")
    print(f"{Fore.CYAN}{'='*70}\n")
    
    all_ok = gpu_ok and model_ok and hybrid_ok and cv_ok
    
    components = [
        ("GPU Acceleration", gpu_ok),
        ("Custom ML Model", model_ok),
        ("Hybrid Detector", hybrid_ok),
        ("Rule-Based CV", cv_ok),
    ]
    
    for name, status in components:
        icon = "✅" if status else "❌"
        color = Fore.GREEN if status else Fore.RED
        print(f"{color}{icon} {name:20} {'READY' if status else 'NOT READY'}")
    
    print()
    
    if all_ok:
        print(f"{Fore.GREEN + Style.BRIGHT}🎉 ALL SYSTEMS READY!")
        print(f"{Fore.GREEN}Your hybrid detection system is fully operational.\n")
        print(f"{Fore.CYAN}To start testing:")
        print(f"{Fore.WHITE}   1. Run: python front.py")
        print(f"{Fore.WHITE}   2. Look for: \"Custom model optimized (FP32) on cuda:0\"")
        print(f"{Fore.WHITE}   3. Test actions and watch for [ML✓] indicators\n")
        print(f"{Fore.CYAN}For testing guide:")
        print(f"{Fore.WHITE}   python test_actions_guide.py")
        print(f"{Fore.WHITE}   OR see: LIVE_TESTING_GUIDE.md")
    elif model_ok and hybrid_ok and cv_ok:
        print(f"{Fore.YELLOW + Style.BRIGHT}⚠️  SYSTEM READY (CPU MODE)")
        print(f"{Fore.YELLOW}GPU not available - will run slower but still work.\n")
        print(f"{Fore.CYAN}To start testing:")
        print(f"{Fore.WHITE}   python front.py")
    else:
        print(f"{Fore.RED + Style.BRIGHT}❌ SYSTEM NOT READY")
        print(f"{Fore.RED}Fix the issues above before testing.\n")
        
        if not model_ok:
            print(f"{Fore.YELLOW}To train custom model:")
            print(f"{Fore.WHITE}   python train_malpractice_detector.py")
        
        if not cv_ok:
            print(f"{Fore.YELLOW}To install dependencies:")
            print(f"{Fore.WHITE}   pip install -r requirements.txt")

def print_detectable_actions():
    """Print what actions can be detected"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN + Style.BRIGHT}🎯 DETECTABLE ACTIONS")
    print(f"{Fore.CYAN}{'='*70}\n")
    
    print(f"{Fore.GREEN}Rule-Based CV + Custom ML Model (Hybrid):")
    actions = [
        "1. Leaning",
        "2. Passing Paper",
        "3. Turning Back",
        "4. Hand Raised",
        "5. Phone/Mobile",
    ]
    for action in actions:
        print(f"{Fore.WHITE}   {action}")
    
    print(f"\n{Fore.YELLOW}Custom ML Model Only:")
    ml_actions = [
        "6. Cheat Material",
        "7. Peeking",
        "8. Talking",
        "9. Suspicious Behavior",
    ]
    for action in ml_actions:
        print(f"{Fore.WHITE}   {action}")
    
    print()

def main():
    """Main verification"""
    print(f"\n{Fore.CYAN + Style.BRIGHT}{'='*70}")
    print(f"{Fore.CYAN + Style.BRIGHT}🔍 HYBRID DETECTION SYSTEM VERIFIER")
    print(f"{Fore.CYAN + Style.BRIGHT}{'='*70}")
    
    # Run checks
    gpu_ok = check_gpu()
    model_ok = check_custom_model()
    hybrid_ok = check_hybrid_detector()
    cv_ok = check_rule_based_cv()
    check_dataset_classes()
    
    # Summary
    print_system_summary(gpu_ok, model_ok, hybrid_ok, cv_ok)
    print_detectable_actions()
    
    print(f"\n{Fore.CYAN}{'='*70}\n")

if __name__ == "__main__":
    main()
