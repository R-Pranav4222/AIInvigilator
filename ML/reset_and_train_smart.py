"""
Reset Training & Start with Smart Auto-Stop
Deletes old checkpoints and starts intelligent training
"""

import shutil
from pathlib import Path
import subprocess
import sys

print("\n" + "="*80)
print("🔄 RESET & START SMART TRAINING")
print("="*80)

# Paths to clean
paths_to_remove = [
    Path("runs/train/malpractice_detector"),
]

print("\n📂 Cleaning old training data...")
print("-"*80)

for path in paths_to_remove:
    if path.exists():
        try:
            if path.is_dir():
                shutil.rmtree(path)
                print(f"✅ Removed: {path}")
            else:
                path.unlink()
                print(f"✅ Removed: {path}")
        except Exception as e:
            print(f"⚠️  Could not remove {path}: {e}")
    else:
        print(f"ℹ️  Already clean: {path}")

print("-"*80)
print("✅ Cleanup complete!\n")

print("="*80)
print("🧠 SMART TRAINING CONFIGURATION")
print("="*80)
print("📊 Features:")
print("   • Minimum 6 epochs before early stopping")
print("   • Auto-stops when no improvement for 5 epochs")
print("   • Monitors mAP50 (detection accuracy)")
print("   • Saves best model automatically")
print("\n📈 Expected behavior:")
print("   • Trains for at least 6 epochs")
print("   • Likely stops around epoch 10-15")
print("   • Total time: ~3-5 hours")
print("="*80)
print("\n⏱️  Starting training...\n")

# Start training
try:
    subprocess.run([sys.executable, "train_smart_stop.py"], check=True)
except KeyboardInterrupt:
    print("\n\n⚠️  Training interrupted by user")
except Exception as e:
    print(f"\n\n❌ Training failed: {e}")
    sys.exit(1)
