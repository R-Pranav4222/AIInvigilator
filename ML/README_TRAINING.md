# 🎯 Custom Model Training System - Quick Reference

## 📚 What You Got

A complete, production-ready system for training custom YOLO models with:

✅ **Real-time progress bars** with percentage & ETA  
✅ **Auto-resume capability** - survives power loss & internet disconnection  
✅ **Time estimation** before you start  
✅ **Optimized for RTX 3050 6GB** VRAM  

---

## 🚀 Quick Start (3 Simple Steps)

### Step 1: Navigate to ML Directory
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
```

### Step 2: Validate Setup
```bash
python validate_setup.py
```
Checks if your system is ready for training.

### Step 3: Use Quick Launcher
```bash
python quick_start.py
```
Interactive menu that guides you through everything!

### Step 4: Done!
Your custom model will be saved to:
```
e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\runs\train\malpractice_detector\weights\best.pt
```

---

## 📁 File Overview

| File | Purpose | When to Use |
|------|---------|-------------|
| **quick_start.py** | 🚀 Interactive launcher | Start here! |
| **validate_setup.py** | ✅ System validation | Before training |
| **estimate_processing_time.py** | ⏱️ Time estimation | Plan your session |
| **filter_dataset_with_progress.py** | 🗂️ Dataset filtering | Filter 152→10 classes |
| **train_with_checkpointing.py** | 🎯 Model training | Train the model |
| **training_config.yaml** | ⚙️ Configuration | Adjust settings |
| **CUSTOM_MODEL_TRAINING_GUIDE.md** | 📖 Full guide | Detailed instructions |

---

## ⚡ Super Quick Start

If you're in a hurry:

```bash
# Navigate to ML directory
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML

# 1. Validate everything is working
python validate_setup.py

# 2. Launch the interactive menu
python quick_start.py

# 3. Follow the menu:
#    - Option 1: Check time estimates
#    - Option 2: Filter dataset (~15 min)
#    - Option 3: Train model (~8 hours)
```

---

## ⏱️ Time Expectations (RTX 3050 6GB)

| Task | Time |
|------|------|
| Dataset Filtering | 10-30 minutes |
| Model Training (100 epochs) | 6-12 hours |
| **Total** | **~6-13 hours** |

💡 **Tip:** Start training before bed, let it run overnight!

---

## 🛡️ Auto-Resume Feature

**Power loss? Internet down? No problem!**

Just run the training script again from ML directory:
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python train_with_checkpointing.py
```

It will automatically:
1. Detect previous session
2. Find last checkpoint
3. Resume from where it stopped

**No data loss!** ✅

---

## 📊 Dataset Information

**Source:** major-aast-dataset2 (152 classes, ~214k images)  
**Filtered:** custom_filtered_dataset (10 classes, optimized)

**10 Relevant Classes:**
1. phone - Phone usage
2. cheat_material - Cheat sheets
3. peeking - Looking at others
4. turning_back - Turning around
5. hand_raise - Raising hand
6. passing - Passing items
7. talking - Students talking
8. cheating - General cheating
9. suspicious - Suspicious behavior
10. normal - Normal exam behavior

---

## 🎮 System Requirements

**Minimum:**
- GPU: RTX 3050 6GB (or equivalent)
- RAM: 16GB
- Storage: 50GB free
- OS: Windows/Linux/macOS

**Your System:** ✅ RTX 3050 6GB, 16GB RAM - Perfect!

---

## 🆘 Common Issues & Solutions

### "CUDA out of memory"
```yaml
# Edit: e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\training_config.yaml
batch: 8  # Reduce from 16
```

### "Dataset not found"
1. Ensure major-aast-dataset2 is in `e:\witcher\AIINVIGILATOR\Dataset\` folder
2. Navigate to: `cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML`
3. Run: `python filter_dataset_with_progress.py`

### Training too slow?
1. Close background apps
2. Enable high-performance mode
3. Ensure laptop is plugged in

---

## 🎯 After Training

### Use Your Model
```python
from ultralytics import YOLO

# Load trained model (full path)
model = YOLO('e:/witcher/AIINVIGILATOR/AIINVIGILATOR/ML/runs/train/malpractice_detector/weights/best.pt')

# Test on webcam
model.predict(source=0, show=True)

