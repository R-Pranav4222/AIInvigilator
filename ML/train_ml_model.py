"""
Quick Start: Train ML Model for Exam Malpractice Detection

This script provides multiple options:
1. Use pre-trained model from Roboflow
2. Fine-tune on downloaded dataset
3. Train from scratch

Choose the option that best fits your needs!
"""

from ultralytics import YOLO
import torch
import os
from pathlib import Path

class MLTrainer:
    """Train or load ML models for exam malpractice detection"""
    
    def __init__(self, 
                 project_name="exam_malpractice_detection",
                 model_save_path="models/trained_models"):
        """
        Initialize trainer
        
        Args:
            project_name: Name for this training project
            model_save_path: Where to save trained models
        """
        self.project_name = project_name
        self.model_save_path = Path(model_save_path)
        self.model_save_path.mkdir(parents=True, exist_ok=True)
        
        # Check GPU availability
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🖥️  Using device: {self.device}")
        
        if self.device == 'cuda':
            print(f"   GPU: {torch.cuda.get_device_name(0)}")
            print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    
    def option_1_use_pretrained_roboflow(self):
        """
        Option 1: Use pre-trained model from Roboflow
        
        Fastest option - just download and use!
        """
        print("\n" + "="*70)
        print("OPTION 1: USE PRE-TRAINED MODEL FROM ROBOFLOW")
        print("="*70)
        
        print("\n📋 Steps:")
        print("1. Go to: https://universe.roboflow.com/research-xfm0x/major-aast-dataset-3d")
        print("2. Click 'Download' → Select 'YOLOv8' format")
        print("3. Choose 'Model' tab instead of 'Dataset'")
        print("4. Download the pre-trained .pt file")
        print("5. Place it in: models/trained_models/yolov8_exam.pt")
        
        print("\n💡 Advantages:")
        print("   - Instant setup (no training needed)")
        print("   - Already trained on 213k images")
        print("   - 20 classes of exam behaviors")
        print("   - Ready to use immediately")
        
        print("\n⚠️  Limitations:")
        print("   - May not be optimized for your specific setup")
        print("   - Can't customize classes")
        
        print("\n✅ Best for: Quick testing and proof of concept")
        print("="*70)
    
    def option_2_finetune_on_dataset(self, 
                                      dataset_path="datasets/major-aast/data.yaml",
                                      base_model="yolov8n.pt",
                                      epochs=50,
                                      imgsz=640,
                                      batch=16):
        """
        Option 2: Fine-tune YOLOv8 on downloaded dataset
        
        Args:
            dataset_path: Path to data.yaml from downloaded dataset
            base_model: Base YOLO model to start from
            epochs: Number of training epochs
            imgsz: Image size for training
            batch: Batch size (reduce if GPU OOM)
        
        Best option for accuracy!
        """
        print("\n" + "="*70)
        print("OPTION 2: FINE-TUNE ON DOWNLOADED DATASET")
        print("="*70)
        
        # Check if dataset exists
        if not os.path.exists(dataset_path):
            print(f"\n❌ Dataset not found at: {dataset_path}")
            print("\n📋 Please download dataset first:")
            print("   python download_roboflow_dataset.py")
            return None
        
        print(f"\n📊 Training configuration:")
        print(f"   Base model: {base_model}")
        print(f"   Dataset: {dataset_path}")
        print(f"   Epochs: {epochs}")
        print(f"   Image size: {imgsz}")
        print(f"   Batch size: {batch}")
        print(f"   Device: {self.device}")
        
        # Load base model
        print(f"\n📥 Loading base model...")
        model = YOLO(base_model)
        
        # Start training
        print(f"\n🚀 Starting training...")
        print("   This may take several hours depending on dataset size and GPU")
        
        results = model.train(
            data=dataset_path,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device=self.device,
            project=str(self.model_save_path),
            name=self.project_name,
            
            # Performance optimizations
            cache=True,  # Cache images for faster training
            amp=True,    # Automatic Mixed Precision
            
            # Augmentation (helps with overfitting)
            hsv_h=0.015,
            hsv_s=0.7,
            hsv_v=0.4,
            degrees=10.0,
            translate=0.1,
            scale=0.5,
            shear=0.0,
            perspective=0.0,
            flipud=0.0,
            fliplr=0.5,
            mosaic=1.0,
            
            # Early stopping
            patience=10,  # Stop if no improvement for 10 epochs
            
            # Save best model
            save=True,
            save_period=10  # Save checkpoint every 10 epochs
        )
        
        # Save best model
        best_model_path = self.model_save_path / self.project_name / "weights" / "best.pt"
        final_path = self.model_save_path / "yolov8_exam.pt"
        
        if best_model_path.exists():
            # Copy best model to standard location
            import shutil
            shutil.copy(best_model_path, final_path)
            print(f"\n✅ Training complete!")
            print(f"   Best model saved to: {final_path}")
            print(f"   Training results: {self.model_save_path / self.project_name}")
        
        return model
    
    def option_3_train_from_scratch(self, 
                                     dataset_path="datasets/major-aast/data.yaml",
                                     model_size="n",  # n, s, m, l, x
                                     epochs=100):
        """
        Option 3: Train from scratch
        
        Only use if you have custom data very different from COCO
        """
        print("\n" + "="*70)
        print("OPTION 3: TRAIN FROM SCRATCH")
        print("="*70)
        
        print("\n⚠️  WARNING: Training from scratch requires:")
        print("   - Large dataset (100k+ images)")
        print("   - Long training time (days/weeks)")
        print("   - High GPU memory")
        
        response = input("\nAre you sure you want to train from scratch? (y/n): ")
        
        if response.lower() != 'y':
            print("Cancelled. Consider Option 2 (fine-tuning) instead!")
            return None
        
        # Use YOLOv8 architecture without pre-trained weights
        model = YOLO(f"yolov8{model_size}.yaml")  # .yaml = architecture only
        
        # Train
        results = model.train(
            data=dataset_path,
            epochs=epochs,
            device=self.device,
            project=str(self.model_save_path),
            name=f"{self.project_name}_scratch",
            cache=True,
            amp=True,
            patience=20
        )
        
        return model
    
    def evaluate_model(self, model_path="models/trained_models/yolov8_exam.pt",
                       test_data="datasets/major-aast/data.yaml"):
        """
        Evaluate trained model on test set
        
        Args:
            model_path: Path to trained model
            test_data: Path to test dataset
        """
        print("\n" + "="*70)
        print("MODEL EVALUATION")
        print("="*70)
        
        if not os.path.exists(model_path):
            print(f"❌ Model not found: {model_path}")
            return
        
        # Load model
        model = YOLO(model_path)
        
        # Run validation
        print("\n📊 Running validation on test set...")
        results = model.val(
            data=test_data,
            device=self.device,
            plots=True  # Generate confusion matrix, etc.
        )
        
        # Print results
        print("\n✅ Evaluation Results:")
        print(f"   mAP50: {results.box.map50:.3f}")
        print(f"   mAP50-95: {results.box.map:.3f}")
        print(f"   Precision: {results.box.mp:.3f}")
        print(f"   Recall: {results.box.mr:.3f}")
        
        return results
    
    def quick_test(self, model_path="models/trained_models/yolov8_exam.pt",
                   test_image="test_images/sample.jpg"):
        """
        Quick test on single image
        
        Args:
            model_path: Path to trained model
            test_image: Path to test image
        """
        print("\n" + "="*70)
        print("QUICK TEST")
        print("="*70)
        
        if not os.path.exists(model_path):
            print(f"❌ Model not found: {model_path}")
            return
        
        # Load model
        model = YOLO(model_path)
        
        # Run inference
        print(f"\n🔍 Testing on: {test_image}")
        results = model.predict(
            source=test_image,
            device=self.device,
            save=True,  # Save annotated image
            conf=0.5    # Confidence threshold
        )
        
        # Print detections
        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            print(f"\n✅ Found {len(boxes)} detections:")
            for i, box in enumerate(boxes):
                cls = int(box.cls)
                conf = float(box.conf)
                print(f"   {i+1}. Class {cls}, Confidence: {conf:.2f}")
        else:
            print("\n❌ No detections found")
        
        print(f"\nResults saved to: runs/detect/predict/")


