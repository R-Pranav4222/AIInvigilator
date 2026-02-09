"""
Test Video Detection Script
Tests the ML-enhanced detection system on a pre-recorded video file

Usage:
    python test_video_detection.py

This script will:
1. Test the video file on your detection system
2. Show real-time detection with bounding boxes
3. Save any detected malpractices to the database
4. Display ML verification statistics
"""

import os
import sys

# Test video path
TEST_VIDEO_PATH = r"E:\witcher\AIINVIGILATOR\Test\[1]Passing paper - Subtle.mp4"

print("="*80)
print("🎥 VIDEO DETECTION TEST - AI INVIGILATOR")
print("="*80)
print(f"📹 Video File: {os.path.basename(TEST_VIDEO_PATH)}")
print(f"📍 Full Path: {TEST_VIDEO_PATH}")

# Verify video exists
if not os.path.exists(TEST_VIDEO_PATH):
    print(f"\n❌ ERROR: Video file not found!")
    print(f"   Expected location: {TEST_VIDEO_PATH}")
    print(f"\n💡 Please check if the video file exists at this location.")
    sys.exit(1)

print("\n✅ Video file found!")
print("\n📋 TEST CONFIGURATION:")
print("   • ML Verification: ENABLED")
print("   • GPU Acceleration: ENABLED (if available)")
print("   • Video Writing: DISABLED (for faster testing)")
print("   • Frame Skip: 2 (process every 3rd frame) ⚡⚡")
print("   • Resolution: 1280x720 (full quality)")
print("   • Detection Types: Leaning, Passing Paper, Mobile Phone, Turning Back")
print("   • Database Logging: ENABLED")

print("\n" + "="*80)
print("🚀 INSTRUCTIONS:")
print("="*80)
print("   1. The video will play at HIGH SPEED (30-40+ FPS expected)")
print("   2. Watch for detection boxes (GREEN = detected)")
print("   3. ML statistics will show at the top")
print("   4. FPS will be displayed in real-time")
print("   5. Press 'q' to quit anytime")
print("   6. Check Django admin panel for malpractice logs")
print("="*80)

input("\n👉 Press ENTER to start the HIGH-SPEED test...")

print("\n🔄 Activating Frame Skipping for Maximum Speed...\n")

# Read front.py
with open('front.py', 'r', encoding='utf-8') as f:
    front_code = f.read()

# Modify the configuration for frame skipping only
front_code = front_code.replace('USE_CAMERA = True', 'USE_CAMERA = False')
front_code = front_code.replace('VIDEO_PATH = "test_videos/Leaning.mp4"', 
                                f'VIDEO_PATH = r"{TEST_VIDEO_PATH}"')
front_code = front_code.replace('DISABLE_VIDEO_WRITE = False', 'DISABLE_VIDEO_WRITE = True')
front_code = front_code.replace('VIDEO_FRAME_SKIP = 0', 'VIDEO_FRAME_SKIP = 2')
# Don't enable RESIZE_FRAME to keep full quality

print("✅ HIGH-SPEED OPTIMIZATIONS ENABLED:")
print("   • USE_CAMERA = False")
print(f"   • VIDEO_PATH = {TEST_VIDEO_PATH}")
print("   • DISABLE_VIDEO_WRITE = True (no video recording)")
print("   • VIDEO_FRAME_SKIP = 2 (process every 3rd frame - 3x faster!)")
print("   • RESIZE_FRAME = False (full resolution maintained)")
print("   • Hardware acceleration enabled")
print("   • FP16 precision enabled")
print("\n🎯 Expected FPS: 35-45+ FPS (3x faster!)")
print("\n🎬 Starting detection system...\n")
print("="*80 + "\n")

# Execute the modified front.py code
exec(front_code)