# Or on video
model.predict(source='exam.mp4', save=True)
```

### Model Location
```
e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\runs\train\malpractice_detector\
├── weights\
│   ├── best.pt          ⭐ Use this!
│   └── last.pt          (last checkpoint)
├── results.csv          (training metrics)
├── confusion_matrix.png (evaluation)
└── results.png          (training curves)
```

---

## 📞 Need Help?

1. **Read the full guide:** `CUSTOM_MODEL_TRAINING_GUIDE.md`
2. **Check system status:** Run `quick_start.py` → Option 5
3. **Validate setup:** Run `validate_setup.py`

---

## ✨ Features Highlights

### Progress Bars Everywhere
```
Filtering train: 100%|████████| 15000/15000 [02:15<00:00, 110.5 files/s]
Epoch 1/100: 100%|████████| 234/234 [02:15<00:00, 1.73it/s]
```

### Real-Time Stats
```
⏱️  Time per epoch: 00:02:15
📊 Epochs remaining: 99
⏰ ETA: 3h 42m
```

### Auto-Recovery
```
🔄 RESUMING PREVIOUS TRAINING
Previous Session: 20260213_223000
Completed Epochs: 35/100
Last Checkpoint: runs/train/.../last.pt
```

---

## 🎉 Success Criteria

Training is successful when you see:
```
✅ TRAINING COMPLETED SUCCESSFULLY!
📁 Results saved to: runs/train/malpractice_detector
⏱️  Total Time: 8:32:15
📊 Best mAP50: 0.752
```

**Your model is ready!** 🎊

---

## 💡 Pro Tips

1. **Run time estimation first** - know what to expect
2. **Start training overnight** - let it run while you sleep
3. **Don't worry about interruptions** - auto-resume has your back
4. **Monitor GPU temperature** - keep it below 85°C
5. **Keep laptop plugged in** - don't risk power loss

---

## 📂 Project Structure

```
ML/
├── quick_start.py                    🚀 Start here!
├── validate_setup.py                 ✅ Validation
├── estimate_processing_time.py       ⏱️ Time estimation
├── filter_dataset_with_progress.py   🗂️ Dataset filtering
├── train_with_checkpointing.py       🎯 Training
├── training_config.yaml              ⚙️ Configuration
├── CUSTOM_MODEL_TRAINING_GUIDE.md    📖 Full guide
├── checkpoints/                      💾 Auto-save states
└── runs/                            📊 Training results
```

---

## 🔥 One-Liner Commands

```bash
# Complete workflow (from ML directory)
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML && python validate_setup.py && python filter_dataset_with_progress.py && python train_with_checkpointing.py
```

Or just use the interactive launcher:
```bash
# Navigate to ML directory first
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python quick_start.py
```

---

## 📋 Complete Command Reference

### All commands must be run from the ML directory:
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
```

### Individual Commands:

| Command | Purpose | Estimated Time |
|---------|---------|----------------|
| `python validate_setup.py` | Check system readiness | < 1 minute |
| `python estimate_processing_time.py` | Benchmark & time estimates | 2-5 minutes |
| `python filter_dataset_with_progress.py` | Filter dataset (152→10 classes) | 10-30 minutes |
| `python train_with_checkpointing.py` | Train model with auto-resume | 6-12 hours |
| `python quick_start.py` | Interactive launcher (all-in-one) | - |

### Full Workflow:
```bash
# STEP 0: Navigate to ML directory
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML

# STEP 1: Validate system (GPU, dependencies, dataset)
python validate_setup.py

# STEP 2: Get time estimates for your system
python estimate_processing_time.py

# STEP 3: Filter dataset (152 classes → 10 relevant classes)
python filter_dataset_with_progress.py

# STEP 4: Train custom model (with auto-resume)
python train_with_checkpointing.py
```

### One-Line Execution:
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML && python validate_setup.py && python filter_dataset_with_progress.py && python train_with_checkpointing.py
```

### Testing Your Trained Model:
```bash
# Option 1: Using quick_start.py menu
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python quick_start.py
# Then select Option 6: Test Trained Model

# Option 2: Using Python script
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python
```
```python
from ultralytics import YOLO
model = YOLO('runs/train/malpractice_detector/weights/best.pt')
model.predict(source=0, show=True)  # Webcam test
```

### Important File Paths:

| Type | Location |
|------|----------|
| **Source Dataset** | `e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8\` |
| **Filtered Dataset** | `e:\witcher\AIINVIGILATOR\Dataset\custom_filtered_dataset\` |
| **Training Config** | `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\training_config.yaml` |
| **Best Model** | `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\runs\train\malpractice_detector\weights\best.pt` |
| **Checkpoints** | `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\checkpoints\training_state.json` |

---

**Ready to train your custom model?** 🚀

**Quick Start Command:**
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML && python quick_start.py
```

---

*Optimized for RTX 3050 6GB | Auto-Resume Enabled | Progress Bars Everywhere*
