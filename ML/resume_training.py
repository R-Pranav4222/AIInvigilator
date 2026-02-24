"""
Resume Training from Last Checkpoint
Continues from where you stopped (epoch 9)
"""

from ultralytics import YOLO

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🔄 RESUMING TRAINING FROM EPOCH 9")
    print("="*80)
    print(f"📁 Loading: runs/train/malpractice_detector/weights/last.pt")
    print("="*80 + "\n")

    # Load the checkpoint and resume training
    model = YOLO('runs/train/malpractice_detector/weights/last.pt')

    # YOLO will automatically detect and resume from this checkpoint
    # It will continue to the configured max epochs (25)
    results = model.train(resume=True)

    print("\n" + "="*80)
    print("✅ TRAINING COMPLETED")
    print("="*80)
    print(f"📁 Results: {results.save_dir}")
    print("="*80)
