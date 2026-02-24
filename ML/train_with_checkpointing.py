"""
Advanced Training Script with Auto-Resume & Real-Time Progress
Supports checkpointing for power loss/internet disconnection recovery
Author: AI Invigilator System
"""

import os
import yaml
import torch
from ultralytics import YOLO
from pathlib import Path
import time
from datetime import datetime, timedelta
import json
from tqdm import tqdm
import sys


class ProgressCallback:
    """Callback to display training progress with percentage and time estimates"""
    
    def __init__(self, total_epochs, start_epoch=0):
        self.total_epochs = total_epochs
        self.start_epoch = start_epoch
        self.start_time = None
        self.epoch_times = []
        self.current_epoch = start_epoch
        self.last_epoch_time = None
        
    def on_train_start(self):
        """Called when training starts"""
        self.start_time = time.time()
        print(f"\n{'='*80}")
        print(f"🚀 Training Progress Tracker Initialized")
        print(f"📊 Total Epochs: {self.total_epochs} (Starting from: {self.start_epoch})")
        print(f"{'='*80}\n")
        
    def on_train_epoch_start(self, epoch):
        """Called at the start of each epoch"""
        self.current_epoch = epoch
        self.epoch_start_time = time.time()
        
    def on_train_epoch_end(self, epoch):
        """Called at the end of each epoch"""
        if not hasattr(self, 'epoch_start_time'):
            # First epoch - estimate from total elapsed time
            if self.start_time and len(self.epoch_times) == 0:
                epoch_time = (time.time() - self.start_time) / (epoch + 1 - self.start_epoch)
            else:
                return
        else:
            epoch_time = time.time() - self.epoch_start_time
            
        self.epoch_times.append(epoch_time)
        
        # Calculate statistics
        completed = epoch + 1
        percentage = (completed / self.total_epochs) * 100
        
        # Estimate remaining time
        if len(self.epoch_times) > 0:
            # Use recent epochs for better estimate (last 10 epochs)
            recent_times = self.epoch_times[-10:] if len(self.epoch_times) > 10 else self.epoch_times
            avg_epoch_time = sum(recent_times) / len(recent_times)
            remaining_epochs = self.total_epochs - completed
            estimated_remaining = remaining_epochs * avg_epoch_time
            
            # Format times
            elapsed = timedelta(seconds=int(time.time() - self.start_time))
            remaining = timedelta(seconds=int(estimated_remaining))
            eta = datetime.now() + timedelta(seconds=int(estimated_remaining))
            
            # Display progress summary
            print(f"\n{'─'*80}")
            print(f"📊 Progress: {completed}/{self.total_epochs} epochs ({percentage:.1f}% complete)")
            print(f"⏱️  This Epoch: {timedelta(seconds=int(epoch_time))} | Avg: {timedelta(seconds=int(avg_epoch_time))}")
            print(f"⏱️  Elapsed: {elapsed} | Remaining: ~{remaining}")
            print(f"🎯 ETA: {eta.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'─'*80}\n")