def main():
    """Main function with interactive menu"""
    print("\n" + "="*70)
    print("ML MODEL TRAINING - QUICK START")
    print("="*70)
    
    # Initialize trainer
    trainer = MLTrainer()
    
    print("\n📋 Choose an option:")
    print("1. Use pre-trained model from Roboflow (fastest)")
    print("2. Fine-tune on downloaded dataset (recommended)")
    print("3. Train from scratch (advanced)")
    print("4. Evaluate existing model")
    print("5. Quick test on image")
    print("6. Exit")
    
    choice = input("\nEnter your choice (1-6): ")
    
    if choice == '1':
        trainer.option_1_use_pretrained_roboflow()
    
    elif choice == '2':
        print("\n⚙️  Training Configuration:")
        epochs = int(input("Number of epochs (50): ") or "50")
        batch = int(input("Batch size (16): ") or "16")
        
        trainer.option_2_finetune_on_dataset(
            epochs=epochs,
            batch=batch
        )
    
    elif choice == '3':
        trainer.option_3_train_from_scratch()
    
    elif choice == '4':
        model_path = input("Model path (models/trained_models/yolov8_exam.pt): ") or "models/trained_models/yolov8_exam.pt"
        trainer.evaluate_model(model_path)
    
    elif choice == '5':
        model_path = input("Model path (models/trained_models/yolov8_exam.pt): ") or "models/trained_models/yolov8_exam.pt"
        test_image = input("Test image path: ")
        if test_image:
            trainer.quick_test(model_path, test_image)
    
    elif choice == '6':
        print("\n👋 Goodbye!")
    
    else:
        print("\n❌ Invalid choice!")


if __name__ == "__main__":
    main()
