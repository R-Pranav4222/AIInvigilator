"""
Download Roboflow Dataset for Exam Malpractice Detection
Dataset: https://universe.roboflow.com/research-xfm0x/major-aast-dataset-3d
"""

from roboflow import Roboflow
import os

def download_dataset():
    """
    Download the Major AAST Dataset from Roboflow
    You'll need a Roboflow API key (free account)
    Get it from: https://app.roboflow.com/settings/api
    """
    
    # Set your Roboflow API key here
    API_KEY = "oL4YKGjfGLGDnovxVvcx"  # Replace with your actual API key
    
    print("⚠️  NOTE: This dataset is on Roboflow Universe and may not be directly downloadable.")
    print("📌 Alternative approach: Use Roboflow CLI or fork the dataset first.\n")
    
    # Initialize Roboflow
    rf = Roboflow(api_key=API_KEY)
    
    print("🔍 Connecting to Roboflow...")
    
    # Try Universe download method
    try:
        print("📦 Attempting Universe dataset download...")
        print("💡 If this fails, you'll need to:")
        print("   1. Go to: https://universe.roboflow.com/research-xfm0x/major-aast-dataset-3d")
        print("   2. Click 'Fork Dataset' button")
        print("   3. This will copy it to YOUR workspace")
        print("   4. Then download from YOUR workspace\n")
        
        # Try direct download from Universe
        workspace = rf.workspace("research-xfm0x")
        project = workspace.project("major-aast-dataset-3d")
        
        # Try to get project info
        print(f"✅ Project found: {project.name}")
        print(f"📁 Project ID: {project.id}")
        
        # Attempt download - this might fail for Universe projects
        print("\n🚀 Attempting download...")
        print("⏳ This may take 1-2 hours for 214k images (~50-100GB)...\n")
        
        # For Universe projects, we need to use a different approach
        # Try getting the dataset without version number
        dataset = project.download("yolov8", location="./datasets/major-aast")
        
        print(f"\n✅ Dataset downloaded successfully!")
        print(f"📂 Location: ./datasets/major-aast")
        print(f"\n📁 Dataset structure:")
        print("  - train/: Training images and labels")
        print("  - valid/: Validation images and labels")  
        print("  - test/: Test images and labels")
        print("  - data.yaml: Dataset configuration\n")
        
        return dataset
        
    except Exception as e:
        print(f"\n❌ Direct download failed: {str(e)}\n")
        print("="*70)
        print("🔧 SOLUTION: Fork the dataset first")
        print("="*70)
        print("\n📋 Steps to fork and download:")
        print("1. Go to: https://universe.roboflow.com/research-xfm0x/major-aast-dataset-3d")
        print("2. Click the 'Fork Dataset' button (top right)")
        print("3. Wait for forking to complete (~5 minutes)")
        print("4. The dataset will appear in YOUR workspace")
        print("5. Update this script with YOUR workspace name")
        print("6. Run this script again\n")
        
        print("💡 OR Download manually:")
        print("1. Go to the dataset page")
        print("2. Click 'Download Dataset'")
        print("3. Select 'YOLO v8' format")
        print("4. Click 'Download ZIP'")
        print("5. Extract to: ./datasets/major-aast")
        print("\n" + "="*70)
        
        raise

def get_dataset_info():
    """Display information about downloading the dataset"""
    print("\n" + "="*70)
    print("ROBOFLOW DATASET DOWNLOAD GUIDE")
    print("="*70)
    print("\n📋 Dataset: Major AAST Dataset (213k images, 20 classes)")
    print("🔗 URL: https://universe.roboflow.com/research-xfm0x/major-aast-dataset-3d")
    
    print("\n📝 Steps to download:")
    print("1. Create a free Roboflow account at: https://roboflow.com")
    print("2. Get your API key from: https://app.roboflow.com/settings/api")
    print("3. Install Roboflow package: pip install roboflow")
    print("4. Update API_KEY in this script")
    print("5. Run: python download_roboflow_dataset.py")
    
    print("\n⚠️  Note: 213k images = ~50-100GB. Ensure you have enough disk space!")
    
    print("\n💡 Alternative: Download specific subset")
    print("   - Can download only validation set for testing")
    print("   - Use Roboflow's web interface to export smaller batches")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    # Show instructions
    get_dataset_info()
    
    # Auto-start download (API key already configured)
    print("🚀 Starting download with configured API key...\n")
    
    try:
        download_dataset()
    except Exception as e:
        print(f"\n❌ Error downloading dataset: {e}")
        print("\nTroubleshooting:")
        print("1. Verify your API key is correct")
        print("2. Check your internet connection")
        print("3. Ensure you have enough disk space")
        print("4. Try downloading a smaller subset first")
