# Model Directory

This folder contains trained YOLO models for malpractice detection.

## Available Models

| Model | Description | Status |
|-------|-------------|--------|
| `pretrained/yolo11n.pt` | Pre-trained YOLO11 nano (general objects) | ✅ Working |
| `pretrained/yolov8n-pose.pt` | Pre-trained YOLOv8 pose detection | ✅ Working |
| `custom/malpractice_detector.pt` | Custom trained on malpractice dataset | 🔄 Training |

## Switching Models

Edit `ML/model_config.py` to switch between models:

```python
# Use pre-trained models (default, stable)
ACTIVE_MODEL_PRESET = "pretrained"

# Use custom trained model
ACTIVE_MODEL_PRESET = "custom"
```

## Model Backup

Pre-trained models are backed up and will never be overwritten by training.
