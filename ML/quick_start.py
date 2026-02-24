"""
Quick Start Launcher - AI Invigilator Custom Model Training
Interactive menu to guide you through the entire process
Author: AI Invigilator System
"""

import os
import sys
from pathlib import Path
import subprocess


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print application header"""
    print("\n" + "="*80)
    print(" "*20 + "🚀 AI INVIGILATOR - CUSTOM MODEL TRAINING")
    print("="*80 + "\n")


def print_menu():
    """Print main menu"""
    print("📋 MENU - Choose an option:")
    print("─"*80)
    print("  1️⃣  System Information & Time Estimation")
    print("  2️⃣  Filter Dataset (152 classes → 10 relevant classes)")
    print("  3️⃣  Train Custom Model (with auto-resume)")
    print("  4️⃣  View Training Guide")
    print("  5️⃣  Check Training Status")
    print("  6️⃣  Test Trained Model")
    print("  0️⃣  Exit")
    print("─"*80)


def run_script(script_name, description):
    """Run a Python script"""
    print(f"\n🚀 {description}")
    print("─"*80)
    
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f"❌ Error: {script_name} not found!")
        return False
    
    try:
        # Run the script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=script_path.parent
        )
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False


def check_status():
    """Check training status"""
    print("\n📊 CHECKING TRAINING STATUS")
    print("─"*80)
    
    # Check for filtered dataset
    filtered_dataset = Path('../../Dataset/custom_filtered_dataset')
    if filtered_dataset.exists():
        print("✅ Filtered Dataset: EXISTS")
        
        # Count images
        train_images = len(list((filtered_dataset / 'train' / 'images').glob('*.*')))
        valid_images = len(list((filtered_dataset / 'valid' / 'images').glob('*.*')))
        test_images = len(list((filtered_dataset / 'test' / 'images').glob('*.*')))
        
        print(f"   📁 Train: {train_images:,} images")
        print(f"   📁 Valid: {valid_images:,} images")
        print(f"   📁 Test:  {test_images:,} images")
    else:
        print("❌ Filtered Dataset: NOT CREATED")
        print("   💡 Run option 2 to filter the dataset")
    
    print()
    
    # Check for training state
    state_file = Path('checkpoints/training_state.json')
    if state_file.exists():
        import json
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        print("🔄 Training Session: IN PROGRESS")
        print(f"   Session ID: {state['session_id']}")
        print(f"   Started: {state['started_at']}")
        print(f"   Epochs: {state['completed_epochs']} completed")
        print(f"   Last Checkpoint: {state.get('last_checkpoint', 'N/A')}")
    else:
        print("⭕ Training Session: NO ACTIVE SESSION")
    
    print()
    
    # Check for trained models
    runs_dir = Path('runs/train/malpractice_detector/weights')
    if runs_dir.exists():
        best_model = runs_dir / 'best.pt'
        last_model = runs_dir / 'last.pt'
        
        if best_model.exists():
            print("✅ Trained Model: AVAILABLE")
            print(f"   📍 Best Model: {best_model}")
            print(f"   📁 Size: {best_model.stat().st_size / 1024**2:.1f} MB")
            
            if last_model.exists():
                print(f"   📍 Last Checkpoint: {last_model}")
        else:
            print("⚠️  Model training in progress or incomplete")
    else:
        print("❌ Trained Model: NOT AVAILABLE")
        print("   💡 Run option 3 to train the model")
    
    print("─"*80)


def view_guide():
    """View training guide"""
    print("\n📖 OPENING TRAINING GUIDE")
    print("─"*80)
    
    guide_path = Path(__file__).parent / 'CUSTOM_MODEL_TRAINING_GUIDE.md'
    
    if not guide_path.exists():
        print("❌ Guide not found!")
        return
    
    # Try to open with default markdown viewer
    try:
        if os.name == 'nt':  # Windows
            os.startfile(guide_path)
        elif sys.platform == 'darwin':  # macOS
            subprocess.run(['open', guide_path])
        else:  # Linux
            subprocess.run(['xdg-open', guide_path])
        
        print(f"✅ Opened: {guide_path}")
    except:
        # Fallback: print to console
        with open(guide_path, 'r', encoding='utf-8') as f:
            print(f.read())


def test_model():
    """Test trained model"""
    print("\n🔬 TEST TRAINED MODEL")
    print("─"*80)
    
    model_path = Path('runs/train/malpractice_detector/weights/best.pt')
    
    if not model_path.exists():
        print("❌ No trained model found!")
        print("   💡 Complete training first (option 3)")
        return
    
    print(f"✅ Model found: {model_path}\n")
    print("Select test source:")
    print("  1️⃣  Webcam (camera 0)")
    print("  2️⃣  Video file")
    print("  3️⃣  Image file")
    print("  0️⃣  Cancel")
    
    choice = input("\nEnter choice: ").strip()
    
    if choice == '0':
        return
    
    try:
        from ultralytics import YOLO
        model = YOLO(str(model_path))
        
        if choice == '1':
            print("\n📹 Starting webcam test...")
            print("   Press 'q' to quit")
            model.predict(source=0, show=True, conf=0.5)
            
        elif choice == '2':
            video_path = input("Enter video path: ").strip()
            if Path(video_path).exists():
                print(f"\n📹 Testing on: {video_path}")
                model.predict(source=video_path, show=True, save=True, conf=0.5)
                print(f"✅ Results saved to: runs/detect/predict")
            else:
                print("❌ Video file not found!")
                
        elif choice == '3':
            image_path = input("Enter image path: ").strip()
            if Path(image_path).exists():
                print(f"\n🖼️  Testing on: {image_path}")
                results = model.predict(source=image_path, show=True, save=True, conf=0.5)
                print(f"✅ Results saved to: runs/detect/predict")
            else:
                print("❌ Image file not found!")
        
    except ImportError:
        print("❌ ultralytics not installed!")
        print("   Run: pip install ultralytics")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def main():
    """Main application loop"""
    while True:
        clear_screen()
        print_header()
        check_status()
        print()
        print_menu()
        
        choice = input("\n👉 Enter your choice: ").strip()
        
        if choice == '1':
            run_script('estimate_processing_time.py', 'System Information & Time Estimation')
            input("\nPress Enter to continue...")
            
        elif choice == '2':
            print("\n⚠️  DATASET FILTERING")
            print("─"*80)
            print("This will filter the major-aast-dataset (152 classes)")
            print("to 10 relevant classes for malpractice detection.")
            print()
            print("Expected time: 10-30 minutes")
            print("─"*80)
            
            confirm = input("Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                run_script('filter_dataset_with_progress.py', 'Filtering Dataset')
            input("\nPress Enter to continue...")
            
        elif choice == '3':
            print("\n⚠️  MODEL TRAINING")
            print("─"*80)
            print("This will train a custom YOLO model on the filtered dataset.")
            print()
            print("Expected time: 6-12 hours (RTX 3050 6GB)")
            print("Auto-resume enabled: You can safely stop and restart anytime")
            print("─"*80)
            
            confirm = input("Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                run_script('train_with_checkpointing.py', 'Training Model')
            input("\nPress Enter to continue...")
            
        elif choice == '4':
            view_guide()
            input("\nPress Enter to continue...")
            
        elif choice == '5':
            input("\nPress Enter to continue...")
            
        elif choice == '6':
            test_model()
            input("\nPress Enter to continue...")
            
        elif choice == '0':
            print("\n👋 Goodbye!\n")
            break
        
        else:
            print("\n❌ Invalid choice! Please try again.")
            input("Press Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!\n")
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
