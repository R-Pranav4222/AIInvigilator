"""
Count class distribution in training dataset
"""
import os
from collections import Counter

# Class mapping
CLASSES = {
    '0': 'phone',
    '1': 'cheat_material',
    '2': 'peeking',
    '3': 'turning_back',
    '4': 'hand_raise',
    '5': 'passing',
    '6': 'talking',
    '7': 'cheating',
    '8': 'suspicious',
    '9': 'normal'
}

labels_dir = r"E:\witcher\AIINVIGILATOR\Dataset\filtered_malpractice_dataset\train\labels"

print("="*60)
print("DATASET CLASS DISTRIBUTION")
print("="*60)

class_counts = Counter()

# Count classes in all label files
label_files = [f for f in os.listdir(labels_dir) if f.endswith('.txt')]
print(f"\nTotal label files: {len(label_files)}")

for label_file in label_files:
    with open(os.path.join(labels_dir, label_file), 'r') as f:
        lines = f.readlines()
        for line in lines:
            parts = line.strip().split()
            if parts:
                class_id = parts[0]
                class_counts[class_id] += 1

print(f"\n{'Class':<20} {'Count':<10} {'Percentage'}")
print("="*60)

total = sum(class_counts.values())
for class_id, count in sorted(class_counts.items(), key=lambda x: int(x[0])):
    class_name = CLASSES.get(class_id, f'Unknown ({class_id})')
    percentage = (count / total * 100) if total > 0 else 0
    print(f"{class_name:<20} {count:<10} {percentage:.2f}%")

print("="*60)
print(f"Total annotations: {total}\n")

# Identify problematic classes (< 5% of dataset)
print("\n⚠️ CLASSES WITH LOW REPRESENTATION (< 5%):")
for class_id, count in class_counts.items():
    percentage = (count / total * 100)
    if percentage < 5:
        class_name = CLASSES.get(class_id, f'Unknown ({class_id})')
        print(f"  - {class_name}: {count} ({percentage:.2f}%)")
