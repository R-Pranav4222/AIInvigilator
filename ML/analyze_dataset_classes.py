"""
Quick analysis of the major-aast-dataset to see what class IDs are actually used
"""
import yaml
from pathlib import Path
from collections import Counter

# Load data.yaml
dataset_path = Path(r"e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8")
with open(dataset_path / 'data.yaml', 'r') as f:
    data = yaml.safe_load(f)

class_names = data['names']
print(f"Total classes: {len(class_names)}\n")
print("First 20 class names:")
for i, name in enumerate(class_names[:20]):
    print(f"  {i}: {name}")

# Sample some label files to see what's actually used
label_dir = dataset_path / 'train' / 'labels'
label_files = list(label_dir.glob('*.txt'))[:1000]  # Sample 1000 files

class_counter = Counter()

print(f"\nAnalyzing {len(label_files)} label files...")
for label_file in label_files:
    with open(label_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                class_id = int(parts[0])
                class_counter[class_id] += 1

print(f"\nTop 20 most common class IDs found:")
for class_id, count in class_counter.most_common(20):
    if class_id < len(class_names):
        class_name = class_names[class_id]
        print(f"  Class {class_id:3d} ('{class_name}'):  {count:6d} instances")
    else:
        print(f"  Class {class_id:3d} (OUT OF RANGE): {count:6d} instances")

print("\n" + "="*70)
print("CONCLUSION:")
print("="*70)
print("The dataset uses numeric class IDs (0-9, etc.) not the meaningful names!")
print("We need to check what these digit classes actually represent")
