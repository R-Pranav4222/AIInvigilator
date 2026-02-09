# ML Integration Plan for AI Invigilator

## 🎯 Goal
Enhance detection accuracy and reduce false positives by integrating ML-based detection alongside existing computer vision rules.

## 📊 Dataset Options

### Option 1: Roboflow Major AAST Dataset (RECOMMENDED)
- **Link**: https://universe.roboflow.com/research-xfm0x/major-aast-dataset-3d
- **Size**: 213k images, 20 classes
- **Format**: YOLOv8 compatible
- **Classes**: Exam cheating behaviors, phone usage, paper passing, etc.
- **Download**: Use `download_roboflow_dataset.py` script
- **Status**: ✅ Public, Free with API key

### Option 2: Create Custom Dataset
- Record your own exam videos (with consent)
- Use LabelImg/Roboflow Annotate to label
- Minimum: 500-1000 images per class
- **Advantage**: Perfect for your specific use case

### Option 3: Other Public Datasets
1. **Kaggle Exam Monitoring Datasets**
   - Search: "exam cheating detection" on Kaggle
   - Typically smaller (10k-50k images)
   
2. **COCO Person Keypoints** (for pose refinement)
   - Link: https://cocodataset.org/#keypoints-2020
   - Can fine-tune pose detection
   
3. **Synthetic Data Generation**
   - Use existing videos + augmentation
   - Tools: Albumentations, imgaug

## 🚀 Implementation Strategy

### Phase 1: Hybrid Approach (RECOMMENDED - START HERE)
**Combine ML + Computer Vision for best results**

```
Current CV Rules → ML Confidence Score → Final Decision
     ↓                      ↓                  ↓
  Quick filter        Verify/Refine      High accuracy
```

**Benefits**:
- Reduces false positives from CV rules
- ML validates suspicious behavior
- Faster than pure ML (CV does initial filtering)
- Easy to implement incrementally

**Implementation**:
1. Keep existing CV detection
2. Add ML model as verification layer
3. Only trigger ML when CV detects something
4. Use ML confidence score to filter false positives

### Phase 2: Pure ML Approach (FUTURE)
**Train custom YOLO model on exam dataset**

**Options**:
- **A. Fine-tune YOLOv8/v11** on exam dataset
- **B. Train from scratch** (requires more data/time)
- **C. Use pre-trained model** from Roboflow Universe

### Phase 3: Ensemble Approach (ADVANCED)
**Combine multiple models**:
- YOLOv8 for object detection (phone, paper)
- Pose estimation for body language
- Action recognition for suspicious movements
- Facial recognition for identity verification

## 📋 Recommended Implementation Path

### Week 1: Setup & Data Preparation
```bash
# 1. Install dependencies
pip install roboflow ultralytics supervision

# 2. Download dataset (use smaller subset first)
python download_roboflow_dataset.py

# 3. Verify dataset structure
python verify_dataset.py
```

### Week 2: Model Training
```bash
# Option A: Fine-tune existing YOLOv8
python train_ml_model.py --mode finetune --epochs 50

# Option B: Use pre-trained from Roboflow
python download_pretrained_model.py
```

### Week 3: Integration
```bash
# 1. Create ML detection module
python ml_detector.py

# 2. Integrate with existing front.py
python integrate_ml.py

# 3. Test hybrid detection
python test_hybrid_detection.py
```

### Week 4: Testing & Optimization
```bash
# 1. Compare CV vs ML vs Hybrid
python benchmark_detection.py

# 2. Optimize thresholds
python optimize_thresholds.py

# 3. Deploy to production
python deploy_ml_system.py
```

## 🎨 Architecture Design

### Current System
```
Camera → Computer Vision Rules → Detection → Database
```

### Proposed Hybrid System
```
Camera → CV Rules (Fast Filter) → ML Verification → Final Decision → Database
         ↓                         ↓
    Quick detection          Confidence score
    Low computation          High accuracy
```

### Implementation Code Structure
```
ML/
├── models/
│   ├── ml_detector.py          # ML detection module
│   ├── hybrid_detector.py      # Combines CV + ML
│   └── trained_models/
│       ├── yolov8_exam.pt      # Trained YOLO model
│       └── config.yaml         # Model configuration
├── datasets/
│   └── major-aast/             # Downloaded dataset
├── training/
│   ├── train_ml_model.py       # Training script
│   ├── evaluate_model.py       # Evaluation script
│   └── hyperparameter_tuning.py
└── utils/
    ├── data_preprocessing.py   # Data augmentation
    └── metrics.py              # Performance metrics
```

## 🔧 Key Technologies

### Training
- **YOLOv8/v11**: Main detection model
- **Roboflow**: Dataset management & training
- **Weights & Biases**: Experiment tracking
- **TensorBoard**: Training visualization

### Deployment
- **ONNX**: Model optimization
- **TensorRT**: GPU acceleration
- **FastAPI**: ML model serving (optional)
- **Redis**: Caching predictions

## 📊 Expected Performance Improvements

### Current System (Computer Vision)
- **Speed**: 30-60 FPS ✅
- **Accuracy**: ~70-80% (many false positives)
- **False Positive Rate**: ~20-30%

### ML-Enhanced System (Hybrid)
- **Speed**: 20-40 FPS (slightly slower)
- **Accuracy**: ~90-95% (much better)
- **False Positive Rate**: ~5-10% (75% reduction!)

### Pure ML System
- **Speed**: 15-30 FPS (slower)
- **Accuracy**: ~85-92%
- **False Positive Rate**: ~8-15%

## 💰 Cost Analysis

### Option 1: Use Roboflow Pre-trained Model
- **Cost**: FREE (with API key limits)
- **Time**: 1-2 days setup
- **Effort**: LOW
- **Recommendation**: ⭐⭐⭐⭐⭐ START HERE!

### Option 2: Fine-tune on Downloaded Dataset
- **Cost**: FREE (training on your GPU)
- **Time**: 1-2 weeks
- **Effort**: MEDIUM
- **Recommendation**: ⭐⭐⭐⭐ Best accuracy for your use case

### Option 3: Train from Scratch
- **Cost**: FREE (but requires GPU time)
- **Time**: 3-4 weeks
- **Effort**: HIGH
- **Recommendation**: ⭐⭐ Only if you have lots of custom data

## 🎯 Next Steps

1. **TODAY**: Download Roboflow dataset (use script)
2. **THIS WEEK**: Implement hybrid detection prototype
3. **NEXT WEEK**: Train/fine-tune model
4. **MONTH END**: Deploy ML-enhanced system

## 📝 Notes

- Start with **Hybrid Approach** - easiest and fastest ROI
- Keep your current CV system as backup
- Use git branches to experiment safely
- Monitor performance metrics continuously
- Gradually increase ML usage as confidence grows

## 🆘 Troubleshooting

### Can't download dataset?
- Try smaller version/subset first
- Use Roboflow web interface to export
- Contact Roboflow support

### Training too slow?
- Use Google Colab (free GPU)
- Reduce batch size
- Use pre-trained weights
- Train on subset first

### Integration issues?
- Test ML module separately first
- Use feature flags to enable/disable ML
- Monitor memory usage
- Check GPU compatibility

---

**Remember**: ML is not magic! It needs:
- Good quality data
- Proper training
- Careful integration
- Continuous monitoring

Your current CV system is already good! ML will make it GREAT! 🚀
