"""
Sample dataset to estimate class distribution
"""
import os
import random
from collections import Counter

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
print("DATASET CLASS DISTRIBUTION (Sample of 1000 files)")
print("="*60)

class_counts = Counter()

# Get all label files
label_files = [f for f in os.listdir(labels_dir) if f.endswith('.txt')]
total_files = len(label_files)
print(f"\nTotal files: {total_files}")

# Sample 1000 random files
sample_size = min(1000, total_files)
sample_files = random.sample(label_files, sample_size)
print(f"Sampling: {sample_size} files\n")

# Count classes in sampled files
for label_file in sample_files:
    try:
        with open(os.path.join(labels_dir, label_file), 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            for line in lines:
                parts = line.strip().split()
                if parts:
                    class_id = parts[0]
                    class_counts[class_id] += 1
    except:
        pass

print(f"{'Class':<20} {'Count (sample)':<15} {'Est. Total':<15} {'%'}")
print("="*70)

total_in_sample = sum(class_counts.values())
multiplier = total_files / sample_size

for class_id in sorted(CLASSES.keys(), key=lambda x: int(x)):
    class_name = CLASSES[class_id]
    count = class_counts.get(class_id, 0)
    estimated_total = int(count * multiplier)
    percentage = (count / total_in_sample * 100) if total_in_sample > 0 else 0
    
    emoji = '✅' if estimated_total > 1000 else '⚠️' if estimated_total > 100 else '❌'
    print(f"{emoji} {class_name:<17} {count:<15} {estimated_total:<15} {percentage:.1f}%")

print("="*70)
print(f"Total annotations in sample: {total_in_sample}")
print(f"Estimated total: {int(total_in_sample * multiplier)}\n")

print("\n❌ CRITICAL: Classes with < 500 estimated examples:")
for class_id in sorted(CLASSES.keys(), key=lambda x: int(x)):
    class_name = CLASSES[class_id]
    count = class_counts.get(class_id, 0)
    estimated = int(count * multiplier)
    if estimated < 500:
        print(f"  🔴 {class_name}: ~{estimated} (INSUFFICIENT DATA FOR ML)")
