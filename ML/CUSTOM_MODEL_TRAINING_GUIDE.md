# 🚀 Custom Model Training Guide - AI Invigilator

## 📋 Overview
This guide walks you through creating a custom YOLO model trained on relevant malpractice detection classes from the major-aast-dataset (152 classes filtered down to 10 relevant classes).

## ✨ Features
- ✅ **Real-time Progress Bars** - See percentage completion and ETA for all operations
- ✅ **Auto-Resume** - Power loss or internet disconnection? Resume from last checkpoint
- ✅ **Time Estimation** - Know beforehand how long everything will take
- ✅ **Optimized for RTX 3050 6GB** - Pre-configured batch sizes and settings

## 📁 Dataset Information

### Source Dataset (major-aast-dataset2)
- **Total Classes:** 152
- **Total Images:** ~214,000
- **Source:** Roboflow

### Filtered Dataset (custom_filtered_dataset)
- **Target Classes:** 10 relevant classes
- **Classes:**
  1. `phone` - Phone usage detection
  2. `cheat_material` - Cheat sheets, notes, papers
  3. `peeking` - Looking at other students' papers
  4. `turning_back` - Turning around during exam
  5. `hand_raise` - Student raising hand
  6. `passing` - Passing notes or items
  7. `talking` - Students talking to each other
  8. `cheating` - General cheating behavior
  9. `suspicious` - Suspicious movements
  10. `normal` - Normal exam behavior

## 🔧 System Requirements

### Minimum Requirements
- **GPU:** NVIDIA RTX 3050 (6GB VRAM) or better
- **RAM:** 16GB
- **Storage:** 50GB free space
- **OS:** Windows 10/11, Linux, macOS

### Recommended Laptop Settings
- **Power Mode:** High Performance (battery saver OFF)
- **Laptop Cooling:** Ensure good ventilation
- **Close Background Apps:** Free up GPU memory

## ⏱️ Expected Processing Times (RTX 3050 6GB)

| Task | Estimated Time |
|------|---------------|
| Dataset Filtering | 10-30 minutes |
| Model Training (100 epochs) | 6-12 hours |
| **Total** | **~6-13 hours** |

💡 **Tip:** Start training overnight and let auto-resume handle any interruptions!

## 🚦 Step-by-Step Guide

### IMPORTANT: All commands must be run from the ML directory
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
```

### Step 1: Estimate Processing Time
Run this first to get accurate time estimates for your system:

```bash
python estimate_processing_time.py
```

**What it does:**
- Analyzes your GPU capabilities
- Counts dataset files
- Runs mini-benchmark
- Provides accurate time estimates

**Expected Output:**
```
💻 SYSTEM INFORMATION
══════════════════════════════════════
🖥️  Platform:     Windows
💾 RAM:          16.0 GB
🎮 GPU:          NVIDIA GeForce RTX 3050 Laptop GPU
💾 VRAM:         6.0 GB

⏱️  DATASET FILTERING: ~15 minutes
⏱️  MODEL TRAINING: ~8 hours 30 minutes
⏱️  TOTAL: ~8 hours 45 minutes
```

### Step 2: Filter Dataset
Filter the 152-class dataset to 10 relevant classes:

```bash
python filter_dataset_with_progress.py
```

**Features:**
- ✅ Real-time progress bar with ETA
- ✅ Shows files kept vs skipped
- ✅ Creates optimized directory structure
- ✅ Generates data.yaml automatically

**Expected Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Processing TRAIN split
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Filtering train: 100%|████████| 15000/15000 [02:15<00:00, 110.5 files/s]
✅ TRAIN complete: 8,432 images kept, 6,568 skipped

✨ FILTERING COMPLETE!
📁 Dataset saved to: E:\witcher\AIINVIGILATOR\Dataset\custom_filtered_dataset
```

**Output Location:**
```
e:\witcher\AIINVIGILATOR\Dataset\
└── custom_filtered_dataset\
    ├── data.yaml
    ├── train\
    │   ├── images\
    │   └── labels\
    ├── valid\
    │   ├── images\
    │   └── labels\
    └── test\
        ├── images\
        └── labels\
```

