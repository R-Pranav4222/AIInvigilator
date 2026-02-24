"""
Test the filtering logic on a single file
"""
from pathlib import Path
import yaml

# Load data.yaml
dataset_path = Path(r"e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8")
with open(dataset_path / 'data.yaml', 'r') as f:
    data = yaml.safe_load(f)

old_class_names = data['names']

# Test on first label file
label_file = Path(r"e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8\train\labels\0000000100_jpg.rf.11cfdac911ff6378e12657fb52c24ab6.txt")

print(f"Testing label file: {label_file.name}")
print(f"Exists: {label_file.exists()}\n")

# Read and process
with open(label_file, 'r') as f:
    lines = f.readlines()

print(f"Label file has {len(lines)} lines\n")

# Class mapping (digit classes to normal)
CLASS_MAPPING = {
    '0': 9, '1': 9, '2': 9, '3': 9, '4': 9, 
    '5': 9, '6': 9, '7': 9, '8': 9, '9': 9,
}

# Process
new_lines = []
for line in lines[:5]:  # First 5 lines
    parts = line.strip().split()
    if parts:
        old_class_id = int(parts[0])
        old_class_name = old_class_names[old_class_id]
        
        print(f"Line: {line.strip()}")
        print(f"  Class ID: {old_class_id}")
        print(f"  Class name: '{old_class_name}'")
        print(f"  In mapping: {old_class_name in CLASS_MAPPING}")
        
        if old_class_name in CLASS_MAPPING:
            new_class_id = CLASS_MAPPING[old_class_name]
            parts[0] = str(new_class_id)
            new_lines.append(' '.join(parts))
            print(f"  ✅ Mapped to class {new_class_id}")
        else:
            print(f"  ❌ NOT in mapping")
        print()

print(f"\nResult: {len(new_lines)} lines would be kept")
print(f"New labels would be: {'YES' if new_lines else 'NO (skipped)'}\n")

# Test image file lookup
image_file = Path(r"e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8\train\images") / label_file.stem
image_file = image_file.with_suffix('.jpg')
print(f"Image file path: {image_file}")
print(f"Image exists: {image_file.exists()}")
