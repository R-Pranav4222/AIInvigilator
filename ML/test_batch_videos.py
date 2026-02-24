"""
Fast Batch Video Testing
Test multiple videos quickly
"""

from test_video import test_video
from pathlib import Path

# Video paths
VIDEOS = [
    r"E:\witcher\[1]Passing paper - Subtle.mp4",
    # Add more video paths here
]

def batch_test():
    """Test multiple videos in batch"""
    print("\n" + "="*80)
    print("🎬 BATCH VIDEO TESTING - FAST MODE")
    print("="*80)
    print(f"📁 Testing {len(VIDEOS)} videos")
    print("⚡ Settings: conf=0.25, inference=640px, speed mode ON")
    print("="*80 + "\n")
    
    results = []
    
    for i, video_path in enumerate(VIDEOS, 1):
        video_file = Path(video_path)
        if not video_file.exists():
            print(f"❌ Video {i}/{len(VIDEOS)}: File not found - {video_path}\n")
            continue
        
        print(f"\n{'='*80}")
        print(f"🎥 VIDEO {i}/{len(VIDEOS)}: {video_file.name}")
        print(f"{'='*80}\n")
        
        # Process with fast settings
        test_video(
            video_path=video_path,
            save_output=True,
            conf_threshold=0.25,
            inference_size=640,
            speed_mode=True
        )
        
        print(f"\n✅ Video {i}/{len(VIDEOS)} completed!\n")
    
    print("\n" + "="*80)
    print("✅ BATCH TESTING COMPLETED")
    print("="*80)
    print("📁 All outputs saved to: E:\\witcher\\AIINVIGILATOR\\AIINVIGILATOR\\ML\\")
    print("="*80 + "\n")

if __name__ == '__main__':
    batch_test()
