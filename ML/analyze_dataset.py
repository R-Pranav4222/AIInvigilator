# analyze_dataset.py
"""
Analyze the malpractice dataset to:
1. Count annotations per class
2. Identify which relevant classes actually exist
3. Estimate training time
"""

import os
from pathlib import Path
from collections import Counter
import yaml

# Dataset path
DATASET_ROOT = Path(r"E:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8")

def load_classes():
    """Load class names from data.yaml."""
    with open(DATASET_ROOT / "data.yaml", 'r') as f:
        data = yaml.safe_load(f)
    return data['names']

def count_annotations():
    """Count annotations per class across all splits."""
    class_names = load_classes()
    class_counts = Counter()
    total_images = 0
    images_with_annotations = 0
    
    for split in ['train', 'valid', 'test']:
        labels_dir = DATASET_ROOT / split / 'labels'
        if not labels_dir.exists():
            continue
            
        label_files = list(labels_dir.glob('*.txt'))
        total_images += len(label_files)
        
        for label_file in label_files:
            with open(label_file, 'r') as f:
                lines = f.readlines()
            
            if lines:
                images_with_annotations += 1
                
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5:
                    class_idx = int(parts[0])
                    if class_idx < len(class_names):
                        class_counts[class_names[class_idx]] += 1
    
    return class_counts, class_names, total_images, images_with_annotations

def main():
    print("="*70)
    print("DATASET ANALYSIS")
    print("="*70)
    
    class_counts, class_names, total_images, images_with_annotations = count_annotations()
    
    print(f"\nTotal images: {total_images:,}")
    print(f"Images with annotations: {images_with_annotations:,}")
    print(f"Total classes in dataset: {len(class_names)}")
    print(f"Classes with annotations: {len(class_counts)}")
    
    # Relevant classes for malpractice detection
    RELEVANT_KEYWORDS = [
        'phone', 'mobile', 'cellphone', 'using_phone', 'using phone',
        'cheat', 'chit', 'note',
        'peep', 'look', 'peeking',
        'turn', 'back', 'backward',
        'hand', 'raise', 'raising',
        'pass', 'share', 'giving', 'transmit',
        'talk', 'signal', 'discuss',
        'suspicious', 'restless', 'cheating',
        'student', 'write', 'read', 'normal'
    ]
    
    print("\n" + "="*70)
    print("RELEVANT CLASSES FOR MALPRACTICE DETECTION")
    print("="*70)
    
    relevant_classes = {}
    total_relevant_annotations = 0
    
    for class_name, count in sorted(class_counts.items(), key=lambda x: -x[1]):
        class_lower = class_name.lower()
        is_relevant = any(keyword in class_lower for keyword in RELEVANT_KEYWORDS)
        
        if is_relevant:
            relevant_classes[class_name] = count
            total_relevant_annotations += count
    
    # Print relevant classes
    print(f"\n{'Class Name':<45} {'Count':>10} {'Category':<20}")
    print("-"*75)
    
    # Categorize
    categories = {
        'PHONE/MOBILE': [],
        'CHEATING MATERIAL': [],
        'PEEKING/LOOKING': [],
        'TURNING BACK': [],
        'HAND RAISE': [],
        'PASSING/SHARING': [],
        'TALKING': [],
        'OTHER RELEVANT': []
    }
    
    for class_name, count in sorted(relevant_classes.items(), key=lambda x: -x[1]):
        cl = class_name.lower()
        if 'phone' in cl or 'mobile' in cl or 'cellphone' in cl:
            categories['PHONE/MOBILE'].append((class_name, count))
        elif 'cheat' in cl or 'chit' in cl or 'note' in cl:
            categories['CHEATING MATERIAL'].append((class_name, count))
        elif 'peep' in cl or ('look' in cl and ('neighbor' in cl or 'over' in cl or 'around' in cl or 'back' in cl)):
            categories['PEEKING/LOOKING'].append((class_name, count))
        elif 'turn' in cl or 'backward' in cl:
            categories['TURNING BACK'].append((class_name, count))
        elif 'hand' in cl or 'raise' in cl or 'raising' in cl:
            categories['HAND RAISE'].append((class_name, count))
        elif 'pass' in cl or 'share' in cl or 'giving' in cl or 'transmit' in cl:
            categories['PASSING/SHARING'].append((class_name, count))
        elif 'talk' in cl or 'signal' in cl or 'discuss' in cl:
            categories['TALKING'].append((class_name, count))
        else:
            categories['OTHER RELEVANT'].append((class_name, count))
    
    for category, items in categories.items():
        if items:
            print(f"\n📌 {category}")
            for class_name, count in items:
                print(f"   {class_name:<42} {count:>10,}")
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Relevant classes found: {len(relevant_classes)}")
    print(f"Total relevant annotations: {total_relevant_annotations:,}")
    
    # Estimate training time
    print("\n" + "="*70)
    print("TRAINING TIME ESTIMATE (RTX 3050 6GB)")
    print("="*70)
    
    # Training parameters
    images_to_train = total_relevant_annotations  # Approximate
    epochs = 100
    batch_size = 16
    time_per_image_ms = 15  # Approximate for RTX 3050 with YOLO11n
    
    # Calculations
    batches_per_epoch = images_to_train / batch_size
    time_per_epoch_sec = (batches_per_epoch * time_per_image_ms * batch_size) / 1000
    total_time_sec = time_per_epoch_sec * epochs
    total_time_hours = total_time_sec / 3600
    
    print(f"\nEstimated images to process: {images_to_train:,}")
    print(f"Epochs: {epochs}")
    print(f"Batch size: {batch_size}")
    print(f"\nEstimated time per epoch: {time_per_epoch_sec/60:.1f} minutes")
    print(f"Estimated total training time: {total_time_hours:.1f} hours ({total_time_hours/24:.1f} days)")
    
    print("\n⚠️  Notes:")
    print("   - First epoch is slower (data loading)")
    print("   - Early stopping may reduce time if model converges quickly")
    print("   - Actual time depends on dataset filtering")
    
    # Quick training option
    print("\n" + "="*70)
    print("QUICK TRAINING OPTIONS")
    print("="*70)
    print("\nOption 1: Full training (100 epochs)")
    print(f"   Time: ~{total_time_hours:.0f} hours ({total_time_hours/24:.1f} days)")
    print(f"   Best accuracy but longest time")
    
    quick_epochs = 30
    quick_time = total_time_hours * (quick_epochs / epochs)
    print(f"\nOption 2: Quick training ({quick_epochs} epochs)")
    print(f"   Time: ~{quick_time:.0f} hours")
    print(f"   Good accuracy, faster")
    
    sample_pct = 0.1
    sample_time = total_time_hours * sample_pct * (quick_epochs / epochs)
    print(f"\nOption 3: Sample training (10% data, {quick_epochs} epochs)")
    print(f"   Time: ~{sample_time:.1f} hours")
    print(f"   For testing pipeline only")
    
    return relevant_classes, total_relevant_annotations

if __name__ == "__main__":
    main()
