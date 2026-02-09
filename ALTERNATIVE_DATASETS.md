# Alternative Public Datasets for Exam Malpractice Detection

## 🎯 Primary Recommendation: Roboflow Major AAST Dataset
- **Link**: https://universe.roboflow.com/research-xfm0x/major-aast-dataset-3d
- **Size**: 213k images
- **Classes**: 20 exam malpractice behaviors
- **Status**: ✅ Free with API key
- **Download**: Use `download_roboflow_dataset.py`

---

## 📊 Alternative Datasets

### 1. Roboflow Universe - Other Exam Datasets

**Search for**: "exam", "cheating", "classroom", "student behavior"

**Notable datasets**:
- **Exam Cheating Detection** (various creators)
- **Classroom Monitoring** datasets
- **Student Pose** datasets
- **Phone Detection in Classroom**

**How to find**:
```
1. Go to https://universe.roboflow.com/
2. Search: "exam cheating" or "student monitoring"
3. Filter by: Public, Large (10k+ images)
4. Download in YOLOv8 format
```

### 2. Kaggle Datasets

**Link**: https://www.kaggle.com/datasets

**Search terms**:
- "exam proctoring"
- "online exam cheating"
- "student behavior detection"
- "classroom monitoring"

**Popular datasets**:
- Exam Proctoring Dataset (~10-50k images)
- Student Engagement Dataset
- Cheating Detection Challenge datasets

**Download**:
```bash
# Install Kaggle CLI
pip install kaggle

# Set up API credentials (from kaggle.com/account)
# Download dataset
kaggle datasets download -d <dataset-name>
```

### 3. COCO Dataset (for fine-tuning pose/object detection)

**Link**: https://cocodataset.org/

**Relevant subsets**:
- **Person Keypoints**: 200k images with pose annotations
- **Objects**: Phone, laptop, book, paper detection

**Use case**: Pre-train on COCO, then fine-tune on exam data

**Download**:
```bash
# Download COCO 2017
wget http://images.cocodataset.org/zips/train2017.zip
wget http://images.cocodataset.org/annotations/annotations_trainval2017.zip
```

### 4. Custom Dataset Creation

**If you can't find suitable public datasets, create your own!**

**Tools**:
1. **Label Studio** (https://labelstud.io/)
   - Free, open-source
   - Web-based annotation
   - Supports YOLO format export

2. **Roboflow Annotate** (https://roboflow.com/)
   - Free tier available
   - Auto-annotation features
   - Dataset augmentation

3. **CVAT** (https://cvat.org/)
   - Free, open-source
   - Professional-grade
   - Team collaboration

**Process**:
```
1. Record exam videos (with consent!)
2. Extract frames: 1 frame per second
3. Annotate 500-1000 images per class
4. Export in YOLOv8 format
5. Train custom model
```

### 5. Synthetic Data Generation

**Tools**:
- **Unreal Engine + AirSim**: Generate synthetic exam scenarios
- **Unity ML-Agents**: Create virtual classrooms
- **Blender**: Render 3D scenes

**Advantages**:
- Unlimited data
- Perfect annotations
- No privacy concerns

**Disadvantages**:
- Time-consuming setup
- May not generalize to real-world

### 6. Academic Datasets

**Search on**:
- **Papers With Code**: https://paperswithcode.com/datasets
- **Google Dataset Search**: https://datasetsearch.research.google.com/
- **IEEE DataPort**: https://ieee-dataport.org/

**Keywords**:
- "exam monitoring"
- "academic integrity"
- "student behavior"
- "classroom analytics"

---

## 🔧 Dataset Conversion Tools

### Convert Other Formats to YOLOv8

**Pascal VOC → YOLO**:
```python
from roboflow import Roboflow
# Use Roboflow's conversion tools
```

**COCO → YOLO**:
```python
from ultralytics.data.converter import convert_coco
convert_coco(labels_dir='annotations/')
```

**Custom Format → YOLO**:
```python
# Create conversion script
# YOLO format: <class> <x_center> <y_center> <width> <height> (normalized 0-1)
```

---

## 💡 Data Augmentation Strategies

**If dataset is small, augment it!**

```python
import albumentations as A

transform = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.RandomBrightnessContrast(p=0.5),
    A.Blur(p=0.3),
    A.GaussNoise(p=0.3),
    A.Rotate(limit=10, p=0.5),
], bbox_params=A.BboxParams(format='yolo'))

# Apply to your dataset
# Can 5x your data easily!
```

---

## 📊 Dataset Quality Checklist

Before training, verify:
- [ ] Balanced classes (each class has similar number of images)
- [ ] High-quality annotations (boxes are accurate)
- [ ] Diverse scenarios (different lighting, angles, backgrounds)
- [ ] No data leakage (train/val/test split properly)
- [ ] Sufficient size (500+ images per class minimum)

---

## 🚀 Quick Start Recommendations

### For Quick Testing (TODAY):
1. Download Roboflow Major AAST dataset (use API)
2. Use pre-trained model if available
3. Test on your video footage

### For Best Accuracy (THIS WEEK):
1. Download Major AAST dataset
2. Fine-tune YOLOv8 on it
3. Collect 100-200 images from YOUR exam setup
4. Add to dataset and retrain
5. This gives you generalization + customization!

### For Production (THIS MONTH):
1. Start with fine-tuned model
2. Continuously collect edge cases
3. Retrain monthly
4. Monitor performance metrics
5. A/B test with CV rules

---

## 🆘 If You Still Can't Download Datasets

### Try These Alternatives:

1. **Use Roboflow Web Interface**
   - Download from browser instead of API
   - Export in smaller batches
   - Contact Roboflow support

2. **Use Kaggle Notebooks**
   - Run training in Kaggle (free GPU)
   - Datasets already available there
   - No download needed locally

3. **Use Google Colab**
   - Mount Google Drive
   - Download datasets in Colab
   - Train in cloud

4. **Contact Dataset Creators**
   - Most researchers are happy to share
   - Explain your use case
   - Request direct download link

5. **Start Small**
   - Create 100-image dataset yourself
   - Prove concept works
   - Expand gradually

---

## 📧 Get Help

If you're stuck:
1. **Roboflow Community**: community.roboflow.com
2. **Ultralytics Discord**: ultralytics.com/discord
3. **Computer Vision Discord**: https://discord.gg/computervision
4. **Reddit**: r/computervision, r/MachineLearning

---

## ✅ Summary

**Easiest Path**:
```
1. Get Roboflow API key (free)
2. Run: python download_roboflow_dataset.py
3. Run: python train_ml_model.py (option 2)
4. Wait a few hours
5. You have a trained model!
```

**If that fails**:
```
1. Search Kaggle for "exam cheating"
2. Download smaller dataset (10k images)
3. Fine-tune on that
4. Still better than pure CV!
```

**Best long-term**:
```
1. Use Roboflow dataset as base
2. Add your own data (100-200 images)
3. Fine-tune on combined dataset
4. Perfect for your specific setup!
```

---

Good luck! Remember: Even a small ML model (trained on 1000 images) can significantly reduce false positives compared to pure computer vision rules! 🚀
