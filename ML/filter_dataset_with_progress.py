"""
Dataset Filtering Script with Real-Time Progress Tracking
Filters major-aast-dataset (152 classes) to relevant invigilator classes (10 classes)
Author: AI Invigilator System
"""

import os
import shutil
import yaml
from pathlib import Path
from tqdm import tqdm
import time
from datetime import timedelta

# Class mapping: major-aast-dataset classes -> our relevant classes
CLASS_MAPPING = {
    # Digit classes (0-9) - these are generic person/student detections -> map to normal
    '0': 9, '1': 9, '2': 9, '3': 9, '4': 9, 
    '5': 9, '6': 9, '7': 9, '8': 9, '9': 9,
    
    # Phone related -> 0: phone
    'Cellphone': 0, 'Mobile': 0, 'Phone': 0, 'Phone use': 0, 'Using Phone': 0, 
    'Using_Mobile': 0, 'Using_phone': 0, 'mobile': 0, 'phone': 0, 'phone using': 0,
    'student_using_phone': 0, 'playing_phone': 0, 'make_phone_call': 0,
    'taking photo using phone': 0, 'using_mobile': 0,
    
    # Cheat material -> 1: cheat_material
    'Cheat_note': 1, 'Cheating-Paper': 1, 'cheating-paper': 1, 'chit': 1,
    'using chits': 1, 'Using_cheat_sheets': 1, 'paper': 1,
    
    # Peeking -> 2: peeking
    'Peeping': 2, 'Looking Over': 2, 'back peeking': 2, 'front peeking': 2,
    'side peeking': 2, 'looking into neighbors paper': 2, 'looking at other person': 2,
    
    # Turning back -> 3: turning_back
    'Turning Back': 3, 'turn_head': 3, 'student_looking_backward': 3,
    
    # Hand raise -> 4: hand_raise
    'Hand raise': 4, 'hand-raising': 4, 'raising hand': 4, 'handra': 4,
    'raise_head': 4,
    
    # Passing -> 5: passing
    'Giving Cheats': 5, 'Sharing': 5, 'passing notes': 5, 'give_object_to_person': 5,
    
    # Talking -> 6: talking
    'Talking each other': 6, 'talking': 6, 'discussion': 6, 'discuss': 6,
    'class activity discussion': 6,
    
    # Cheating -> 7: cheating
    'student_cheating': 7, 'Signalling': 7, 'Hand-Gestures': 7, 'gesture using': 7,
    
    # Suspicious -> 8: suspicious
    'restless': 8, 'looking around': 8, 'confused state': 8, 'frustrated': 8,
    'yawning': 8, 'sleeping': 8, 'sleep': 8, 'Sleeping': 8, 'bend': 8,
    
    # Normal -> 9: normal
    'student_not_cheating': 9, 'normal_person': 9, 'student_sitting': 9,
    'student_writing': 9, 'writing': 9, 'Write': 9, 'answering the question': 9,
    'student_looking_forward': 9, 'student_looking_down': 9, 'upright': 9,
    'reading': 9, 'read': 9, 'listening': 9, 'thinking': 9, 'bow_head': 9,
    'bowing': 9, 'student_looking_up': 9, 'book': 9,
}

# Our target classes
TARGET_CLASSES = [
    'phone', 'cheat_material', 'peeking', 'turning_back', 'hand_raise',
    'passing', 'talking', 'cheating', 'suspicious', 'normal'
]


def load_yaml(yaml_path):
    """Load YAML file"""
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)


