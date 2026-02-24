# 🚀 COMMAND QUICK REFERENCE - AI Invigilator Custom Training

## 📍 IMPORTANT: Navigate to ML Directory First!

```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
```

---

## 🎯 Complete Workflow Commands

### 1️⃣ Validate System (< 1 minute)
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python validate_setup.py
```
Checks: GPU, dependencies, dataset, disk space

### 2️⃣ Estimate Time (2-5 minutes)
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python estimate_processing_time.py
```
Provides: System benchmark + time estimates

### 3️⃣ Filter Dataset (10-30 minutes)
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python filter_dataset_with_progress.py
```
Converts: 152 classes → 10 relevant classes

### 4️⃣ Train Model (6-12 hours)
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python train_with_checkpointing.py
```
Trains: Custom YOLO model with auto-resume

---

## 🚀 Quick Start (All-in-One)

```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python quick_start.py
```
Interactive menu that handles everything!

---

## 🔄 Resume Training After Interruption

```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python train_with_checkpointing.py
```
(Just run the same command - auto-detects and resumes!)

---

## 🧪 Test Your Trained Model

```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python quick_start.py
# Select Option 6: Test Trained Model
```

Or use Python:
```python
from ultralytics import YOLO
model = YOLO('e:/witcher/AIINVIGILATOR/AIINVIGILATOR/ML/runs/train/malpractice_detector/weights/best.pt')
model.predict(source=0, show=True)  # Webcam
```

---

## ⚙️ Edit Configuration

```bash
# Open in notepad
notepad e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\training_config.yaml

# Or VS Code
code e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\training_config.yaml
```

Key settings:
- `batch: 16` - If OOM error, reduce to 8 or 12
- `epochs: 100` - Total training epochs
- `save_period: 5` - Save checkpoint every N epochs

---

## 📁 Important File Locations

| Item | Path |
|------|------|
| **ML Scripts** | `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\` |
| **Source Dataset** | `e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8\` |
| **Filtered Dataset** | `e:\witcher\AIINVIGILATOR\Dataset\custom_filtered_dataset\` |
| **Training Config** | `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\training_config.yaml` |
| **Best Model** | `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\runs\train\malpractice_detector\weights\best.pt` |
| **Last Checkpoint** | `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\runs\train\malpractice_detector\weights\last.pt` |
| **Training State** | `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\checkpoints\training_state.json` |

---

## 🔥 One-Line Complete Workflow

```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML && python validate_setup.py && python filter_dataset_with_progress.py && python train_with_checkpointing.py
```

---

## 🆘 Quick Troubleshooting

### "CUDA out of memory"
```bash
# Edit config file
notepad e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\training_config.yaml
# Change: batch: 16 → batch: 8
```

### "Dataset not found"
```bash
# Make sure dataset exists
dir e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8

# If exists, filter it
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python filter_dataset_with_progress.py
```

### "Can't resume training"
```bash
# Check if checkpoint exists
dir e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\checkpoints\training_state.json
dir e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\runs\train\malpractice_detector\weights\last.pt
```

### Training very slow?
```bash
# Check GPU is being used (look for "GPU_mem" in training output)
# If showing "N/A", GPU not detected - check CUDA installation
```

---

## 📊 Check Training Progress

```bash
# View training results
dir e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\runs\train\malpractice_detector\

# View results.csv (training metrics)
type e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\runs\train\malpractice_detector\results.csv

# View with Excel
start excel e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\runs\train\malpractice_detector\results.csv
```

---

## 🎯 Copy-Paste Commands for Each Stage

### First Time Setup:
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python validate_setup.py
python estimate_processing_time.py
python filter_dataset_with_progress.py
python train_with_checkpointing.py
```

### Resume After Interruption:
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python train_with_checkpointing.py
```

### Test Trained Model:
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python
```
```python
from ultralytics import YOLO
model = YOLO('runs/train/malpractice_detector/weights/best.pt')
model.predict(source=0, show=True, conf=0.5)
```

---

## ⏱️ Time Estimates (RTX 3050 6GB)

| Command | Time |
|---------|------|
| `validate_setup.py` | < 1 minute |
| `estimate_processing_time.py` | 2-5 minutes |
| `filter_dataset_with_progress.py` | 10-30 minutes |
| `train_with_checkpointing.py` | 6-12 hours |

---

## 💡 Pro Tips

1. Always run from `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\` directory
2. Keep laptop plugged in during training
3. Use high-performance power mode
4. Don't worry about interruptions - auto-resume works perfectly
5. Training saves automatically every 5 epochs
6. Press Ctrl+C anytime to safely stop (progress is saved)

---

## 🎓 What Each Script Does

| Script | Purpose |
|--------|---------|
| `validate_setup.py` | Checks if system is ready (GPU, RAM, dependencies) |
| `estimate_processing_time.py` | Runs benchmark to estimate total time |
| `filter_dataset_with_progress.py` | Filters 152 classes down to 10 relevant ones |
| `train_with_checkpointing.py` | Trains model with progress bars & auto-resume |
| `quick_start.py` | Interactive menu for all operations |

---

**Need more help?** Read the full guide:
- Quick Guide: `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\README_TRAINING.md`
- Detailed Guide: `e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML\CUSTOM_MODEL_TRAINING_GUIDE.md`

---

**Ready?** Start with:
```bash
cd e:\witcher\AIINVIGILATOR\AIINVIGILATOR\ML
python quick_start.py
```