### Step 3: Configure Training (Optional)
Edit training configuration file if needed:

**File location:** `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\training_config.yaml`

```yaml
# Key settings for RTX 3050 6GB
epochs: 100          # Training epochs
batch: 16            # Batch size (reduce to 8 if OOM)
imgsz: 640          # Image size
patience: 20         # Early stopping
save_period: 5      # Save checkpoint every 5 epochs
```

**Batch Size Guide:**
- RTX 3050 (6GB): `batch: 16` ✅ Optimal
- RTX 3060 (8GB): `batch: 24`
- RTX 3070+ (10GB+): `batch: 32`

If you get **Out of Memory (OOM)** errors, reduce batch size:
```yaml
batch: 12  # or 8
```

### Step 4: Train Model
Start training with auto-resume capability:

```bash
python train_with_checkpointing.py
```

**Features:**
- ✅ YOLO's built-in progress bars with ETA per epoch
- ✅ Auto-save every 5 epochs
- ✅ Resume from interruption automatically
- ✅ Real-time loss and metric tracking

**Expected Output:**
```
════════════════════════════════════════════════════════════
🚀 AI INVIGILATOR - ADVANCED TRAINING WITH AUTO-RESUME
════════════════════════════════════════════════════════════
📅 Start Time: 2026-02-13 22:30:00
💻 Device: GPU (CUDA)
🎮 GPU: NVIDIA GeForce RTX 3050 Laptop GPU
💾 VRAM: 6.0 GB
════════════════════════════════════════════════════════════

⚙️  TRAINING CONFIGURATION
────────────────────────────────────────────────────────────
  Model:          yolo11n.pt
  Epochs:         100
  Batch Size:     16
  Save Period:    Every 5 epochs
────────────────────────────────────────────────────────────

🎯 TRAINING STARTED
════════════════════════════════════════════════════════════

Epoch    GPU_mem   box_loss   cls_loss   dfl_loss  Instances       Size
  1/100      4.2G      0.850      2.345      1.123        156        640: 100%|████| 234/234 [02:15<00:00,  1.73it/s]
                 Class     Images  Instances      P      R      mAP50  mAP50-95
                   all       1000       5234  0.345  0.432      0.398     0.234
```

**Progress Tracking:**
- Each epoch shows: GPU memory, losses, metrics
- Real-time ETA for current epoch
- Validation metrics after each epoch
- Auto-save checkpoints every 5 epochs

### Step 5: Handle Interruptions

#### If Power Loss or Internet Disconnection Occurs:
Navigate to ML directory and run the training script again!

```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python train_with_checkpointing.py
```

**The script will automatically:**
1. Detect previous training session
2. Find last checkpoint
3. Ask if you want to resume
4. Continue from where it stopped

**Example Resume:**
```
🔄 RESUMING PREVIOUS TRAINING
────────────────────────────────────────────────────────────
  Previous Session: 20260213_223000
  Completed Epochs: 35/100
  Last Checkpoint:  runs/train/malpractice_detector/weights/last.pt
────────────────────────────────────────────────────────────

Do you want to resume training? (y/n):
```

#### To Safely Stop Training:
Press `Ctrl+C` - checkpoint will be saved automatically!

```
⚠️  TRAINING INTERRUPTED BY USER
════════════════════════════════════════════════════════════
💾 Checkpoint saved: runs/train/malpractice_detector/weights/last.pt
📊 Completed epochs: 35/100

💡 To resume training, run this script again!
```

### Step 6: Evaluate Results

After training completes, find your model:

```
e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\runs\train\malpractice_detector\
├── weights\
│   ├── best.pt          # ⭐ Best model (use this!)
│   └── last.pt          # Last checkpoint
├── results.csv          # Training metrics
├── confusion_matrix.png # Confusion matrix
├── results.png          # Training curves
└── val_batch*.jpg       # Validation predictions
```

