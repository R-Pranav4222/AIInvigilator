"""
Smart Training Script with Automatic Early Stopping
Stops when model reaches peak accuracy (no improvement for N epochs)
Minimum 6 epochs guaranteed before early stopping
"""

import os
import yaml
import torch
from ultralytics import YOLO
from pathlib import Path
import time
from datetime import datetime, timedelta
import json
import sys


class SmartTrainingManager:
    """Manages training with intelligent early stopping"""
    
    def __init__(self, config_path='training_config.yaml'):
        self.config_path = config_path
        self.config = self.load_config()
        self.best_map50 = 0.0
        self.epochs_no_improve = 0
        self.min_epochs = 6  # Minimum epochs before early stopping
        self.patience = 5  # Stop if no improvement for 5 epochs after min_epochs
        self.improvement_threshold = 0.005  # 0.5% improvement considered significant
        
    def load_config(self):
        """Load training configuration"""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def train(self):
        """Start training with smart early stopping"""
        
        print("\n" + "="*80)
        print("🎯 SMART TRAINING - AUTO-STOP AT PEAK ACCURACY")
        print("="*80)
        print(f"📊 Configuration:")
        print(f"   • Minimum Epochs: {self.min_epochs}")
        print(f"   • Patience: {self.patience} epochs without improvement")
        print(f"   • Improvement Threshold: {self.improvement_threshold*100}%")
        print(f"   • Max Epochs: {self.config['epochs']}")
        print("="*80 + "\n")
        
        # Initialize model
        model = YOLO(self.config['model'])
        
        # Training arguments
        train_args = {
            'data': self.config['data'],
            'epochs': self.config['epochs'],
            'imgsz': self.config['imgsz'],
            'batch': self.config['batch'],
            'patience': 0,  # Disable YOLO's built-in early stopping - we'll handle it
            'device': self.config['device'],
            'project': self.config['project'],
            'name': self.config['name'],
            'exist_ok': True,
            'plots': self.config['plots'],
            'verbose': self.config['verbose'],
            'save': True,
            'save_period': self.config['save_period']
        }
        
        # Add optional parameters
        if 'workers' in self.config:
            train_args['workers'] = self.config['workers']
        if 'amp' in self.config:
            train_args['amp'] = self.config['amp']
        if 'close_mosaic' in self.config:
            train_args['close_mosaic'] = self.config['close_mosaic']
        if 'val' in self.config:
            train_args['val'] = self.config['val']
        
        # Add custom callback for early stopping
        stop_training = False
        current_epoch = [0]  # Use list for mutability in callback
        start_time = time.time()
        
        def on_fit_epoch_end(trainer):
            """Check if training should stop"""
            nonlocal stop_training
            
            current_epoch[0] = trainer.epoch + 1
            
            # Get current mAP50
            metrics = trainer.validator.metrics
            if hasattr(metrics, 'box') and hasattr(metrics.box, 'map50'):
                current_map50 = metrics.box.map50
            else:
                current_map50 = 0.0
            
            # Calculate progress
            elapsed = time.time() - start_time
            elapsed_td = timedelta(seconds=int(elapsed))
            
            # Update best score
            improvement = current_map50 - self.best_map50
            
            if improvement > self.improvement_threshold:
                self.best_map50 = current_map50
                self.epochs_no_improve = 0
                status = "✅ NEW BEST!"
            else:
                self.epochs_no_improve += 1
                status = f"⏸️  No improvement ({self.epochs_no_improve}/{self.patience})"
            
            # Display progress
            print(f"\n{'─'*80}")
            print(f"📊 Epoch {current_epoch[0]}/{self.config['epochs']} Summary")
            print(f"   • mAP50: {current_map50:.3f} (Best: {self.best_map50:.3f})")
            print(f"   • Improvement: {improvement:+.4f}")
            print(f"   • Status: {status}")
            print(f"   • Elapsed: {elapsed_td}")
            
            # Check early stopping conditions
            if current_epoch[0] >= self.min_epochs:
                if self.epochs_no_improve >= self.patience:
                    print(f"\n{'='*80}")
                    print(f"🎯 EARLY STOPPING TRIGGERED")
                    print(f"   • No improvement for {self.patience} consecutive epochs")
                    print(f"   • Best mAP50: {self.best_map50:.3f} (Epoch {current_epoch[0] - self.patience})")
                    print(f"   • Total training time: {elapsed_td}")
                    print(f"{'='*80}\n")
                    stop_training = True
                    trainer.stop = True  # Signal YOLO to stop
            else:
                remaining_min = self.min_epochs - current_epoch[0]
                print(f"   • Minimum epochs not reached yet ({remaining_min} more required)")
            
            print(f"{'─'*80}\n")
        
        # Register callback
        model.add_callback("on_fit_epoch_end", on_fit_epoch_end)
        
        try:
            print("🚀 TRAINING STARTED")
            print("="*80)
            print("💡 Press Ctrl+C to safely stop training")
            print("="*80 + "\n")
            
            # Start training
            results = model.train(**train_args)
            
            # Training completed
            total_time = timedelta(seconds=int(time.time() - start_time))
            
            print("\n" + "="*80)
            if stop_training:
                print("✅ TRAINING STOPPED - PEAK ACCURACY REACHED")
            else:
                print("✅ TRAINING COMPLETED - MAX EPOCHS REACHED")
            print("="*80)
            print(f"📁 Results: {results.save_dir}")
            print(f"🎯 Best mAP50: {self.best_map50:.3f}")
            print(f"📊 Total Epochs: {current_epoch[0]}")
            print(f"⏱️  Total Time: {total_time}")
            print("="*80 + "\n")
            
            print("📂 Model files:")
            print(f"   • Best model: runs/train/malpractice_detector/weights/best.pt")
            print(f"   • Last model: runs/train/malpractice_detector/weights/last.pt")
            print("\n✅ Training complete! Use best.pt for inference.\n")
            
        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("⚠️  TRAINING INTERRUPTED BY USER")
            print("="*80)
            print(f"📊 Completed {current_epoch[0]} epochs")
            print(f"🎯 Best mAP50: {self.best_map50:.3f}")
            print(f"\n💡 Checkpoint saved. Model available at:")
            print(f"   runs/train/malpractice_detector/weights/last.pt")
            print("="*80 + "\n")
            
        except Exception as e:
            print(f"\n\n❌ ERROR during training: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    manager = SmartTrainingManager()
    manager.train()
