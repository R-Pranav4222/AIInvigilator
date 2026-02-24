"""Test Path.stem behavior"""
from pathlib import Path

label_file = Path(r"e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8\train\labels\0000000100_jpg.rf.11cfdac911ff6378e12657fb52c24ab6.txt")

print(f"Full name: {label_file.name}")
print(f"Stem: {label_file.stem}")
print(f"Stem length: {len(label_file.stem)}")

# Build image path like in filter script
image_file = (label_file.parent.parent / 'images' / label_file.stem).with_suffix('.jpg')
print(f"\nImage path: {image_file}")
print(f"Image exists: {image_file.exists()}")

# Try direct approach
image_file2 = Path(r"e:\witcher\AIINVIGILATOR\Dataset\major-aast-dataset2.v1i.yolov8\train\images") / f"{label_file.stem}.jpg"
print(f"\nDirect approach: {image_file2}")
print(f"Exists: {image_file2.exists()}")