class TrainingManager:
    """Manages training with checkpointing and progress tracking"""
    
    def __init__(self, config_path='training_config.yaml'):
        self.config_path = config_path
        self.checkpoint_dir = Path('checkpoints')
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.state_file = self.checkpoint_dir / 'training_state.json'
        self.config = self.load_config()
        
    def load_config(self):
        """Load or create training configuration"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Default configuration
            config = {
                'model': 'yolo11n.pt',  # Starting model
                'data': 'e:/witcher/AIINVIGILATOR/Dataset/custom_filtered_dataset/data.yaml',
                'epochs': 100,
                'imgsz': 640,
                'batch': 16,  # Optimal for RTX 3050 6GB
                'patience': 20,  # Early stopping
                'device': 0,  # GPU
                'project': 'runs/train',
                'name': 'malpractice_detector',
                'save_period': 5,  # Save checkpoint every 5 epochs
                'plots': True,
                'verbose': True
            }
            self.save_config(config)
            return config
    
    def save_config(self, config):
        """Save configuration to file"""
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    def load_training_state(self):
        """Load previous training state if exists"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return None
    
    def save_training_state(self, state):
        """Save current training state"""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def clear_training_state(self):
        """Clear training state after completion"""
        if self.state_file.exists():
            self.state_file.unlink()
    
    def find_latest_checkpoint(self, project_dir):
        """Find the latest checkpoint in the project directory"""
        project_path = Path(project_dir)
        if not project_path.exists():
            return None
        
        # Look for last.pt (auto-saved by YOLO)
        last_checkpoint = project_path / 'weights' / 'last.pt'
        if last_checkpoint.exists():
            return str(last_checkpoint)
        
        # Look for numbered checkpoints
        checkpoints = list(project_path.glob('weights/epoch*.pt'))
        if checkpoints:
            # Sort by epoch number
            checkpoints.sort(key=lambda x: int(x.stem.replace('epoch', '')))
            return str(checkpoints[-1])
        
        return None
    
    def estimate_time_remaining(self, epoch, total_epochs, epoch_times):
        """Estimate time remaining based on epoch times"""
        if not epoch_times:
            return "Calculating..."
        
        avg_epoch_time = sum(epoch_times) / len(epoch_times)
        remaining_epochs = total_epochs - epoch
        estimated_seconds = avg_epoch_time * remaining_epochs
        
        return str(timedelta(seconds=int(estimated_seconds)))
    
    def print_header(self):
        """Print training header"""
        print("\n" + "="*80)
        print("🚀 AI INVIGILATOR - ADVANCED TRAINING WITH AUTO-RESUME")
        print("="*80)
        print(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💻 Device: {'GPU (CUDA)' if torch.cuda.is_available() else 'CPU'}")
        if torch.cuda.is_available():
            print(f"🎮 GPU: {torch.cuda.get_device_name(0)}")
            print(f"💾 VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        print("="*80 + "\n")
    
    def print_config(self):
        """Print training configuration"""
        print("⚙️  TRAINING CONFIGURATION")
        print("─"*80)
        print(f"  Model:          {self.config['model']}")
        print(f"  Dataset:        {Path(self.config['data']).name}")
        print(f"  Epochs:         {self.config['epochs']}")
        print(f"  Image Size:     {self.config['imgsz']}")
        print(f"  Batch Size:     {self.config['batch']}")
        print(f"  Patience:       {self.config['patience']} (early stopping)")
        print(f"  Save Period:    Every {self.config['save_period']} epochs")
        print("─"*80 + "\n")
    
    def train(self, resume=True):
        """Start or resume training"""
        self.print_header()
        
        # Check for GPU
        if not torch.cuda.is_available():
            print("⚠️  WARNING: GPU not available! Training will be VERY slow on CPU")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                return
        
        # Check for existing training state
        state = self.load_training_state() if resume else None

        # Fallback: if state file is missing, try discovering last checkpoint directly
        if resume and not state:
            discovered_checkpoint = self.find_latest_checkpoint(
                Path(self.config['project']) / self.config['name']
            )
            if discovered_checkpoint:
                recovered_epochs = 0
                try:
                    checkpoint = torch.load(discovered_checkpoint, map_location='cpu')
                    if isinstance(checkpoint, dict) and 'epoch' in checkpoint:
                        recovered_epochs = int(checkpoint['epoch']) + 1
                except Exception:
                    recovered_epochs = 0

                state = {
                    'session_id': f"recovered_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'started_at': datetime.now().isoformat(),
                    'completed_epochs': recovered_epochs,
                    'last_checkpoint': discovered_checkpoint,
                    'interrupted_at': datetime.now().isoformat(),
                    'epoch_times': []
                }

        if state:
            print("🔄 RESUMING PREVIOUS TRAINING")
            print("─"*80)
            print(f"  Previous Session: {state['session_id']}")
            print(f"  Completed Epochs: {state['completed_epochs']}/{self.config['epochs']}")
            print(f"  Last Checkpoint:  {state['last_checkpoint']}")
            print(f"  Interrupted At:   {state['interrupted_at']}")
            print("─"*80 + "\n")
            
            resume_path = state['last_checkpoint']
            model = YOLO(resume_path)
            start_epoch = state['completed_epochs']
            
        else:
            print("🆕 STARTING NEW TRAINING SESSION")
            print("─"*80)
            self.print_config()
            
            model = YOLO(self.config['model'])
            start_epoch = 0
            
            # Create new session
            session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            state = {
                'session_id': session_id,
                'started_at': datetime.now().isoformat(),
                'completed_epochs': 0,
                'last_checkpoint': None,
                'epoch_times': []
            }
        
        # Training arguments
        train_args = {
            'data': self.config['data'],
            'epochs': self.config['epochs'],
            'imgsz': self.config['imgsz'],
            'batch': self.config['batch'],
            'patience': self.config['patience'],
            'device': self.config['device'],
            'project': self.config['project'],
            'name': self.config['name'],
            'exist_ok': True,  # Allow resuming in same directory
            'plots': self.config['plots'],
            'verbose': self.config['verbose'],
            'save': True,
            'save_period': self.config['save_period']
        }
        
        # Add workers if specified in config (important for Windows compatibility)
        if 'workers' in self.config:
            train_args['workers'] = self.config['workers']
        
        # Add performance optimization parameters
        if 'amp' in self.config:
            train_args['amp'] = self.config['amp']
        if 'cache' in self.config:
            train_args['cache'] = self.config['cache']
        if 'close_mosaic' in self.config:
            train_args['close_mosaic'] = self.config['close_mosaic']
        if 'val' in self.config:
            train_args['val'] = self.config['val']
        
        # If resuming, we need to adjust epochs
        if start_epoch > 0:
            train_args['epochs'] = self.config['epochs']
            train_args['resume'] = True
        
        # Initialize progress callback
        progress_cb = ProgressCallback(self.config['epochs'], start_epoch)
        progress_cb.on_train_start()
        
        # Add callbacks to model
        def epoch_end_callback(trainer):
            """Callback called at the end of each epoch"""
            progress_cb.on_train_epoch_end(trainer.epoch)
        
        # Register callback with YOLO
        from ultralytics.utils import callbacks
        callbacks.add_integration_callbacks = lambda x: None  # Disable unwanted callbacks
        
        model.add_callback("on_train_epoch_end", epoch_end_callback)
        
        try:
            print("🎯 TRAINING STARTED")
            print("="*80)
            print("💡 Press Ctrl+C to safely stop training (checkpoint will be saved)")
            print("="*80 + "\n")
            
            # Start training
            results = model.train(**train_args)
            
            # Training completed successfully
            print("\n" + "="*80)
            print("✅ TRAINING COMPLETED SUCCESSFULLY!")
            print("="*80)
            print(f"📁 Results saved to: {results.save_dir}")
            print(f"⏱️  Total Time: {datetime.now() - datetime.fromisoformat(state['started_at'])}")
            print("="*80 + "\n")
            
            # Clear state
            self.clear_training_state()
            
            # Print summary
            self.print_training_summary(results.save_dir)
            
        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("⚠️  TRAINING INTERRUPTED BY USER")
            print("="*80)
            
            # Save state for resuming
            checkpoint_path = self.find_latest_checkpoint(
                Path(self.config['project']) / self.config['name']
            )
            
            if checkpoint_path:
                state['last_checkpoint'] = checkpoint_path
                state['interrupted_at'] = datetime.now().isoformat()
                # Try to extract epoch from checkpoint
                try:
                    checkpoint = torch.load(checkpoint_path)
                    if 'epoch' in checkpoint:
                        state['completed_epochs'] = checkpoint['epoch'] + 1
                except:
                    pass
                
                self.save_training_state(state)
                
                print(f"💾 Checkpoint saved: {checkpoint_path}")
                print(f"📊 Completed epochs: {state['completed_epochs']}/{self.config['epochs']}")
                print("\n💡 To resume training, run this script again!")
                print("   The training will automatically continue from where it stopped.")
                print("="*80 + "\n")
            else:
                print("⚠️  No checkpoint found to resume from")
                
        except Exception as e:
            print(f"\n❌ ERROR during training: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Try to save state
            checkpoint_path = self.find_latest_checkpoint(
                Path(self.config['project']) / self.config['name']
            )
            if checkpoint_path:
                state['last_checkpoint'] = checkpoint_path
                state['interrupted_at'] = datetime.now().isoformat()
                self.save_training_state(state)
                print(f"\n💾 State saved. You can try resuming by running the script again.")
    
    def print_training_summary(self, results_dir):
        """Print training summary"""
        results_path = Path(results_dir)
        
        print("📊 TRAINING SUMMARY")
        print("─"*80)
        
        # Check for results files
        if (results_path / 'results.csv').exists():
            import pandas as pd
            df = pd.read_csv(results_path / 'results.csv')
            df.columns = df.columns.str.strip()
            
            print(f"  Total Epochs:     {len(df)}")
            
            if 'metrics/mAP50-95(B)' in df.columns:
                best_map = df['metrics/mAP50-95(B)'].max()
                print(f"  Best mAP50-95:    {best_map:.4f}")
            
            if 'metrics/mAP50(B)' in df.columns:
                best_map50 = df['metrics/mAP50(B)'].max()
                print(f"  Best mAP50:       {best_map50:.4f}")
        
        print(f"\n📁 Saved Weights:")
        if (results_path / 'weights' / 'best.pt').exists():
            print(f"  ✅ Best:  {results_path / 'weights' / 'best.pt'}")
        if (results_path / 'weights' / 'last.pt').exists():
            print(f"  ✅ Last:  {results_path / 'weights' / 'last.pt'}")
        
        print("─"*80 + "\n")


def main():
    """Main entry point"""
    print("\n" + "🔷"*40)
    print("AI INVIGILATOR - TRAINING MANAGER")
    print("🔷"*40 + "\n")
    
    # Initialize training manager
    manager = TrainingManager()
    
    # Check if there's a previous session
    state = manager.load_training_state()
    
    if state:
        print("📋 Found previous training session")
        print(f"   Session ID: {state['session_id']}")
        print(f"   Started at: {state['started_at']}")
        print(f"   Progress: {state['completed_epochs']}/{manager.config['epochs']} epochs\n")
        
        response = input("Do you want to resume training? (y/n): ")
        resume = response.lower() == 'y'
        
        if not resume:
            response = input("Start new training (this will archive old state)? (y/n): ")
            if response.lower() == 'y':
                # Archive old state
                archive_name = f"training_state_{state['session_id']}.json.bak"
                manager.state_file.rename(manager.checkpoint_dir / archive_name)
                print(f"✅ Old state archived as: {archive_name}\n")
            else:
                print("Exiting...")
                return
    else:
        resume = False
    
    # Start training
    manager.train(resume=resume)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
