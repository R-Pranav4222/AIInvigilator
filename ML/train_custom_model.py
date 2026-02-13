# train_custom_model.py
"""
Custom Malpractice Detection Model Training
=============================================
Train a YOLO model on the malpractice dataset.

This script:
1. Filters the dataset to relevant malpractice classes
2. Creates a training configuration
3. Trains the model with GPU acceleration
4. Saves the model to models/custom/

Your pre-trained models remain untouched in models/pretrained/
"""

import os
import yaml
import shutil
from pathlib import Path
from ultralytics import YOLO
import torch

# ============================================
# CONFIGURATION
# ============================================

# Dataset path
DATASET_ROOT = Path(r"E:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8")

# Output directory
OUTPUT_DIR = Path(__file__).parent / "models" / "custom"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Training configuration
TRAINING_CONFIG = {
    "epochs": 100,           # Number of training epochs
    "batch_size": 8,         # Lowered to 8 to fix memory error (Page File)
    "imgsz": 640,            # Image size
    "device": "0",           # GPU device (use "cpu" for CPU)
    "workers": 2,            # Lowered to 2 to fix memory error (Page File)
    "patience": 20,          # Early stopping patience
    "save_period": 10,       # Save checkpoint every N epochs
    "exist_ok": True,        # Overwrite existing runs
    "pretrained": True,      # Use pretrained weights
    "optimizer": "AdamW",    # Optimizer
    "lr0": 0.001,            # Initial learning rate
    "lrf": 0.01,             # Final learning rate factor
    "warmup_epochs": 3,      # Warmup epochs
    "close_mosaic": 10,      # Disable mosaic augmentation last N epochs
}

# Base model to start from (transfer learning)
BASE_MODEL = "yolo11n.pt"  # Use nano model for faster training

# Classes to keep from the dataset (relevant to malpractice)
RELEVANT_CLASSES = [
    # Mobile/Phone
    'Cellphone', 'Mobile', 'Phone', 'Using Phone', 'Using_Mobile', 
    'phone using', 'mobile using', 'student_using_phone', 'Using_phone',
    'make_phone_call', 'playing_phone', 'phone', 'mobile',
    
    # Cheating materials
    'Cheat_note', 'Cheating-Paper', 'cheating-paper', 
    'Using_cheat_sheets', 'chit', 'using chits', 'student_cheating',
    
    # Looking/Peeking
    'Looking Over', 'Peeping', 'back peeking', 'front peeking', 
    'side peeking', 'looking into neighbors paper', 'looking around',
    
    # Turning back
    'Turning Back', 'student_looking_backward', 'turn_head',
    
    # Hand raising
    'Hand raise', 'hand-raising', 'raising hand', 'Hand-Gestures',
    
    # Passing/Sharing
    'Giving Cheats', 'Sharing', 'passing notes', 'give_object_to_person',
    
    # Communication
    'Talking each other', 'Signalling', 'talking', 'discuss', 'discussion',
    
    # Other
    'restless', 'student_not_cheating', 'writing', 'reading'
]

# Class consolidation mapping (combine similar classes)
CLASS_CONSOLIDATION = {
    # All phone-related -> "phone"
    'Cellphone': 'phone', 'Mobile': 'phone', 'Phone': 'phone',
    'Using Phone': 'phone', 'Using_Mobile': 'phone', 'phone using': 'phone',
    'mobile using': 'phone', 'student_using_phone': 'phone', 'Using_phone': 'phone',
    'make_phone_call': 'phone', 'playing_phone': 'phone', 'mobile': 'phone',
    
    # All cheating materials -> "cheat_material"
    'Cheat_note': 'cheat_material', 'Cheating-Paper': 'cheat_material',
    'cheating-paper': 'cheat_material', 'Using_cheat_sheets': 'cheat_material',
    'chit': 'cheat_material', 'using chits': 'cheat_material',
    
    # All peeking -> "peeking"
    'Looking Over': 'peeking', 'Peeping': 'peeking', 'back peeking': 'peeking',
    'front peeking': 'peeking', 'side peeking': 'peeking',
    'looking into neighbors paper': 'peeking', 'looking around': 'peeking',
    
    # Turning back
    'Turning Back': 'turning_back', 'student_looking_backward': 'turning_back',
    'turn_head': 'turning_back',
    
    # Hand raise
    'Hand raise': 'hand_raise', 'hand-raising': 'hand_raise',
    'raising hand': 'hand_raise', 'Hand-Gestures': 'hand_raise',
    
    # Passing
    'Giving Cheats': 'passing', 'Sharing': 'passing',
    'passing notes': 'passing', 'give_object_to_person': 'passing',
    
    # Talking
    'Talking each other': 'talking', 'Signalling': 'talking',
    'talking': 'talking', 'discuss': 'talking', 'discussion': 'talking',
    
    # Cheating behavior
    'student_cheating': 'cheating', 'restless': 'suspicious',
    
    # Normal behavior (for negative samples)
    'student_not_cheating': 'normal', 'writing': 'normal', 'reading': 'normal',
}

