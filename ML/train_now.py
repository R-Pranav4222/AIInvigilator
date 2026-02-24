"""Quick training script without confirmation prompts"""
import torch
from ultralytics import YOLO
import os

def main():
    print("=" * 70)
    print("🎯 Training YOLO11 on Filtered Malpractice Dataset")
    print("=" * 70)

    # Configuration
    data_yaml = "../../Dataset/filtered_malpractice_dataset/data.yaml"
    model_size = 'n'  # nano - fastest
    epochs = 50
    imgsz = 416  # Reduced for memory efficiency
    batch = 8  # Smaller batch for GPU memory
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    print(f"\n📊 Configuration:")
    print(f"   Model: yolo11{model_size}")
    print(f"   Epochs: {epochs}")
    print(f"   Image size: {imgsz}")
    print(f"   Batch size: {batch}")
    print(f"   Device: {device}")

    if device == 'cuda':
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
        # Clear CUDA cache
        torch.cuda.empty_cache()
        print("   ✅ Cleared CUDA cache")

    print(f"\n🚀 Starting training...")
    print("=" * 70)

    try:
        # Load model with pre-trained weights
        model = YOLO(f"yolo11{model_size}.pt")
        
        # Train
        results = model.train(
            data=data_yaml,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device=device,
            project='models/custom',
            name='malpractice_detector',
            
            # Memory optimization
            cache=False,  # Don't cache images (saves RAM)
            workers=0,  # Set to 0 for Windows multiprocessing issue
            
            # Training settings
            patience=10,
            save=True,
            save_period=5,
            
            # Augmentation
            augment=True,
            
            # Performance
            amp=True,  # Mixed precision
            
            # Validation
            val=True,
            plots=True,
            verbose=True
        )
        
        print("\n" + "=" * 70)
        print("✅ TRAINING COMPLETED!")
        print("=" * 70)
        print(f"\n📊 Model saved to: {results.save_dir}/weights/best.pt")
        
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        
        # If CUDA error, suggest CPU training
        if 'CUDA' in str(e) or 'memory' in str(e).lower():
            print("\n💡 GPU memory issue detected!")
            print("   Try: python train_now.py (it will auto-retry on CPU)")

if __name__ == '__main__':
    main()
