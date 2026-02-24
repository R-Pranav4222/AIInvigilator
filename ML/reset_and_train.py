"""
Reset Training & Start Fresh with Optimized Settings
Deletes old checkpoints and starts training with new config
"""

import shutil
import os
from pathlib import Path
import subprocess
import sys

print("\n" + "="*80)
print("🔄 RESET TRAINING - START FRESH WITH OPTIMIZED CONFIG")
print("="*80)

# Paths to clean
paths_to_remove = [
    Path("runs/train/malpractice_detector"),
    Path("checkpoints/training_state.json"),
]

print("\n📂 Cleaning old training data...")
print("-"*80)

for path in paths_to_remove:
    if path.exists():
        try:
            if path.is_dir():
                shutil.rmtree(path)
                print(f"✅ Removed directory: {path}")
            else:
                path.unlink()
                print(f"✅ Removed file: {path}")
        except Exception as e:
            print(f"⚠️  Could not remove {path}: {e}")
    else:
        print(f"ℹ️  Already clean: {path}")

print("-"*80)
print("✅ Cleanup complete!\n")

print("="*80)
print("🚀 STARTING TRAINING WITH OPTIMIZED SETTINGS")
print("="*80)
print("📊 New Config:")
print("   • Batch size: 32 (was 16)")
print("   • Workers: 4 (was 2)")
print("   • Mixed Precision: Enabled (2x faster)")
print("   • Image Caching: RAM (10x faster after epoch 1)")
print("   • Epochs: 50 (was 100)")
print("="*80)
print("\n⏱️  Expected training time: 2-4 hours (was 30+ hours)\n")

# Start training
try:
    subprocess.run([sys.executable, "train_with_checkpointing.py"], check=True)
except KeyboardInterrupt:
    print("\n\n⚠️  Training interrupted by user")
except Exception as e:
    print(f"\n\n❌ Training failed: {e}")
    sys.exit(1)
