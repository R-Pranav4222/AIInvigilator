"""
Quick dataset class count using grep
"""
import subprocess
import os

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
print("DATASET CLASS DISTRIBUTION (Quick Count)")
print("="*60)

results = {}
total = 0

for class_id, class_name in CLASSES.items():
    # Count lines starting with this class_id
    cmd = f'powershell -Command "(Get-Content {labels_dir}\\*.txt | Select-String ''^{class_id} '').Count"'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
        results[class_id] = (class_name, count)
        total += count
    except:
        results[class_id] = (class_name, 0)

print(f"\n{'Class':<20} {'Count':<10} {'Percentage'}")
print("="*60)

for class_id in sorted(results.keys(), key=lambda x: int(x)):
    class_name, count = results[class_id]
    percentage = (count / total * 100) if total > 0 else 0
    emoji = '✅' if count > 1000 else '⚠️' if count > 100 else '❌'
    print(f"{emoji} {class_name:<17} {count:<10} {percentage:.2f}%")

print("="*60)
print(f"Total annotations: {total}\n")

print("\n❌ CRITICAL ISSUES:")
for class_id, (class_name, count) in results.items():
    if count < 500:
        print(f"  - {class_name}: Only {count} examples (needs 5000+)")
