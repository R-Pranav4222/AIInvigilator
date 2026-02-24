"""
Train Custom YOLO Model on Filtered Malpractice Dataset
========================================================

This script trains a YOLO11 model on your filtered_malpractice dataset.

Dataset: 50,286 training images, 19,022 validation images
Classes: phone, cheat_material, peeking, turning_back, hand_raise, 
         passing, talking, cheating, suspicious, normal

Expected Training Time (with GPU):
- YOLO11n (nano): 2-3 hours
- YOLO11s (small): 3-4 hours  
- YOLO11m (medium): 4-6 hours
"""

import torch
from ultralytics import YOLO
import os
from pathlib import Path
import yaml

def train_malpractice_detector(
    data_yaml_path="../../Dataset/filtered_malpractice_dataset/data.yaml",
    model_size='n',  # 'n' (nano), 's' (small), 'm' (medium), 'l' (large)
    epochs=50,
    imgsz=640,
    batch_size=-1,  # Auto batch size
    device='cuda' if torch.cuda.is_available() else 'cpu',
    project='models/custom',
    name='malpractice_detector',
    resume=False,
    pretrained=True
):
    """
    Train YOLO model on filtered_malpractice dataset
    
    Args:
        data_yaml_path: Path to data.yaml file
        model_size: 'n', 's', 'm', 'l', or 'x' (nano to extra-large)
        epochs: Number of training epochs
        imgsz: Image size for training
        batch_size: Batch size (-1 for auto)
        device: 'cuda' or 'cpu'
        project: Project directory for results
        name: Experiment name
        resume: Resume from last checkpoint
        pretrained: Start from pre-trained COCO weights
    """
    
    print("=" * 60)
    print("🎯 YOLO11 Training on Filtered Malpractice Dataset")
    print("=" * 60)
    
    # Check if dataset exists
    data_path = Path(data_yaml_path)
    if not data_path.exists():
        print(f"❌ Dataset not found: {data_yaml_path}")
        print(f"   Please check if the path is correct")
        return
    
    # Load and display dataset info
    with open(data_path, 'r') as f:
        data_config = yaml.safe_load(f)
    
    print("\n📦 Dataset Configuration:")
    print(f"   Classes: {data_config['nc']}")
    print(f"   Names: {data_config['names']}")
    print(f"   Training data: {data_config['train']}")
    print(f"   Validation data: {data_config['val']}")
    
    # Check device
    print(f"\n🖥️  Device: {device}")
    if device == 'cuda':
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
        print(f"   Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    else:
        print("   ⚠️  Training on CPU will be VERY slow")
        print("   Recommend using GPU for faster training")
    
    # Select model
    model_name = f"yolo11{model_size}.pt"
    print(f"\n🤖 Model: {model_name}")
    
    model_info = {
        'n': '3.2M params - Fastest, good for real-time',
        's': '9.4M params - Balanced speed/accuracy',
        'm': '20.1M params - Higher accuracy',
        'l': '25.3M params - Best accuracy',
        'x': '56.9M params - Maximum accuracy (slow)'
    }
    print(f"   {model_info.get(model_size, 'Unknown')}")
    
    # Initialize model
    if pretrained:
        print(f"\n📥 Loading pre-trained YOLO11{model_size.upper()} weights...")
        model = YOLO(model_name)
        print("   ✅ Starting from COCO pre-trained weights (Transfer Learning)")
        print("   This will train much faster and achieve better accuracy!")
    else:
        print(f"\n📥 Training from scratch...")
        model = YOLO(f"yolo11{model_size}.yaml")
        print("   ⚠️  Training from scratch takes longer and needs more data")
    
    # Training configuration
    print("\n⚙️  Training Configuration:")
    print(f"   Epochs: {epochs}")
    print(f"   Image size: {imgsz}x{imgsz}")
    print(f"   Batch size: {batch_size if batch_size != -1 else 'Auto'}")
    print(f"   Project: {project}")
    print(f"   Name: {name}")
    
    # Estimate training time
    dataset_size = 50286  # Training images
    if device == 'cuda':
        batches_per_epoch = dataset_size / (16 if batch_size == -1 else batch_size)
        time_per_epoch_min = batches_per_epoch * 0.3 / 60  # ~0.3s per batch
        total_time_hours = time_per_epoch_min * epochs / 60
        print(f"\n⏱️  Estimated Training Time: ~{total_time_hours:.1f} hours")
    else:
        print(f"\n⏱️  Estimated Training Time: ~3-5x longer on CPU")
    
    # Confirmation
    print("\n" + "=" * 60)
    response = input("Start training? (y/n): ")
    if response.lower() != 'y':
        print("Training cancelled")
        return
    
    print("\n🚀 Starting training...\n")
    print("=" * 60)
    
    try:
        # Train model
        results = model.train(
            data=str(data_path),
            epochs=epochs,
            imgsz=imgsz,
            batch=batch_size,
            device=device,
            project=project,
            name=name,
            resume=resume,
            
            # Optimization settings
            patience=10,  # Early stopping patience
            save=True,    # Save checkpoints
            save_period=5,  # Save every N epochs
            
            # Data augmentation (helps with variety)
            augment=True,
            hsv_h=0.015,  # Image HSV-Hue augmentation
            hsv_s=0.7,    # Image HSV-Saturation augmentation
            hsv_v=0.4,    # Image HSV-Value augmentation
            degrees=10,   # Image rotation (+/- deg)
            translate=0.1,  # Image translation (+/- fraction)
            scale=0.5,    # Image scale (+/- gain)
            fliplr=0.5,   # Image flip left-right (probability)
            
            # Performance
            workers=8,    # Number of worker threads
            amp=True,     # Automatic Mixed Precision training
            
            # Validation
            val=True,     # Validate during training
            plots=True,   # Save plots
            
            # Verbose
            verbose=True
        )
        
        print("\n" + "=" * 60)
        print("✅ TRAINING COMPLETED!")
        print("=" * 60)
        
        # Display results
        print(f"\n📊 Final Results:")
        print(f"   Best Model: {results.save_dir / 'weights' / 'best.pt'}")
        print(f"   Last Model: {results.save_dir / 'weights' / 'last.pt'}")
        
        # Metrics
        if hasattr(results, 'results_dict'):
            metrics = results.results_dict
            print(f"\n📈 Performance Metrics:")
            print(f"   mAP50: {metrics.get('metrics/mAP50(B)', 'N/A')}")
            print(f"   mAP50-95: {metrics.get('metrics/mAP50-95(B)', 'N/A')}")
            print(f"   Precision: {metrics.get('metrics/precision(B)', 'N/A')}")
            print(f"   Recall: {metrics.get('metrics/recall(B)', 'N/A')}")
        
        # Validation on test set
        print(f"\n🧪 Running validation on test set...")
        val_results = model.val(data=str(data_path), split='test')
        
        print(f"\n📋 Test Set Results:")
        print(f"   mAP50: {val_results.box.map50:.4f}")
        print(f"   mAP50-95: {val_results.box.map:.4f}")
        
        # Class-wise performance
        print(f"\n📊 Per-Class Performance:")
        for i, class_name in enumerate(data_config['names']):
            if i < len(val_results.box.ap_class_index):
                ap = val_results.box.ap50[i]
                print(f"   {class_name:20s}: {ap:.4f}")
        
        print("\n" + "=" * 60)
        print("🎉 Training pipeline completed successfully!")
        print("=" * 60)
        
        print(f"\n💡 Next Steps:")
        print(f"   1. Review training plots in: {results.save_dir}")
        print(f"   2. Test model with: test_custom_model.py")
        print(f"   3. Integrate with: advanced_tracker.py")
        print(f"   4. Deploy to production system")
        
        return results
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Training interrupted by user")
        print("   You can resume training by setting resume=True")
        
    except Exception as e:
        print(f"\n\n❌ Training failed with error:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()


def quick_train():
    """Quick training with recommended settings"""
    print("🎯 Quick Training Mode - Recommended Settings\n")
    
    train_malpractice_detector(
        data_yaml_path="../../Dataset/filtered_malpractice_dataset/data.yaml",
        model_size='n',  # Nano - fastest for real-time
        epochs=50,       # Good balance
        imgsz=640,       # Standard size
        batch_size=-1,   # Auto batch
        device='cuda' if torch.cuda.is_available() else 'cpu',
        project='models/custom',
        name='malpractice_detector_v1',
        pretrained=True  # Transfer learning
    )


def high_accuracy_train():
    """Training for maximum accuracy"""
    print("🎯 High Accuracy Training Mode\n")
    
    train_malpractice_detector(
        data_yaml_path="../../Dataset/filtered_malpractice_dataset/data.yaml",
        model_size='m',  # Medium - better accuracy
        epochs=100,      # More epochs
        imgsz=640,
        batch_size=-1,
        device='cuda' if torch.cuda.is_available() else 'cpu',
        project='models/custom',
        name='malpractice_detector_high_acc',
        pretrained=True
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Train YOLO11 on Filtered Malpractice Dataset')
    parser.add_argument('--mode', type=str, default='quick', 
                       choices=['quick', 'high-accuracy', 'custom'],
                       help='Training mode')
    parser.add_argument('--model', type=str, default='n',
                       choices=['n', 's', 'm', 'l', 'x'],
                       help='Model size')
    parser.add_argument('--epochs', type=int, default=50,
                       help='Number of epochs')
    parser.add_argument('--imgsz', type=int, default=640,
                       help='Image size')
    parser.add_argument('--batch', type=int, default=-1,
                       help='Batch size (-1 for auto)')
    parser.add_argument('--data', type=str, 
                       default='../../Dataset/filtered_malpractice_dataset/data.yaml',
                       help='Path to data.yaml')
    
    args = parser.parse_args()
    
    if args.mode == 'quick':
        quick_train()
    elif args.mode == 'high-accuracy':
        high_accuracy_train()
    else:
        train_malpractice_detector(
            data_yaml_path=args.data,
            model_size=args.model,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch_size=args.batch
        )