def save_yaml(data, yaml_path):
    """Save YAML file"""
    with open(yaml_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def count_files(directory):
    """Count total files for progress tracking"""
    return sum(1 for _ in Path(directory).rglob('*.txt'))


def remap_label_file(label_path, old_class_names):
    """
    Remap label file from old classes to new classes
    Returns None if no relevant classes found
    """
    new_lines = []
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            
            old_class_id = int(parts[0])
            if old_class_id >= len(old_class_names):
                continue
                
            old_class_name = old_class_names[old_class_id]
            
            # Check if this class should be remapped
            if old_class_name in CLASS_MAPPING:
                new_class_id = CLASS_MAPPING[old_class_name]
                parts[0] = str(new_class_id)
                new_lines.append(' '.join(parts))
    
    return new_lines if new_lines else None


def filter_dataset(source_dataset_path, target_dataset_path):
    """
    Filter dataset with real-time progress tracking
    """
    print("\n" + "="*70)
    print("🎯 DATASET FILTERING - AI INVIGILATOR SYSTEM")
    print("="*70)
    print(f"📁 Source: {source_dataset_path}")
    print(f"📁 Target: {target_dataset_path}")
    print(f"🎯 Classes: 152 → 10 relevant classes")
    print("="*70 + "\n")
    
    # Load source data.yaml
    source_yaml_path = Path(source_dataset_path) / 'data.yaml'
    source_data = load_yaml(source_yaml_path)
    old_class_names = source_data['names']
    
    print(f"✅ Loaded {len(old_class_names)} classes from source dataset\n")
    
    # Create target directory structure
    target_path = Path(target_dataset_path)
    target_path.mkdir(parents=True, exist_ok=True)
    
    splits = ['train', 'valid', 'test']
    stats = {split: {'images': 0, 'labels': 0, 'skipped': 0} for split in splits}
    
    start_time = time.time()
    
    # Process each split
    for split in splits:
        print(f"\n{'━'*70}")
        print(f"📊 Processing {split.upper()} split")
        print(f"{'━'*70}")
        
        source_split_path = Path(source_dataset_path) / split
        target_split_path = target_path / split
        
        # Create directories
        (target_split_path / 'images').mkdir(parents=True, exist_ok=True)
        (target_split_path / 'labels').mkdir(parents=True, exist_ok=True)
        
        # Count files for progress bar
        label_files = list((source_split_path / 'labels').glob('*.txt'))
        total_files = len(label_files)
        
        print(f"📁 Found {total_files} label files")
        
        # Process with progress bar
        with tqdm(total=total_files, 
                  desc=f"Filtering {split}",
                  unit="files",
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
                  colour='green') as pbar:
            
            for label_file in label_files:
                # Remap labels
                new_labels = remap_label_file(label_file, old_class_names)
                
                # Debug first 3 files
                if pbar.n < 3:
                    print(f"\n[DEBUG] File #{pbar.n+1}: {label_file.name}")
                    print(f"  Remapped: {len(new_labels) if new_labels else 0} lines")
                
                if new_labels:
                    # Copy image (don't use with_suffix - it treats hash dots as extensions!)
                    image_file = source_split_path / 'images' / f"{label_file.stem}.jpg"
                    
                    if pbar.n < 3:
                        print(f"  Image: {image_file.name}")
                        print(f"  Exists: {image_file.exists()}")
                    
                    if not image_file.exists():
                        image_file = source_split_path / 'images' / f"{label_file.stem}.png"
                    
                    if image_file.exists():
                        target_image = target_split_path / 'images' / image_file.name
                        shutil.copy2(image_file, target_image)
                        stats[split]['images'] += 1
                        
                        if pbar.n < 3:
                            print(f"  ✅ Copied!")
                        
                        # Save remapped label
                        target_label = target_split_path / 'labels' / label_file.name
                        with open(target_label, 'w') as f:
                            f.write('\n'.join(new_labels))
                        stats[split]['labels'] += 1
                    else:
                        # Image not found - increment skipped
                        stats[split]['skipped'] += 1
                        if pbar.n < 3:
                            print(f"  ❌ Image not found")
                else:
                    stats[split]['skipped'] += 1
                    if pbar.n < 3:
                        print(f"  ❌ No remapped labels")
                
                pbar.update(1)
                
                # Update postfix with current stats
                pbar.set_postfix({
                    'kept': stats[split]['images'],
                    'skipped': stats[split]['skipped'],
                    'kept%': f"{(stats[split]['images']/total_files*100):.1f}%" if total_files > 0 else "0.0%"
                })
        
        print(f"✅ {split.upper()} complete: {stats[split]['images']} images kept, {stats[split]['skipped']} skipped")
    
    # Create data.yaml for filtered dataset
    print(f"\n{'━'*70}")
    print("📝 Creating data.yaml configuration")
    print(f"{'━'*70}")
    
    target_yaml_data = {
        'names': TARGET_CLASSES,
        'nc': len(TARGET_CLASSES),
        'path': str(target_path.absolute()),
        'train': 'train/images',
        'val': 'valid/images',
        'test': 'test/images'
    }
    
    save_yaml(target_yaml_data, target_path / 'data.yaml')
    
    # Final statistics
    elapsed_time = time.time() - start_time
    total_images = sum(stats[split]['images'] for split in splits)
    total_skipped = sum(stats[split]['skipped'] for split in splits)
    total_processed = total_images + total_skipped
    
    print(f"\n{'='*70}")
    print("✨ FILTERING COMPLETE!")
    print(f"{'='*70}")
    print(f"⏱️  Total Time: {timedelta(seconds=int(elapsed_time))}")
    print(f"📊 Total Processed: {total_processed:,} files")
    print(f"✅ Images Kept: {total_images:,} ({total_images/total_processed*100:.1f}%)")
    print(f"❌ Skipped: {total_skipped:,} ({total_skipped/total_processed*100:.1f}%)")
    print(f"\n📁 Dataset saved to: {target_path.absolute()}")
    print(f"{'='*70}\n")
    
    # Breakdown by split
    print("📊 Breakdown by Split:")
    print(f"{'─'*70}")
    for split in splits:
        print(f"  {split.capitalize():8s}: {stats[split]['images']:6,} images")
    print(f"{'─'*70}\n")
    
    return target_path


if __name__ == "__main__":
    # Paths
    SOURCE_DATASET = r"e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8"
    TARGET_DATASET = r"e:\witcher\AIINVIGILATOR\Dataset\custom_filtered_dataset"
    
    print("\n🚀 Starting Dataset Filtering Process...")
    print("⚠️  This may take several minutes depending on dataset size\n")
    
    try:
        filtered_path = filter_dataset(SOURCE_DATASET, TARGET_DATASET)
        print("✅ Dataset filtering completed successfully!")
        print(f"📂 Filtered dataset location: {filtered_path}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        print("💡 You can safely restart this script - it will overwrite existing files")
        
    except Exception as e:
        print(f"\n❌ Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