**Use the best model:**
```python
from ultralytics import YOLO

# Load your custom model (full path)
model = YOLO('e:/witcher/AIINVIGILATOR/AIINVIGILATOR/ML/runs/train/malpractice_detector/weights/best.pt')

# Test on webcam
results = model.predict(source=0, show=True)

# Or on video
results = model.predict(source='exam_video.mp4', save=True)
```

## 🔥 Tips & Best Practices

### Before Training
1. ✅ Run `estimate_processing_time.py` to plan your session
2. ✅ Close unnecessary applications (browsers, games)
3. ✅ Ensure laptop is plugged in
4. ✅ Enable high-performance power mode
5. ✅ Ensure good cooling/ventilation

### During Training
1. ✅ Don't close the terminal window
2. ✅ Monitor GPU temperature (should be <85°C)
3. ✅ Check progress periodically
4. ✅ If you see OOM errors, stop (Ctrl+C) and reduce batch size

### If Training is Too Slow
1. Reduce `epochs: 100` → `epochs: 50`
2. Reduce `batch: 16` → `batch: 12`
3. Use smaller image size: `imgsz: 640` → `imgsz: 512`

### If Out of Memory (OOM)
Edit `training_config.yaml`:
```yaml
batch: 8  # Reduce from 16
```

Or use a smaller model:
```yaml
model: yolo11n.pt  # Smallest (current)
# model: yolo11s.pt  # Small (requires more VRAM)
```

## 📊 Understanding Training Output

### Key Metrics to Watch:
- **box_loss:** Bounding box accuracy (lower is better)
- **cls_loss:** Classification accuracy (lower is better)
- **mAP50:** Mean Average Precision at 50% IoU (higher is better)
- **mAP50-95:** mAP averaged over 50-95% IoU (higher is better)

### Good Training Signs:
- ✅ Losses decreasing over epochs
- ✅ mAP increasing over epochs
- ✅ Validation metrics improving
- ✅ No OOM errors

### Warning Signs:
- ⚠️ Losses not decreasing after 20+ epochs
- ⚠️ mAP stuck or decreasing
- ⚠️ OOM errors (reduce batch size)
- ⚠️ GPU temperature >85°C (improve cooling)

## 🆘 Troubleshooting

### Issue: "CUDA out of memory"
**Solution:**
```yaml
# In training_config.yaml
batch: 8  # Reduce from 16
```

### Issue: "Dataset path not found"
**Solution:**
- Ensure you ran `filter_dataset_with_progress.py` first
- Check path in `training_config.yaml` matches filtered dataset location

### Issue: Training is very slow
**Solution:**
1. Check GPU is being used: Look for "GPU_mem" in output
2. Close background applications
3. Reduce batch size if GPU is maxed out
4. Consider training overnight

### Issue: Can't resume after interruption
**Solution:**
1. Check `checkpoints/training_state.json` exists
2. Ensure checkpoint files exist in `runs/train/malpractice_detector/weights/`
3. If corrupted, start fresh (script will ask)

## 📈 What Happens After Training?

1. **Model is saved** in `runs/train/malpractice_detector/weights/best.pt`
2. **Integrate into your app:**
   ```python
   # In your detection scripts
   model = YOLO('path/to/best.pt')
   ```
3. **Test on real exam videos**
4. **Fine-tune if needed** by resuming training with more epochs

## 🎯 Expected Performance

With proper training on RTX 3050:
- **mAP50:** 60-80% (good performance)
- **mAP50-95:** 40-60% (acceptable)
- **Inference Speed:** 30-60 FPS on 640x640 images

## 📞 Need Help?

If you encounter issues:
1. Check terminal output for error messages
2. Review `checkpoints/training_state.json` for session info
3. Examine training logs in `runs/train/malpractice_detector/`
4. Ensure all paths are correct in `training_config.yaml`

## 🎉 Success Indicators

You're done when you see:
```
✅ TRAINING COMPLETED SUCCESSFULLY!
════════════════════════════════════════════════════════════
📁 Results saved to: runs/train/malpractice_detector
⏱️  Total Time: 8:32:15
════════════════════════════════════════════════════════════
```

Your custom model is ready! 🎊

---

**Happy Training! 🚀**