# Final consolidated class names
CONSOLIDATED_CLASSES = [
    'phone',           # 0 - Mobile phone usage
    'cheat_material',  # 1 - Cheat sheets, notes, chits
    'peeking',         # 2 - Looking at others' papers
    'turning_back',    # 3 - Turning around
    'hand_raise',      # 4 - Hand raised
    'passing',         # 5 - Passing objects/notes
    'talking',         # 6 - Talking/signaling
    'cheating',        # 7 - General cheating behavior
    'suspicious',      # 8 - Suspicious behavior
    'normal',          # 9 - Normal behavior (negative samples)
]


def load_original_classes():
    """Load class names from original data.yaml."""
    data_yaml_path = DATASET_ROOT / "data.yaml"
    with open(data_yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    return data['names']


def create_class_mapping(original_classes):
    """Create mapping from original class indices to new consolidated indices."""
    mapping = {}
    for idx, class_name in enumerate(original_classes):
        if class_name in CLASS_CONSOLIDATION:
            new_class_name = CLASS_CONSOLIDATION[class_name]
            if new_class_name in CONSOLIDATED_CLASSES:
                mapping[idx] = CONSOLIDATED_CLASSES.index(new_class_name)
    return mapping


def create_filtered_dataset():
    """
    Create a filtered dataset with only relevant classes.
    Returns path to the new data.yaml file.
    """
    print("\n" + "="*60)
    print("CREATING FILTERED DATASET")
    print("="*60)
    
    # Load original classes
    original_classes = load_original_classes()
    print(f"Original classes: {len(original_classes)}")
    
    # Create class mapping
    class_mapping = create_class_mapping(original_classes)
    print(f"Mapped classes: {len(set(class_mapping.values()))}")
    
    # Create filtered dataset directory
    filtered_dir = DATASET_ROOT.parent / "filtered_malpractice_dataset"
    data_yaml_path = filtered_dir / 'data.yaml'
    
    # Check if already exists to skip processing
    if data_yaml_path.exists():
        print(f"✅ Found existing filtered dataset at: {filtered_dir}")
        print("   Skipping dataset creation to save time...")
        return data_yaml_path
        
    filtered_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    for split in ['train', 'valid', 'test']:
        (filtered_dir / split / 'images').mkdir(parents=True, exist_ok=True)
        (filtered_dir / split / 'labels').mkdir(parents=True, exist_ok=True)
    
    # Process each split
    total_images = 0
    total_annotations = 0
    
    for split in ['train', 'valid', 'test']:
        print(f"\nProcessing {split} split...")
        
        images_dir = DATASET_ROOT / split / 'images'
        labels_dir = DATASET_ROOT / split / 'labels'
        
        out_images_dir = filtered_dir / split / 'images'
        out_labels_dir = filtered_dir / split / 'labels'
        
        # Get all label files
        label_files = list(labels_dir.glob('*.txt'))
        
        copied_count = 0
        for label_file in label_files:
            # Read annotations
            with open(label_file, 'r') as f:
                lines = f.readlines()
            
            # Filter and remap annotations
            new_lines = []
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5:
                    class_idx = int(parts[0])
                    if class_idx in class_mapping:
                        new_class_idx = class_mapping[class_idx]
                        new_line = f"{new_class_idx} {' '.join(parts[1:])}\n"
                        new_lines.append(new_line)
            
            # Only copy if there are valid annotations
            if new_lines:
                # Copy image
                image_name = label_file.stem + '.jpg'
                image_path = images_dir / image_name
                
                # Try different extensions
                if not image_path.exists():
                    for ext in ['.png', '.jpeg', '.JPG', '.PNG']:
                        alt_path = images_dir / (label_file.stem + ext)
                        if alt_path.exists():
                            image_path = alt_path
                            image_name = alt_path.name
                            break
                
                if image_path.exists():
                    # Copy image
                    shutil.copy2(image_path, out_images_dir / image_name)
                    
                    # Write filtered labels
                    with open(out_labels_dir / label_file.name, 'w') as f:
                        f.writelines(new_lines)
                    
                    copied_count += 1
                    total_annotations += len(new_lines)
        
        total_images += copied_count
        print(f"  Copied {copied_count} images with relevant annotations")
    
    print(f"\nTotal images: {total_images}")
    print(f"Total annotations: {total_annotations}")
    
    # Create new data.yaml
    data_yaml = {
        'path': str(filtered_dir),
        'train': 'train/images',
        'val': 'valid/images',
        'test': 'test/images',
        'nc': len(CONSOLIDATED_CLASSES),
        'names': CONSOLIDATED_CLASSES
    }
    
    data_yaml_path = filtered_dir / 'data.yaml'
    with open(data_yaml_path, 'w') as f:
        yaml.dump(data_yaml, f, default_flow_style=False)
    
    print(f"\nFiltered dataset created at: {filtered_dir}")
    print(f"Data config: {data_yaml_path}")
    
    return data_yaml_path


def train_model(data_yaml_path):
    """Train the YOLO model on the filtered dataset."""
    print("\n" + "="*60)
    print("TRAINING CUSTOM MODEL")
    print("="*60)
    
    # Check GPU
    if torch.cuda.is_available():
        print(f"✅ GPU Available: {torch.cuda.get_device_name(0)}")
        print(f"   Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    else:
        print("⚠️ No GPU detected, training will be slow!")
        TRAINING_CONFIG["device"] = "cpu"
    
    # Check for existing checkpoint to resume
    checkpoint_path = OUTPUT_DIR / "malpractice_training" / "weights" / "last.pt"
    resume_training = False
    
    if checkpoint_path.exists():
        print(f"\n🔄 Found existing checkpoint: {checkpoint_path}")
        print("Resuming training from where it left off...")
        model = YOLO(checkpoint_path)
        resume_training = True
    else:
        # Load base model
        print(f"\nLoading base model: {BASE_MODEL}")
        model = YOLO(BASE_MODEL)
    
    # Start training
    print("\n🚀 Starting training...")
    if resume_training:
        print("   Mode: RESUMING (Efficiency is 100% preserved)")
    else:
        print("   Mode: FRESH START")
        
    print(f"   Epochs: {TRAINING_CONFIG['epochs']}")
    print(f"   Batch size: {TRAINING_CONFIG['batch_size']}")
    print(f"   Image size: {TRAINING_CONFIG['imgsz']}")
    print(f"   Device: {TRAINING_CONFIG['device']}")
    
    results = model.train(
        data=str(data_yaml_path),
        epochs=TRAINING_CONFIG["epochs"],
        batch=TRAINING_CONFIG["batch_size"],
        imgsz=TRAINING_CONFIG["imgsz"],
        device=TRAINING_CONFIG["device"],
        workers=TRAINING_CONFIG["workers"],
        patience=TRAINING_CONFIG["patience"],
        save_period=TRAINING_CONFIG["save_period"],
        exist_ok=TRAINING_CONFIG["exist_ok"] if not resume_training else False, # Don't overwrite if resuming
        pretrained=TRAINING_CONFIG["pretrained"],
        optimizer=TRAINING_CONFIG["optimizer"],
        lr0=TRAINING_CONFIG["lr0"],
        lrf=TRAINING_CONFIG["lrf"],
        warmup_epochs=TRAINING_CONFIG["warmup_epochs"],
        close_mosaic=TRAINING_CONFIG["close_mosaic"],
        project=str(OUTPUT_DIR),
        name="malpractice_training",
        verbose=True,
        resume=resume_training
    )
    
    return results


def export_best_model():
    """Copy the best model to the custom models directory."""
    print("\n" + "="*60)
    print("EXPORTING BEST MODEL")
    print("="*60)
    
    # Find the best model
    training_dir = OUTPUT_DIR / "malpractice_training"
    best_model_path = training_dir / "weights" / "best.pt"
    
    if best_model_path.exists():
        # Copy to custom models directory
        final_model_path = OUTPUT_DIR / "malpractice_detector.pt"
        shutil.copy2(best_model_path, final_model_path)
        print(f"✅ Best model saved to: {final_model_path}")
        
        # Also save last model as backup
        last_model_path = training_dir / "weights" / "last.pt"
        if last_model_path.exists():
            backup_path = OUTPUT_DIR / "malpractice_detector_last.pt"
            shutil.copy2(last_model_path, backup_path)
            print(f"✅ Last checkpoint saved to: {backup_path}")
        
        return final_model_path
    else:
        print(f"❌ Best model not found at {best_model_path}")
        return None


def main():
    """Main training pipeline."""
    print("\n" + "="*60)
    print("MALPRACTICE DETECTION MODEL TRAINING")
    print("="*60)
    print("\n⚠️ Your pre-trained models are safely backed up in:")
    print(f"   {OUTPUT_DIR.parent / 'pretrained'}")
    print("\n📁 Dataset location:")
    print(f"   {DATASET_ROOT}")
    
    # Step 1: Create filtered dataset
    print("\n[Step 1/3] Creating filtered dataset...")
    data_yaml_path = create_filtered_dataset()
    
    # Step 2: Train model
    print("\n[Step 2/3] Training model...")
    results = train_model(data_yaml_path)
    
    # Step 3: Export best model
    print("\n[Step 3/3] Exporting best model...")
    model_path = export_best_model()
    
    if model_path:
        print("\n" + "="*60)
        print("✅ TRAINING COMPLETE!")
        print("="*60)
        print(f"\n📦 Custom model saved to: {model_path}")
        print("\n🔄 To switch to the custom model, edit model_config.py:")
        print('   ACTIVE_MODEL_PRESET = "custom"')
        print("\n🔙 To switch back to pre-trained models:")
        print('   ACTIVE_MODEL_PRESET = "pretrained"')
        print("="*60 + "\n")
    
    return results


if __name__ == "__main__":
    main()
