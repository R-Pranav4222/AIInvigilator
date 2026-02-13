# model_config.py
"""
Model Configuration for AI Invigilator
=======================================
Switch between pre-trained and custom models easily.
Your pre-trained models are safely backed up in models/pretrained/
"""

import os

# ============================================
# MODEL PRESET SELECTION
# ============================================
# Options:
#   "pretrained" - Use pre-trained YOLO models (stable, working)
#   "custom"     - Use custom trained malpractice detection model
#
# Change this to switch between models:
ACTIVE_MODEL_PRESET = "pretrained"


# ============================================
# MODEL PATHS (Auto-configured based on preset)
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# Pre-trained model paths (BACKED UP - NEVER OVERWRITTEN)
PRETRAINED_MODELS = {
    "object_detection": os.path.join(MODELS_DIR, "pretrained", "yolo11n.pt"),
    "pose_detection": os.path.join(MODELS_DIR, "pretrained", "yolov8n-pose.pt"),
    "description": "Pre-trained YOLO models for general detection",
    "mobile_class_id": 67,  # COCO class ID for 'cell phone'
}

# Custom trained model paths (trained on malpractice dataset)
CUSTOM_MODELS = {
    "object_detection": os.path.join(MODELS_DIR, "custom", "malpractice_detector.pt"),
    "pose_detection": os.path.join(MODELS_DIR, "pretrained", "yolov8n-pose.pt"),  # Keep pose model
    "description": "Custom trained malpractice detection model",
    "mobile_class_id": 0,  # Custom dataset class ID for 'phone'
}

# ============================================
# GET ACTIVE MODEL PATHS
# ============================================
def get_model_paths():
    """
    Returns the active model paths based on ACTIVE_MODEL_PRESET.
    
    Returns:
        dict: {
            "object_detection": str,  # Path to object detection model
            "pose_detection": str,    # Path to pose detection model
            "preset": str,            # Active preset name
            "description": str        # Description of the model set
        }
    """
    if ACTIVE_MODEL_PRESET == "custom":
        models = CUSTOM_MODELS.copy()
        # Check if custom model exists, fallback to pretrained if not
        if not os.path.exists(models["object_detection"]):
            print(f"⚠️ Custom model not found at {models['object_detection']}")
            print("   Falling back to pre-trained model...")
            models = PRETRAINED_MODELS.copy()
            models["preset"] = "pretrained (fallback)"
        else:
            models["preset"] = "custom"
    else:
        models = PRETRAINED_MODELS.copy()
        models["preset"] = "pretrained"
    
    return models


def get_object_detection_model():
    """Get the path to the active object detection model."""
    return get_model_paths()["object_detection"]


def get_pose_detection_model():
    """Get the path to the active pose detection model."""
    return get_model_paths()["pose_detection"]


def print_model_status():
    """Print current model configuration status."""
    paths = get_model_paths()
    print("\n" + "="*60)
    print("MODEL CONFIGURATION")
    print("="*60)
    print(f"Active Preset: {paths['preset'].upper()}")
    print(f"Description: {paths['description']}")
    print("-"*60)
    print(f"Object Detection: {os.path.basename(paths['object_detection'])}")
    print(f"  Path: {paths['object_detection']}")
    print(f"  Exists: {'✅' if os.path.exists(paths['object_detection']) else '❌'}")
    print(f"Pose Detection: {os.path.basename(paths['pose_detection'])}")
    print(f"  Path: {paths['pose_detection']}")
    print(f"  Exists: {'✅' if os.path.exists(paths['pose_detection']) else '❌'}")
    print("="*60 + "\n")


# ============================================
# CLASS MAPPING FOR CUSTOM MODEL
# ============================================
# These are the malpractice-relevant classes we'll train on
MALPRACTICE_CLASSES = {
    # Mobile/Phone detection
    "mobile_phone": ["Cellphone", "Mobile", "Phone", "Using Phone", "Using_Mobile", 
                     "phone using", "mobile using", "student_using_phone", "Using_phone",
                     "make_phone_call", "playing_phone", "phone", "mobile"],
    
    # Cheating materials
    "cheat_material": ["Cheat_note", "Cheating-Paper", "cheating-paper", 
                       "Using_cheat_sheets", "chit", "using chits", "student_cheating"],
    
    # Looking/Peeking
    "peeking": ["Looking Over", "Peeping", "back peeking", "front peeking", 
                "side peeking", "looking into neighbors paper", "looking around"],
    
    # Turning back
    "turning_back": ["Turning Back", "student_looking_backward", "turn_head"],
    
    # Hand raising
    "hand_raise": ["Hand raise", "hand-raising", "raising hand", "Hand-Gestures"],
    
    # Passing/Sharing
    "passing": ["Giving Cheats", "Sharing", "passing notes", "give_object_to_person",
                "transmit"],
    
    # Communication
    "talking": ["Talking each other", "Signalling", "talking", "discuss", "discussion"],
    
    # Other suspicious behavior
    "suspicious": ["student_cheating", "restless", "looking around"]
}

# Simplified class names for the custom model (8 classes)
CUSTOM_CLASS_NAMES = [
    "mobile_phone",      # 0
    "cheat_material",    # 1
    "peeking",           # 2
    "turning_back",      # 3
    "hand_raise",        # 4
    "passing",           # 5
    "talking",           # 6
    "suspicious"         # 7
]


if __name__ == "__main__":
    print_model_status()
