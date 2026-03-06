# AIInvigilator — Comprehensive Study Guide
# PERSON 1: Machine Learning & AI Pipeline

---

## TABLE OF CONTENTS

- [Part A — Work Assignment & Overview](#part-a--work-assignment--overview)
- [Part B — Implementation Deep-Dive](#part-b--implementation-deep-dive)
  - [B1. System Architecture — ML Pipeline Overview](#b1-system-architecture--ml-pipeline-overview)
  - [B2. YOLO Models — Selection, Configuration & Loading](#b2-yolo-models--selection-configuration--loading)
  - [B3. GPU Configuration & Optimization](#b3-gpu-configuration--optimization)
  - [B4. Detection Algorithm #1 — Mobile Phone Detection](#b4-detection-algorithm-1--mobile-phone-detection)
  - [B5. Detection Algorithm #2 — Leaning Detection](#b5-detection-algorithm-2--leaning-detection)
  - [B6. Detection Algorithm #3 — Turning Back Detection](#b6-detection-algorithm-3--turning-back-detection)
  - [B7. Detection Algorithm #4 — Hand Raise Detection](#b7-detection-algorithm-4--hand-raise-detection)
  - [B8. Detection Algorithm #5 — Passing Paper Detection](#b8-detection-algorithm-5--passing-paper-detection)
  - [B9. Detection Algorithm #6 — Looking Around / Peeking Sideways](#b9-detection-algorithm-6--looking-around--peeking-sideways)
  - [B10. Detection Algorithm #7 — Suspicious Movement](#b10-detection-algorithm-7--suspicious-movement)
  - [B11. Frame Processing Pipeline — Live Camera (frame_processor.py)](#b11-frame-processing-pipeline--live-camera-frame_processorpy)
  - [B12. Frame Processing Pipeline — Uploaded Video (process_uploaded_video_stream.py)](#b12-frame-processing-pipeline--uploaded-video-process_uploaded_video_streampy)
  - [B13. Video Recording & Evidence Capture](#b13-video-recording--evidence-capture)
  - [B14. Probability Scoring Algorithm](#b14-probability-scoring-algorithm)
  - [B15. Enhanced Hybrid Detector (Voting System)](#b15-enhanced-hybrid-detector-voting-system)
- [Part C — Testing & Results](#part-c--testing--results)
- [Part D — Viva Q&A Bank (60+ Questions)](#part-d--viva-qa-bank-60-questions)

---

# Part A — Work Assignment & Overview

## What Person 1 Owns

You are responsible for the **entire ML/AI detection pipeline** — every algorithm that detects malpractice behaviors, the YOLO model loading and inference, GPU optimization, probability scoring, video evidence recording, and both the live-camera and uploaded-video processing flows.

### Files You Must Know Inside-Out

| File | Lines | Purpose |
|------|-------|---------|
| `ML/frame_processor.py` | 886 | Core live-stream ML processor — runs on every webcam frame |
| `ML/process_uploaded_video_stream.py` | 1716 | Uploaded-video ML processor — threaded pipeline, MJPEG output |
| `ML/gpu_config.py` | 136 | GPU/CUDA setup, FP16 config, cuDNN benchmark |
| `ML/model_config.py` | 154 | Model preset manager (pretrained vs custom) |
| `ML/enhanced_hybrid_detector.py` | 330 | Triple-source voting detector (rule + YOLO + COCO) |
| `ML/mobile_detection.py` | 198 | Standalone mobile phone camera script |
| `ML/hand_raise.py` | 231 | Standalone hand raise camera script |
| `ML/leaning.py` | 232 | Standalone leaning camera script |
| `ML/passing_paper.py` | 260 | Standalone passing paper camera script |

### Key Libraries

| Library | Version | Role |
|---------|---------|------|
| PyTorch | 2.5.1+cu121 | Deep learning framework, CUDA backend |
| Ultralytics | 8.3.0 | YOLO model loading, inference, training |
| OpenCV | 4.10.0 | Frame I/O, drawing, video writing, color conversion |
| NumPy | 1.26.4 | Numerical operations, skeleton math |
| MediaPipe | 0.10.32 | Available but NOT used in production pipeline (legacy) |

### High-Level Summary (Explain This Simply)

> "Our system uses two YOLO neural network models running on a GPU. One model (YOLOv8n-pose) detects human body keypoints — shoulders, eyes, nose, wrists — and from those keypoints we mathematically calculate if someone is leaning, turning back, raising hands, passing papers, or looking around. The second model (YOLOv11n) detects objects and tells us if a mobile phone is present. Every detection gets a probability score from 0-100 computed by a 5-factor weighted formula, and suspicious activity is recorded as video evidence clips."

---

# Part B — Implementation Deep-Dive

---

## B1. System Architecture — ML Pipeline Overview

### Simple Explanation
The ML pipeline takes camera frames (images), runs AI models on them to detect cheating behaviors, draws annotations on the frames, records evidence clips, and sends results to the web interface in real-time.

### Technical Explanation

The pipeline operates in two modes:

**Mode 1: Live Camera (frame_processor.py)**
```
Teacher Webcam → WebSocket binary frame → CameraStreamConsumer
  → FrameProcessor.process_frame()
    → YOLO Pose Model (320px) → 7 keypoint-based detections
    → YOLO Object Model (640px) → mobile phone detection  
    → Annotated frame + detection JSON → WebSocket back to teacher
    → Simultaneously: frame sent to admin grid via AdminGridConsumer
    → If detection active: VideoWriter records clip with pre-roll buffer
```

**Mode 2: Uploaded Video (process_uploaded_video_stream.py)**
```
Video file upload → ffmpeg transcode (if >720p) → OpenCV VideoCapture
  → Background thread: read frames → skip every 3rd → run detections → Queue
  → Main async generator: pull from Queue → yield MJPEG → browser displays
  → Detections saved to database with probability scores
  → Admin gets WebSocket notification when processing completes
```

### Architecture Diagram (Text)
```
┌─────────────┐     Binary JPEG      ┌──────────────────────┐
│  Teacher's   │ ──────────────────► │  CameraStreamConsumer │
│   Webcam     │                      │  (consumers.py)       │
└─────────────┘                      └──────────┬───────────┘
                                                 │
                                     FrameProcessor.process_frame()
                                                 │
                              ┌──────────────────┼──────────────────┐
                              ▼                  ▼                  ▼
                    ┌─────────────────┐ ┌───────────────┐ ┌────────────────┐
                    │  YOLOv8n-pose   │ │   YOLOv11n    │ │  Rule-Based    │
                    │  (Pose Model)   │ │ (Object Det.) │ │  Post-Process  │
                    │  imgsz=320      │ │  imgsz=640    │ │  (thresholds)  │
                    └────────┬────────┘ └───────┬───────┘ └────────┬───────┘
                             │                  │                  │
                             ▼                  ▼                  ▼
                    Keypoints (17pts)    Bounding Boxes      Math Checks
                    per person          class 67=phone       (ratios, distances)
                              │                  │                  │
                              └──────────┬───────┘──────────┬──────┘
                                         ▼                  ▼
                              ┌─────────────────┐  ┌───────────────┐
                              │  Detection       │  │  Video        │
                              │  Aggregation +   │  │  Recording    │
                              │  Counter Thresh. │  │  (pre-roll +  │
                              │                  │  │   grace)      │
                              └────────┬─────────┘  └───────┬───────┘
                                       ▼                    ▼
                              ┌─────────────────┐  ┌───────────────┐
                              │  Annotated       │  │  .avi → .mp4  │
                              │  Frame + JSON    │  │  (H.264)      │
                              │  → WebSocket     │  │  → Database   │
                              └─────────────────┘  └───────────────┘
```

---

## B2. YOLO Models — Selection, Configuration & Loading

### Simple Explanation
We use two pre-trained YOLO (You Only Look Once) neural network models. One finds human body parts (pose), the other finds objects like phones. They're loaded once into GPU memory and reused for every frame to save time.

### Technical Explanation

#### Model Selection Rationale

| Property | YOLOv8n-pose | YOLOv11n |
|----------|-------------|----------|
| Task | Pose estimation (17 keypoints) | Object detection (80 COCO classes) |
| Input Resolution | 320×320 px | 640×640 px |
| Why this model | Nano variant = fast inference; pose gives skeleton keypoints for math-based behavioral analysis | Nano variant for speed; class 67 = "cell phone" in COCO |
| Weight file | `yolov8n-pose.pt` (~6MB) | `yolo11n.pt` (~6MB) |
| Confidence threshold | 0.3 | 0.25 |

**Why Nano (n) variants?** We need real-time inference (15+ FPS) on a mid-range GPU (RTX 3050). The nano models sacrifice some accuracy for speed — acceptable since we use frame-counting thresholds (a detection must persist for N consecutive frames before triggering).

#### Singleton Model Loading Pattern

```python
# ML/frame_processor.py — Global model cache (thread-safe singleton)
_pose_model = None
_mobile_model = None
_models_lock = threading.Lock()

def get_cached_models():
    global _pose_model, _mobile_model
    with _models_lock:
        if _pose_model is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            _pose_model = YOLO('yolov8n-pose.pt')
            _pose_model.to(device)
            if device == 'cuda':
                _pose_model.model.half()  # FP16 for speed
            
            _mobile_model = YOLO('yolo11n.pt')
            _mobile_model.to(device)
            if device == 'cuda':
                _mobile_model.model.half()
        
        return _pose_model, _mobile_model
```

**Why singleton?** Model loading takes ~2-3 seconds and consumes ~200MB GPU memory each. If every WebSocket connection loaded fresh models, we'd crash the GPU. The singleton ensures models are loaded exactly once and shared across all connections.

**Why `threading.Lock()`?** Multiple WebSocket connections may call `get_cached_models()` simultaneously. Without the lock, two threads could both see `_pose_model is None` and double-load, wasting memory.

#### Model Warm-up

```python
def prewarm_models():
    """Call at server startup to eliminate first-frame latency."""
    pose_model, mobile_model = get_cached_models()
    dummy = np.zeros((320, 320, 3), dtype=np.uint8)
    pose_model(dummy, imgsz=320, verbose=False)
    mobile_model(dummy, imgsz=640, verbose=False)
```

First inference on any YOLO model takes 500ms+ due to CUDA kernel compilation. Pre-warming with a dummy frame during server startup eliminates this latency from the first real frame.

#### Model Config System (model_config.py)

```python
MODEL_PRESETS = {
    'pretrained': {
        'detection_model': 'yolo11n.pt',      # COCO 80-class
        'pose_model': 'yolov8n-pose.pt',       # COCO keypoints
        'phone_class_id': 67,                   # COCO class for cell phone
    },
    'custom': {
        'detection_model': 'malpractice_detector.pt',  # Custom trained
        'pose_model': 'yolov8n-pose.pt',
        'phone_class_id': 0,                    # Custom dataset class
    },
}
ACTIVE_PRESET = 'pretrained'  # Toggle between pretrained/custom
```

This abstraction lets us swap between COCO pre-trained models and custom-trained models without changing any detection code. The `phone_class_id` changes because custom datasets may number classes differently.

---

## B3. GPU Configuration & Optimization

### Simple Explanation
We configure the NVIDIA GPU for maximum speed: use half-precision math (FP16) which is twice as fast, enable cuDNN auto-tuning, and set the right CUDA device.

### Technical Explanation

#### gpu_config.py — GPUConfig Class

```python
class GPUConfig:
    def __init__(self):
        self.device = self._setup_device()
        self.fp16 = self._check_fp16()
        self._optimize_cuda()
    
    def _setup_device(self):
        if torch.cuda.is_available():
            device = torch.device('cuda:0')
            torch.cuda.set_device(device)
            return device
        return torch.device('cpu')
    
    def _check_fp16(self):
        if self.device.type == 'cuda':
            capability = torch.cuda.get_device_capability()
            return capability[0] >= 7  # Volta+ supports efficient FP16
        return False
    
    def _optimize_cuda(self):
        if self.device.type == 'cuda':
            torch.backends.cudnn.benchmark = True   # Auto-tune convolutions
            torch.backends.cuda.matmul.allow_tf32 = True  # TF32 on Ampere+
```

#### Key Optimizations Explained

| Optimization | What It Does | Speedup |
|-------------|-------------|---------|
| **FP16 (Half Precision)** | Uses 16-bit floats instead of 32-bit. RTX 3050 has dedicated FP16 Tensor Cores. | ~1.5-2x faster inference |
| **cuDNN Benchmark** | First call tests multiple convolution algorithms, picks fastest for this specific input size. Subsequent calls reuse the winner. | ~10-20% faster after warmup |
| **TF32** | TensorFloat-32 on Ampere GPUs — 19-bit precision at FP16 speed. | ~10% on supported GPUs |
| **CUDA:0** | Explicitly selects first GPU, avoids defaulting to CPU. | Required for GPU use |

#### FP16 Deep Dive

```python
# In model loading:
model.model.half()  # Converts all weights from float32 → float16
```

**Why does this work?** Neural network inference doesn't need full 32-bit precision. The tiny precision loss (< 0.1% accuracy drop) is invisible in our use case since we further filter through frame-count thresholds. But we get:
- **50% less GPU memory** per model (~100MB instead of ~200MB)
- **~2x faster** matrix multiplications on Tensor Cores
- **More headroom** to run both models simultaneously on a 4GB RTX 3050

#### Compute Capability Check

```python
capability = torch.cuda.get_device_capability()  # Returns (major, minor)
# RTX 3050 → (8, 6) — Ampere architecture
# FP16 efficient on >= 7.0 (Volta)
```

Our RTX 3050 is Ampere (8.6), so FP16 and TF32 are both available and efficient.

---

## B4. Detection Algorithm #1 — Mobile Phone Detection

### Simple Explanation
The YOLO object detection model scans each frame for objects. If it finds something classified as "cell phone" (class 67 in the COCO dataset) with at least 25% confidence, and this detection persists for 3+ consecutive frames, we flag it as malpractice.

### Technical Explanation

#### Algorithm Flow

```
Frame → YOLO11n(imgsz=640, conf=0.25) → List of bounding boxes
  → Filter: class_id == 67 (cell phone)
  → Filter: is_likely_phone() smart filter
  → If phone found: increment mobile_counter
  → If mobile_counter >= 3: TRIGGER "Mobile Phone" detection
  → If no phone: reset mobile_counter = 0
```

#### The is_likely_phone() Smart Filter

```python
def is_likely_phone(box, frame_shape):
    """Filter out false positives (calculators, remote controls)."""
    x1, y1, x2, y2 = box[:4]
    w = x2 - x1
    h = y2 - y1
    aspect_ratio = h / w if w > 0 else 0
    area = w * h
    frame_area = frame_shape[0] * frame_shape[1]
    relative_size = area / frame_area
    
    # Phone constraints:
    # - Aspect ratio between 1.2 and 3.0 (portrait orientation)
    # - Not too large (< 15% of frame = not a TV/monitor)
    # - Not too small (> 0.1% of frame = not noise)
    if 1.2 <= aspect_ratio <= 3.0 and 0.001 < relative_size < 0.15:
        return True
    # Also allow landscape phones (wider than tall)
    if 0.3 <= aspect_ratio <= 0.8 and 0.001 < relative_size < 0.15:
        return True
    return False
```

**Why this filter?** COCO class 67 is "cell phone" but YOLO sometimes confuses calculators, remote controls, or even book edges as phones. The aspect ratio filter (portrait: 1.2-3.0, landscape: 0.3-0.8) plus the relative size filter (0.1%-15% of frame) eliminates most false positives. A real phone in an exam hall viewed from a ceiling/desk camera will always fall within these bounds.

#### Frame Counter Mechanism

```python
# In FrameProcessor.__init__():
self.thresholds = {
    'Leaning': 3,
    'Mobile Phone': 3,
    'Turning Back': 3,
    'Passing Paper': 3,
    'Hand Raise': 5,
}
self.counters = {key: 0 for key in self.thresholds}

# In process_frame():
if phone_detected:
    self.counters['Mobile Phone'] += 1
else:
    self.counters['Mobile Phone'] = 0

if self.counters['Mobile Phone'] >= self.thresholds['Mobile Phone']:
    # TRIGGER — been detected for 3 consecutive frames
    self._start_recording('Mobile Phone', confidence)
```

**Why consecutive frames?** A single-frame false positive (YOLO momentarily misclassifying something) would create a bogus alert. Requiring 3 consecutive frames (3/15 = 0.2 seconds at 15 FPS) ensures the phone is genuinely present and not a flicker.

---

## B5. Detection Algorithm #2 — Leaning Detection

### Simple Explanation
If a student leans far to one side (to peek at another student's paper), their nose shifts significantly compared to the midpoint of their shoulders. We measure this offset ratio — if it exceeds 0.4 (40% of shoulder width), they're flagged as leaning.

### Technical Explanation

#### Keypoint Indices Used (COCO Pose Format)
```
Index 0:  Nose
Index 5:  Left Shoulder
Index 6:  Right Shoulder
```

#### Algorithm

```python
def is_leaning(keypoints):
    """Detect sideways leaning using nose-shoulder offset ratio."""
    nose = keypoints[0]        # [x, y, confidence]
    left_sh = keypoints[5]     # Left shoulder
    right_sh = keypoints[6]    # Right shoulder
    
    # Skip if keypoints are low confidence
    if nose[2] < 0.3 or left_sh[2] < 0.3 or right_sh[2] < 0.3:
        return False
    
    shoulder_mid_x = (left_sh[0] + right_sh[0]) / 2
    shoulder_width = abs(left_sh[0] - right_sh[0])
    
    if shoulder_width < 10:  # Shoulders too close = unreliable
        return False
    
    nose_offset = abs(nose[0] - shoulder_mid_x)
    ratio = nose_offset / shoulder_width
    
    return ratio > 0.4  # Threshold: 40% of shoulder width
```

#### Mathematical Visualization
```
Normal posture (ratio ≈ 0.05):        Leaning (ratio > 0.4):
                                       
     👃 (nose)                              👃 (nose far right)
      |                                          \
   ----+----                              ----+----
  LS   Mid   RS                          LS   Mid   RS
  
  offset/width ≈ 0.05                   offset/width ≈ 0.55
  → NOT flagged                          → FLAGGED
```

**Why shoulder_width as denominator?** It normalizes for distance from camera. A student sitting far from the camera has a small pixel shoulder width, so a small pixel offset is proportionally significant. A student close to the camera has large shoulders, so we need a larger absolute offset to flag. The ratio handles both cases.

**Why threshold 0.4?** Empirically tested — normal head movement (looking at your paper) stays below 0.3 ratio. Deliberately leaning to see another student's paper pushes above 0.4. The 3-frame consecutive requirement adds further robustness.

---

## B6. Detection Algorithm #3 — Turning Back Detection

### Simple Explanation
When a student turns their head backward, the camera can no longer see the distance between their eyes clearly — the eyes appear very close together or overlap. We compare eye distance to shoulder distance: if the ratio drops below 0.15, the person has turned away.

### Technical Explanation

#### Keypoint Indices
```
Index 1: Left Eye
Index 2: Right Eye
Index 5: Left Shoulder
Index 6: Right Shoulder
```

#### Algorithm

```python
def is_turning_back(keypoints):
    """Detect if student has turned away from camera."""
    left_eye = keypoints[1]
    right_eye = keypoints[2]
    left_sh = keypoints[5]
    right_sh = keypoints[6]
    
    if any(kp[2] < 0.3 for kp in [left_eye, right_eye, left_sh, right_sh]):
        return False
    
    eye_dist = np.sqrt(
        (left_eye[0] - right_eye[0])**2 + 
        (left_eye[1] - right_eye[1])**2
    )
    shoulder_dist = np.sqrt(
        (left_sh[0] - right_sh[0])**2 + 
        (left_sh[1] - right_sh[1])**2
    )
    
    if shoulder_dist < 10:
        return False
    
    ratio = eye_dist / shoulder_dist
    return ratio < 0.15
```

#### Why This Works — Geometric Reasoning
```
Facing camera (ratio ≈ 0.45):       Turned away (ratio < 0.15):

   LE ──────── RE                      LE/RE (overlapping)
   (eyes far apart)                    (eyes very close)
                                    
   LS ──────── RS                      LS ──────── RS
   (shoulders visible)                 (shoulders still visible)
   
   eye_dist/shoulder_dist ≈ 0.45      eye_dist/shoulder_dist ≈ 0.08
```

When you face forward, your inter-eye distance is roughly 40-50% of your shoulder width. When you turn 90°+, your eyes are nearly co-located from the camera's perspective, but shoulders remain visible from the side. The ratio plummets below 0.15.

**Edge case handling**: Confidence < 0.3 check prevents false positives when keypoints are just poorly detected (e.g., occluded face). shoulder_dist < 10 check prevents division by near-zero.

---

## B7. Detection Algorithm #4 — Hand Raise Detection

### Simple Explanation
If a student's wrist is above their shoulder, their hand is raised (possibly signaling to another student). We check if either wrist's Y coordinate is at least 20 pixels above the corresponding shoulder.

### Technical Explanation

#### Keypoint Indices
```
Index 5: Left Shoulder    Index 6: Right Shoulder
Index 9: Left Wrist       Index 10: Right Wrist
```

#### Algorithm

```python
def is_hand_raised(keypoints):
    """Detect raised hand — possible signaling."""
    left_sh = keypoints[5]
    right_sh = keypoints[6]
    left_wrist = keypoints[9]
    right_wrist = keypoints[10]
    
    # Check left hand
    if left_wrist[2] > 0.3 and left_sh[2] > 0.3:
        if left_wrist[1] < left_sh[1] - 20:  # Y-axis: up = smaller value
            return True
    
    # Check right hand
    if right_wrist[2] > 0.3 and right_sh[2] > 0.3:
        if right_wrist[1] < right_sh[1] - 20:
            return True
    
    return False
```

#### Important Y-Axis Convention
In image coordinates, **Y increases downward**. So "wrist above shoulder" means `wrist_y < shoulder_y`. The 20-pixel buffer (`- 20`) prevents triggering when hands are just at shoulder level (e.g., resting chin on hand).

#### Threshold Choice
```
Threshold = 5 consecutive frames (not 3 like others)
```
Hand raise has a higher threshold because brief hand movements (scratching head, adjusting hair) are normal. Only sustained raised hands (5/15 = 0.33 seconds) are suspicious.

---

## B8. Detection Algorithm #5 — Passing Paper Detection

### Simple Explanation
If two different people's wrists are very close together (within 200 pixels), they might be passing a paper or object between them. We check all pairs of detected people and compute the Euclidean distance between their wrist keypoints.

### Technical Explanation

#### Algorithm

```python
def detect_passing_paper(results):
    """Check if wrists of different people are close → passing objects."""
    if results[0].keypoints is None:
        return False
    
    keypoints_list = results[0].keypoints.data.cpu().numpy()
    num_people = len(keypoints_list)
    
    if num_people < 2:
        return False  # Need at least 2 people
    
    DISTANCE_THRESHOLD = 200  # pixels
    
    for i in range(num_people):
        for j in range(i + 1, num_people):
            person_a = keypoints_list[i]
            person_b = keypoints_list[j]
            
            # Check all 4 wrist pairings:
            # A's left  ↔ B's left,  A's left  ↔ B's right
            # A's right ↔ B's left,  A's right ↔ B's right
            wrist_pairs = [
                (person_a[9], person_b[9]),    # Left-Left
                (person_a[9], person_b[10]),   # Left-Right
                (person_a[10], person_b[9]),   # Right-Left
                (person_a[10], person_b[10]),  # Right-Right
            ]
            
            for wa, wb in wrist_pairs:
                if wa[2] > 0.3 and wb[2] > 0.3:  # Both visible
                    dist = np.sqrt((wa[0]-wb[0])**2 + (wa[1]-wb[1])**2)
                    if dist < DISTANCE_THRESHOLD:
                        return True
    
    return False
```

#### Why 4 Wrist Pairings?
One student might extend their left hand while the other extends their right hand, or both could use right hands. Checking all 4 combinations catches every physical passing orientation.

#### Complexity Analysis
- For N people: we check $\binom{N}{2} \times 4$ distance calculations
- In a typical exam: 1-5 people visible → at most $\binom{5}{2} \times 4 = 40$ distance calculations — negligible cost
- Euclidean distance: $d = \sqrt{(x_a - x_b)^2 + (y_a - y_b)^2}$

#### Why 200 Pixels?
At typical webcam resolution (1280×720) and exam-room camera distance, 200 pixels corresponds to roughly arm's length. Two people's wrists being within arm's length suggests a hand-to-hand transfer.

---

## B9. Detection Algorithm #6 — Looking Around / Peeking Sideways

### Simple Explanation
If a student's nose is offset from the midpoint of their shoulders, but NOT as much as full leaning, they're looking sideways — possibly peeking at another student's paper. The offset ratio between 0.25 and 0.7 (but with different handling) flags this.

### Technical Explanation

These detections exist in the uploaded video processor (`process_uploaded_video_stream.py`):

```python
def is_peeking_sideways(keypoints):
    """Detect sideways glancing without full body lean."""
    nose = keypoints[0]
    left_sh = keypoints[5]
    right_sh = keypoints[6]
    
    if nose[2] < 0.3 or left_sh[2] < 0.3 or right_sh[2] < 0.3:
        return False
    
    shoulder_mid_x = (left_sh[0] + right_sh[0]) / 2
    shoulder_width = abs(left_sh[0] - right_sh[0])
    
    if shoulder_width < 10:
        return False
    
    nose_offset = abs(nose[0] - shoulder_mid_x)
    ratio = nose_offset / shoulder_width
    
    return 0.25 < ratio < 0.7  # Between normal and full lean
```

**Difference from leaning:** Leaning uses threshold > 0.4. Peeking uses the range 0.25-0.7. In the uploaded video processor, both are checked but "Peeking Sideways" is the distinct category name when the offset is in this intermediate range.

---

## B10. Detection Algorithm #7 — Suspicious Movement

### Simple Explanation
If a student's nose position moves around a lot over 10 consecutive frames (high variance), they're displaying restless/suspicious movement — possibly looking at multiple other students' papers rapidly.

### Technical Explanation

```python
# In process_uploaded_video_stream.py:
nose_positions = {}  # Tracks last 10 nose positions per person

def detect_suspicious_behavior(keypoints, person_id=0):
    """Detect rapid head movement by tracking nose position variance."""
    nose = keypoints[0]
    
    if nose[2] < 0.3:
        return False
    
    if person_id not in nose_positions:
        nose_positions[person_id] = []
    
    nose_positions[person_id].append((nose[0], nose[1]))
    
    # Keep only last 10 frames
    if len(nose_positions[person_id]) > 10:
        nose_positions[person_id] = nose_positions[person_id][-10:]
    
    if len(nose_positions[person_id]) < 10:
        return False  # Need 10 frames of data
    
    positions = np.array(nose_positions[person_id])
    variance = np.var(positions[:, 0]) + np.var(positions[:, 1])
    
    return variance > 50  # High movement = suspicious
```

#### The Math
- Collect nose $(x, y)$ for 10 frames
- $\text{Variance} = \text{Var}(x_0..x_9) + \text{Var}(y_0..y_9)$
- If variance > 50: the head is moving rapidly

**Why variance?** A student normally looking at their paper has minimal nose movement (variance < 20). A student rapidly scanning left-right-left (trying to read nearby papers) has high positional variance > 50. Variance captures the "spread" of movement regardless of direction.

---

## B11. Frame Processing Pipeline — Live Camera (frame_processor.py)

### Simple Explanation
When a teacher's webcam is active, every frame goes through our ML pipeline. We resize it, run both YOLO models, check all detection algorithms, draw colored skeleton overlays, update counters, record evidence clips, and send results back — all in under 100ms per frame.

### Technical Explanation

#### FrameProcessor Class — Initialization

```python
class FrameProcessor:
    def __init__(self, teacher_id, hall_name):
        self.teacher_id = teacher_id
        self.hall_name = hall_name
        
        # Detection thresholds (consecutive frames needed)
        self.thresholds = {
            'Leaning': 3,
            'Mobile Phone': 3,
            'Turning Back': 3,
            'Passing Paper': 3,
            'Hand Raise': 5,
        }
        self.counters = {key: 0 for key in self.thresholds}
        self.active_detections = {}  # Currently active detection types
        
        # Frame rate control
        self.INPUT_FPS = 15
        
        # Video recording state (per-action type)
        self.recording_state = {}    # {action: VideoWriter}
        self.recording_start = {}    # {action: timestamp}
        self.recording_frames = {}   # {action: frame_count}
        
        # Pre-roll buffer (captures frames BEFORE detection triggers)
        self.PRE_ROLL_SECONDS = 1.0
        self.frame_buffer = collections.deque(
            maxlen=int(self.INPUT_FPS * self.PRE_ROLL_SECONDS)  # 15 frames
        )
        
        # Grace period (keeps recording after detection ends)
        self.GRACE_FRAMES = 30  # 2 seconds at 15 FPS
        self.grace_counters = {}
```

#### process_frame() — Main Loop (called for every frame)

```python
def process_frame(self, frame_bytes):
    # 1. Decode JPEG bytes to OpenCV image
    nparr = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # 2. Buffer frame for pre-roll recording
    self.buffer_frame(frame)
    
    # 3. Run YOLO Pose model
    pose_results = pose_model(frame, imgsz=320, conf=0.3, verbose=False)
    
    # 4. Run YOLO Object model
    mobile_results = mobile_model(frame, imgsz=640, conf=0.25, verbose=False)
    
    # 5. Extract keypoints
    keypoints_data = pose_results[0].keypoints.data.cpu().numpy()
    
    # 6. Run all detection algorithms
    detections = []
    for person_keypoints in keypoints_data:
        if is_leaning(person_keypoints):
            detections.append('Leaning')
        if is_turning_back(person_keypoints):
            detections.append('Turning Back')
        if is_hand_raised(person_keypoints):
            detections.append('Hand Raise')
    
    if detect_passing_paper(pose_results):
        detections.append('Passing Paper')
    
    # Mobile phone check
    for box in mobile_results[0].boxes:
        if int(box.cls) == 67 and is_likely_phone(box.xyxy[0], frame.shape):
            detections.append('Mobile Phone')
    
    # 7. Update counters & trigger recordings
    for action in self.thresholds:
        if action in detections:
            self.counters[action] += 1
        else:
            self.counters[action] = 0
        
        if self.counters[action] >= self.thresholds[action]:
            self._start_recording(action, confidence)
    
    # 8. Draw skeleton overlay on frame
    annotated = self._draw_skeleton(frame, keypoints_data, detections)
    
    # 9. Draw status overlay (active detections, recording indicator)
    annotated = self._draw_status(annotated)
    
    # 10. Encode back to JPEG
    _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
    
    return buffer.tobytes(), detections_json
```

#### Frame-Dropping Mechanism (in consumers.py)

The WebSocket consumer doesn't queue frames — it uses a "latest frame" pattern:

```python
# In CameraStreamConsumer:
self._latest_frame = None
self._ml_busy = False

async def receive(self, bytes_data=None):
    self._latest_frame = bytes_data  # Always overwrite
    if not self._ml_busy:
        self._ml_busy = True
        frame = self._latest_frame
        result = await self._run_ml(frame)
        self._ml_busy = False
```

**Why drop frames?** ML processing takes ~60-100ms but frames arrive every ~67ms (15 FPS). If we queued them, the queue would grow without bound and latency would increase over time. By always processing the **latest** frame, we maintain real-time responsiveness at the cost of skipping some frames.

---

## B12. Frame Processing Pipeline — Uploaded Video (process_uploaded_video_stream.py)

### Simple Explanation
When a teacher uploads a recorded exam video, we process it frame-by-frame in a background thread and stream the annotated results live to the browser as an MJPEG video stream. The teacher watches the AI analyze the video in real-time.

### Technical Explanation

#### Architecture: Threaded Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                    Main Thread (async)                    │
│  stream_process_video() — async generator                │
│  Pulls frames from Queue, yields MJPEG multipart         │
│  Target: 25 FPS output                                   │
└──────────────────────┬──────────────────────────────────┘
                       │ Queue(maxsize=600)
┌──────────────────────┴──────────────────────────────────┐
│                 Background Thread                        │
│  processing_worker() — reads video, runs ML              │
│  Frame skip = 3 (process every 3rd frame)                │
│  Puts annotated frames + detections into Queue           │
└─────────────────────────────────────────────────────────┘
```

#### Why Threaded?
Django's `StreamingHttpResponse` runs in the main async event loop. ML inference with PyTorch is CPU/GPU-intensive and **blocks** the event loop. Putting ML in a separate thread lets the main thread keep serving MJPEG frames smoothly.

#### Pre-Processing: ffmpeg Transcode

```python
def transcode_for_processing(input_path):
    """Downscale high-resolution videos before processing."""
    cap = cv2.VideoCapture(input_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    
    if width > 720:  # Only transcode if >720p
        output_path = input_path.replace('.', '_transcoded.')
        cmd = [
            'ffmpeg', '-i', input_path,
            '-vf', 'scale=720:-2',  # Scale to 720px width, auto height
            '-c:v', 'libx264', '-preset', 'ultrafast',
            '-y', output_path
        ]
        subprocess.run(cmd, capture_output=True)
        return output_path
    return input_path
```

**Why transcode?** Processing 4K video at YOLO inference resolution is wasteful — YOLO internally resizes to 320/640px anyway. Pre-transcoding to 720p reduces I/O bandwidth and decode time by 4-9x while losing zero detection accuracy.

#### Key Processing Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| FRAME_SKIP | 3 | Process every 3rd frame — 3x faster, minimal accuracy loss since malpractice is sustained action |
| POSE_IMGSZ | 416 | Slightly larger than live (320) since speed pressure is lower |
| MOBILE_IMGSZ | 640 | Same as live |
| STREAM_FPS | 25 | Output MJPEG stream framerate |
| Queue maxsize | 600 | ~24 seconds of buffer at 25 FPS |
| GRACE_PERIOD | 30 | Frames after last detection before stopping recording |

#### Stream Output Format (MJPEG)

```python
async def stream_process_video(session_id, video_path, hall_id):
    """Async generator yielding MJPEG frames."""
    yield b'--frame\r\n'
    
    while not done:
        frame_data = queue.get(timeout=0.04)  # 25 FPS
        yield b'Content-Type: image/jpeg\r\n\r\n'
        yield frame_data
        yield b'\r\n--frame\r\n'
```

The browser displays this by setting an `<img>` tag's `src` to the MJPEG endpoint. The browser natively renders multipart JPEG streams as video.

---

## B13. Video Recording & Evidence Capture

### Simple Explanation
When a malpractice is detected, we automatically start recording a video clip as evidence. The clip includes 1 second BEFORE the detection (pre-roll buffer) and continues until 2 seconds AFTER the detection ends (grace period). This gives reviewers full context.

### Technical Explanation

#### Pre-Roll Buffer

```python
# Circular buffer of recent frames
self.frame_buffer = collections.deque(
    maxlen=int(self.INPUT_FPS * self.PRE_ROLL_SECONDS)  # 15 frames = 1 sec
)

def buffer_frame(self, frame):
    """Called for EVERY frame, before ML processing."""
    self.frame_buffer.append(frame.copy())
```

When a detection triggers, the buffer already contains the last 1 second of video. We write these buffered frames first, then continue recording live frames.

#### Recording Lifecycle

```
Detection starts (counter >= threshold)
  │
  ├── _start_recording(action_type):
  │     1. Create VideoWriter (mp4v codec, .avi)
  │     2. Dump pre-roll buffer frames into writer
  │     3. Set recording_state[action] = writer
  │
  ├── Each subsequent frame while detection active:
  │     writer.write(frame)
  │
  ├── Detection ends (counter reset to 0):
  │     grace_counters[action] = GRACE_FRAMES (30)
  │
  ├── Grace period (30 frames / 2 seconds):
  │     Continue writing frames
  │     grace_counters[action] -= 1
  │
  └── Grace expires (counter hits 0):
        _stop_recording(action):
          1. Release VideoWriter
          2. Convert .avi → .mp4 (H.264)
          3. Calculate probability score
          4. Save to database (MalpraticeDetection model)
```

#### Per-Action Recording

Each detection type records **independently**. If "Leaning" and "Mobile Phone" trigger simultaneously, two separate video clips are created:

```python
self.recording_state = {}    # {'Leaning': VideoWriter, 'Mobile Phone': VideoWriter}
self.recording_start = {}    # {'Leaning': 1709712345.6}
self.recording_frames = {}   # {'Leaning': 47}
```

This ensures each malpractice type has its own clean evidence clip.

#### H.264 Conversion (3-Strategy Fallback)

```python
def convert_to_h264(input_path, output_path):
    """Convert mp4v .avi to H.264 .mp4 for browser playback."""
    # Strategy 1: System ffmpeg
    try:
        subprocess.run(['ffmpeg', '-i', input_path, '-c:v', 'libx264', 
                       '-preset', 'fast', '-y', output_path])
        return True
    except FileNotFoundError:
        pass
    
    # Strategy 2: imageio-ffmpeg (bundled ffmpeg)
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ffmpeg_path, '-i', input_path, '-c:v', 'libx264',
                       '-preset', 'fast', '-y', output_path])
        return True
    except:
        pass
    
    # Strategy 3: OpenCV with H.264 codec
    try:
        # Re-encode using cv2.VideoWriter with 'avc1' fourcc
        ...
        return True
    except:
        pass
    
    return False  # Keep .avi as fallback
```

**Why 3 strategies?** System ffmpeg may not be installed on all machines. imageio-ffmpeg bundles its own ffmpeg binary as a Python package. OpenCV sometimes has H.264 support compiled in. The fallback chain ensures video conversion works on any environment.

**Why H.264?** Browsers cannot play mp4v-encoded .avi files. H.264 in .mp4 container is universally supported by all modern browsers for `<video>` tag playback.

---

## B14. Probability Scoring Algorithm

### Simple Explanation
Each malpractice detection gets a probability score from 0-100 that estimates how likely it is to be real malpractice. Five factors are weighted: how long it lasted (30%), how many frames had detections (25% with 1.5x boost), model confidence (20%), how sustained it was (15%), and the type's base probability (10%).

### Technical Explanation

#### The 5-Factor Formula

```python
def _calc_probability_video(self, action, confidence, duration, 
                            total_frames, detection_frames):
    """Compute 0-100 malpractice probability score."""
    
    # Factor 1: Duration Score (30% weight)
    # Longer = more likely real malpractice
    duration_score = min(duration / 30.0, 1.0) * 100
    # 30 seconds of continuous detection → max score
    
    # Factor 2: Detection Density (25% weight, 1.5x boost)
    # What fraction of frames had this detection
    if total_frames > 0:
        density = detection_frames / total_frames
    else:
        density = 0
    density_score = min(density * 1.5, 1.0) * 100
    # 67%+ detection rate → max score (after 1.5x boost)
    
    # Factor 3: Average Model Confidence (20% weight)
    confidence_score = confidence * 100
    # Direct YOLO/threshold confidence
    
    # Factor 4: Sustainability Score (15% weight)
    # How consistently it was detected (not one-off bursts)
    if total_frames > 0:
        sustainability = detection_frames / total_frames
    else:
        sustainability = 0
    sustainability_score = sustainability * 100
    
    # Factor 5: Type Prior (10% weight)
    # Some actions are inherently more suspicious
    type_priors = {
        'Mobile Phone': 85,
        'Passing Paper': 80,
        'Turning Back': 60,
        'Leaning': 55,
        'Hand Raise': 40,
        'Peeking Sideways': 65,
        'Suspicious Movement': 50,
    }
    type_score = type_priors.get(action, 50)
    
    # Weighted combination
    final = (
        duration_score * 0.30 +
        density_score * 0.25 +
        confidence_score * 0.20 +
        sustainability_score * 0.15 +
        type_score * 0.10
    )
    
    return round(min(max(final, 0), 100), 1)
```

#### Full Mathematical Formula

$$P = \min\left(\max\left(D_s \cdot 0.30 + N_s \cdot 0.25 + C_s \cdot 0.20 + S_s \cdot 0.15 + T_s \cdot 0.10, \; 0\right), \; 100\right)$$

Where:
- $D_s = \min\left(\frac{t}{30}, 1\right) \times 100$ — Duration score ($t$ = seconds)
- $N_s = \min\left(\frac{n}{N} \times 1.5, 1\right) \times 100$ — Density score ($n$ = detection frames, $N$ = total frames)
- $C_s = c \times 100$ — Confidence score ($c$ = avg YOLO confidence)
- $S_s = \frac{n}{N} \times 100$ — Sustainability score
- $T_s$ = Type prior (fixed per action type)

#### Example Calculation

A "Mobile Phone" detected for 15 seconds, in 80 of 225 frames, with 0.72 avg confidence:

| Factor | Calculation | Score |
|--------|------------|-------|
| Duration | min(15/30, 1) × 100 = 50 | 50 |
| Density | min(80/225 × 1.5, 1) × 100 = min(0.533, 1) × 100 = 53.3 | 53.3 |
| Confidence | 0.72 × 100 = 72 | 72 |
| Sustainability | 80/225 × 100 = 35.6 | 35.6 |
| Type Prior (Mobile) | 85 | 85 |

$$P = 50(0.30) + 53.3(0.25) + 72(0.20) + 35.6(0.15) + 85(0.10)$$
$$P = 15 + 13.3 + 14.4 + 5.3 + 8.5 = 56.5$$

Result: **56.5/100 probability**

#### Why These Weights?
- **Duration (30%)**: A brief false positive naturally gets a low score. Sustained cheating gets high.
- **Density (25% with 1.5x boost)**: Even in a long recording, if the detection only appears in 10% of frames, it's likely noise. The 1.5x boost rewards higher density.
- **Confidence (20%)**: YOLO's own confidence matters — a 0.9 confidence detection is more reliable than 0.3.
- **Sustainability (15%)**: Overlaps with density but contributes to overall consistency signal.
- **Type Prior (10%)**: A mobile phone in an exam is almost certainly cheating (85). A hand raise might just be a question (40).

---

## B15. Enhanced Hybrid Detector (Voting System)

### Simple Explanation
Instead of relying on just one detection method, the hybrid detector combines three independent sources — rule-based computer vision, a custom-trained YOLO model, and the standard COCO YOLO model — and uses a voting system. A detection is only confirmed if enough sources agree.

### Technical Explanation

#### Architecture (enhanced_hybrid_detector.py)

```python
class EnhancedHybridDetector:
    def __init__(self):
        self.rule_based = True           # Always available
        self.custom_model = None         # Custom-trained YOLO (optional)
        self.coco_model = None           # Standard YOLOv8n
        self.voting_mode = 'any'         # 'any', 'majority', 'all'
    
    def detect(self, frame):
        votes = {}
        
        # Source 1: Rule-based CV
        rule_detections = self._rule_based_detect(frame)
        for det in rule_detections:
            votes[det] = votes.get(det, 0) + 1
        
        # Source 2: Custom YOLO model
        if self.custom_model:
            custom_detections = self._custom_model_detect(frame)
            for det in custom_detections:
                votes[det] = votes.get(det, 0) + 1
        
        # Source 3: COCO YOLO model
        if self.coco_model:
            coco_detections = self._coco_detect(frame)
            for det in coco_detections:
                votes[det] = votes.get(det, 0) + 1
        
        # Apply voting
        confirmed = []
        for action, count in votes.items():
            if self.voting_mode == 'any' and count >= 1:
                confirmed.append(action)
            elif self.voting_mode == 'majority' and count >= 2:
                confirmed.append(action)
            elif self.voting_mode == 'all' and count >= 3:
                confirmed.append(action)
        
        return confirmed
```

#### Voting Modes

| Mode | Requirement | Use Case |
|------|------------|----------|
| `any` | 1+ sources agree | Maximum recall, catches everything (current default) |
| `majority` | 2+ sources agree | Balanced — reduces false positives |
| `all` | 3 sources agree | Maximum precision, only high-confidence detections |

#### Custom Model's 10 Detection Classes

```python
CUSTOM_CLASSES = {
    0: 'mobile_phone',
    1: 'cheat_sheet',
    2: 'hand_signal',
    3: 'looking_sideways',
    4: 'passing_paper',
    5: 'turning_back',
    6: 'leaning',
    7: 'talking',
    8: 'suspicious_object',
    9: 'normal_behavior',
}
```

> **Note**: The production system currently uses the `pretrained` preset (COCO models + rule-based detection) rather than the hybrid detector. The hybrid detector is infrastructure for future custom-model integration.

---

# Part C — Testing & Results

## How to Test the ML Pipeline

### 1. Unit Test: Individual Detection Functions

```python
# Test leaning detection with known keypoints
import numpy as np
from ML.frame_processor import is_leaning

# Simulated keypoints: nose far right of shoulder midpoint
keypoints = np.zeros((17, 3))
keypoints[0] = [400, 100, 0.9]   # Nose (far right)
keypoints[5] = [200, 200, 0.9]   # Left shoulder
keypoints[6] = [300, 200, 0.9]   # Right shoulder
# shoulder_mid = 250, offset = 150, width = 100, ratio = 1.5 > 0.4 → True

assert is_leaning(keypoints) == True
```

### 2. Integration Test: Full Frame Processing

```python
from ML.frame_processor import FrameProcessor, get_cached_models
import cv2

processor = FrameProcessor(teacher_id=1, hall_name='LH1')
frame = cv2.imread('test_frame.jpg')
_, buffer = cv2.imencode('.jpg', frame)
result_bytes, detections = processor.process_frame(buffer.tobytes())
print(f"Detections: {detections}")
```

### 3. Live Test: Webcam Quick Test

```bash
python ML/quick_start.py  # Opens webcam, runs full pipeline, shows annotated feed
```

### 4. GPU Verification

```bash
python ML/check_gpu.py    # Prints CUDA status, GPU name, memory
python ML/quick_gpu_test.py  # Runs inference benchmark
```

## Expected Performance Metrics

| Metric | Target | Actual (RTX 3050) |
|--------|--------|-------------------|
| Live inference latency | < 100ms/frame | ~60-80ms |
| Pose model inference | < 30ms | ~20ms |
| Object model inference | < 40ms | ~30ms |
| GPU memory usage | < 2GB | ~1.2GB (FP16) |
| Effective live FPS | 10-15 FPS | ~13 FPS |
| Uploaded video processing | 3-5x realtime | ~4x realtime |

---

# Part D — Viva Q&A Bank (60+ Questions)

## Fundamentals

**Q1: What is YOLO and why did you choose it?**
YOLO (You Only Look Once) is a single-stage object detection model that processes the entire image in one forward pass, unlike two-stage detectors (R-CNN) that first propose regions then classify. We chose YOLO because: (1) real-time inference speed — under 30ms per frame, (2) pre-trained on COCO dataset with 80 classes including "cell phone", (3) pose variant gives 17 skeleton keypoints for behavioral analysis, (4) Ultralytics library provides easy Python API.

**Q2: Why YOLOv8n-pose specifically? Why not a larger model like YOLOv8x-pose?**
The "n" (nano) variant has ~3.3M parameters vs "x" (extra-large) with ~69M. On our RTX 3050 (4GB VRAM), the nano model runs at ~20ms inference while x-large would take ~150ms+ and exceed VRAM when running two models simultaneously. Since we use frame-counting thresholds (3+ consecutive frames), the slight accuracy difference is compensated by temporal consistency.

**Q3: What is the COCO dataset and what are its 80 classes?**
COCO (Common Objects in Context) is a large-scale dataset with 80 object categories including person, bicycle, car, airplane, etc. Class 67 is "cell phone" which we use for mobile detection. The dataset has 330K images with 1.5M object instances. Our YOLO models are pre-trained on COCO.

**Q4: What does "confidence threshold" mean?**
It's the minimum probability from the YOLO model to accept a detection. We use 0.3 for pose and 0.25 for object detection. A detection with confidence 0.2 is ignored. Lower thresholds catch more but increase false positives; higher thresholds miss detections but reduce noise. We compensate for low thresholds with our frame-counting system.

**Q5: Why two separate YOLO models instead of one?**
Pose estimation and object detection are fundamentally different tasks. The pose model outputs 17 keypoints per person (nose, eyes, shoulders, etc.) — it doesn't detect objects. The object detection model outputs bounding boxes with class labels — it doesn't know body keypoints. Using both gives us skeletal behavioral analysis AND object identification.

## Detection Algorithms

**Q6: Explain the leaning detection algorithm mathematically.**
We extract nose position and both shoulder positions from YOLOv8-pose keypoints. Compute shoulder midpoint $x_{mid} = \frac{x_{LS} + x_{RS}}{2}$ and shoulder width $w = |x_{LS} - x_{RS}|$. Calculate nose offset $d = |x_{nose} - x_{mid}|$. Compute ratio $r = \frac{d}{w}$. If $r > 0.4$, the person is leaning. The ratio normalizes for camera distance.

**Q7: Why does turning back detection use eye distance vs shoulder distance?**
When facing the camera, inter-eye distance is about 40-50% of shoulder width. When turned 90°+, eyes appear co-located (nearly 0 distance) while shoulders remain visible. The ratio $\frac{d_{eyes}}{d_{shoulders}} < 0.15$ reliably detects this geometric collapse.

**Q8: How does passing paper detection handle multiple people?**
We iterate over all $\binom{N}{2}$ pairs of detected persons and check all 4 wrist combinations (left-left, left-right, right-left, right-right). Euclidean distance < 200px between any pair of wrists from different people triggers the detection.

**Q9: Why is the hand raise threshold 5 frames instead of 3?**
Brief hand movements (scratching, adjusting hair, stretching) are common and innocent. A deliberately raised hand for signaling must be sustained. 5 frames at 15 FPS = 0.33 seconds filters out transient movements while catching intentional signals.

**Q10: What is the is_likely_phone() filter and why is it needed?**
YOLO sometimes misclassifies calculators, remote controls, or dark rectangular objects as phones. The filter checks: (1) aspect ratio is phone-like (portrait: 1.2-3.0, landscape: 0.3-0.8), (2) size is between 0.1% and 15% of frame area. This eliminates oversized false positives (TV screens) and tiny noise.

**Q11: How does suspicious movement detection work?**
We track the nose $(x,y)$ position over 10 consecutive frames and compute the sum of x-variance and y-variance. If $\text{Var}(x) + \text{Var}(y) > 50$, the head is moving rapidly, indicating suspicious scanning behavior. Normal reading has variance < 20.

**Q12: What's the difference between "Leaning" and "Peeking Sideways"?**
Both use the nose-shoulder offset ratio. Leaning triggers at ratio > 0.4 (significant body lean). Peeking Sideways triggers at 0.25 < ratio < 0.7 (head turn without full body lean). In practice, the uploaded video processor uses Peeking as a separate detection category with different handling.

## GPU & Optimization

**Q13: What is FP16 and why do we use it?**
FP16 (half-precision floating point) uses 16 bits instead of 32 bits per number. Benefits: (1) 50% less GPU memory — both models fit in RTX 3050's 4GB VRAM, (2) ~2x faster on Tensor Cores (specialized FP16 hardware in RTX GPUs), (3) negligible accuracy loss for inference (< 0.1%). We call `model.model.half()` to convert all weights.

**Q14: What is cuDNN benchmark mode?**
Setting `torch.backends.cudnn.benchmark = True` tells cuDNN to test multiple convolution algorithms on the first forward pass and cache the fastest one. Subsequent passes use the cached algorithm. This gives ~10-20% speedup but only works when input sizes are consistent (ours are — fixed 320/640 resolution).

**Q15: What is compute capability and how does it affect our code?**
CUDA compute capability is a version number indicating GPU features. Our RTX 3050 is 8.6 (Ampere). We check `capability >= 7.0` before enabling FP16, because GPUs below 7.0 (pre-Volta) lack efficient FP16 Tensor Cores and would actually be slower with FP16.

**Q16: Why do we pre-warm models at server startup?**
The first CUDA inference triggers JIT compilation of GPU kernels, taking 500ms+. Pre-warming with a dummy frame during startup moves this latency to boot time rather than the first real webcam frame.

**Q17: How much GPU memory does our pipeline use?**
Each YOLO nano model in FP16 uses ~100-150MB. Two models total ~300MB. Frame buffers and CUDA workspace add ~200MB. Total: ~500MB-1.2GB, well within RTX 3050's 4GB. This leaves headroom for multiple simultaneous streams.

## Pipeline Architecture

**Q18: What is the frame-dropping pattern and why is it used?**
The consumer stores only the `_latest_frame` and a `_ml_busy` flag. When a new frame arrives, it overwrites the previous one. ML only starts if not already busy. This means if ML takes 80ms and frames arrive every 67ms, some frames are skipped. This prevents unbounded queue growth and keeps latency constant.

**Q19: Explain the pre-roll buffer mechanism.**
A `collections.deque(maxlen=15)` stores the last 15 frames (1 second at 15 FPS). When a detection triggers, these 15 frames are written to the video file BEFORE the detection frame, giving the reviewer context of what happened leading up to the malpractice.

**Q20: What is the grace period and why is it important?**
After a detection ends (counter resets to 0), we continue recording for 30 more frames (2 seconds). This captures the aftermath (e.g., student putting phone away after being caught). Without grace, the clip would cut abruptly at the exact moment the behavior stops.

**Q21: Why does the uploaded video processor use a separate thread?**
Django's `StreamingHttpResponse` runs in the async event loop. PyTorch GPU inference is a blocking CPU-bound operation that would freeze the event loop, causing timeouts and dropped connections. The background thread runs ML independently, putting results into a `Queue(maxsize=600)` that the main thread consumes asynchronously.

**Q22: What is FRAME_SKIP=3 in the uploaded video processor?**
We only process every 3rd frame (frames 0, 3, 6, 9...). Between processed frames, the last annotated result is repeated. This gives 3x processing speed with minimal detection loss since malpractice behaviors persist over many frames.

**Q23: Why is the MJPEG stream used instead of WebSocket for uploaded video?**
Uploaded video processing is a request-response flow — the teacher uploads a file and waits for results. MJPEG over HTTP (`multipart/x-mixed-replace`) is simpler than WebSocket for one-directional streaming, requires no client-side JavaScript for rendering (just `<img src="...">` natively works), and is served via Django's `StreamingHttpResponse`.

**Q24: What is the difference between the live and uploaded video pipelines?**

| Aspect | Live (frame_processor.py) | Uploaded (process_uploaded_video_stream.py) |
|--------|--------------------------|---------------------------------------------|
| Input | WebSocket binary frames | Video file on disk |
| FPS | 15 (from webcam) | Source video FPS ÷ FRAME_SKIP |
| Output | WebSocket binary + JSON | MJPEG HTTP stream |
| Thread model | Async in consumer | Separate background thread |
| Pose resolution | 320px | 416px |
| Recording | Per-action VideoWriter | Per-action VideoWriter |
| Frame dropping | Latest-frame overwrite | FRAME_SKIP=3 |

## Video & Evidence

**Q25: Why record in mp4v (.avi) then convert to H.264 (.mp4)?**
OpenCV's `VideoWriter` reliably supports mp4v (MPEG-4 Part 2) on all platforms. H.264 support varies by platform and OpenCV build. Recording in mp4v ensures we get a valid video file, then we convert to H.264 for browser compatibility.

**Q26: Explain the 3-strategy H.264 conversion fallback.**
Strategy 1: System-installed ffmpeg (fastest, best quality). Strategy 2: imageio-ffmpeg Python package (bundles ffmpeg binary). Strategy 3: OpenCV with avc1 codec (works if OpenCV was compiled with H.264 support). If all fail, we keep the .avi file — it's viewable in VLC even if browsers can't play it.

**Q27: How are evidence videos linked to database records?**
When recording stops, the `_stop_recording()` method saves the video file to `media/uploaded_videos/`, computes the probability score, and creates a `MalpraticeDetection` database record with `proof` = filename, `probability_score` = computed score, `source_type` = 'live' or 'recorded', and `lecture_hall` = the associated hall.

## Probability Scoring

**Q28: Walk through the probability formula with an example.**
Mobile phone detected for 20 seconds in 120 of 300 frames at 0.8 avg confidence:
- Duration: min(20/30, 1) × 100 = 66.7
- Density: min(120/300 × 1.5, 1) × 100 = min(0.6, 1) × 100 = 60
- Confidence: 0.8 × 100 = 80
- Sustainability: 120/300 × 100 = 40
- Type prior (Mobile): 85
- Final: 66.7(0.30) + 60(0.25) + 80(0.20) + 40(0.15) + 85(0.10) = 20.0 + 15.0 + 16.0 + 6.0 + 8.5 = **65.5**

**Q29: Why is the density score boosted by 1.5x?**
Without the boost, a detection present in 67% of frames would score only 67. With 1.5x boost, it maxes out at 100. This rewards concentrated detection — a malpractice present in most frames of a recording is more trustworthy than one appearing sporadically.

**Q30: Why are type priors different for each action?**
Mobile phone in an exam (85) is almost certainly cheating — there's no innocent reason. Hand raising (40) could be asking a legitimate question. Passing paper (80) strongly suggests cheating. These priors encode real-world likelihood and prevent the score from being dominated by detection quality alone.

**Q31: What's the maximum possible probability score?**
Theoretically 100, if all factors max out: detected for 30+ seconds (duration=100), >67% density after boost (density=100), 1.0 model confidence (confidence=100), and a high-prior type. In practice, scores above 85 indicate very strong evidence.

**Q32: What's the minimum score that should concern an examiner?**
Scores below 30 are usually noise. 30-50 deserves a quick video review. 50-70 is moderate evidence. 70+ is strong evidence. These intervals are displayed in the UI with color coding.

## Hybrid Detection

**Q33: What are the three sources in the hybrid detector?**
(1) Rule-based: mathematical calculations on YOLO pose keypoints (nose/shoulder ratios, wrist distances). (2) Custom YOLO: a separately trained model on exam-specific malpractice images. (3) COCO YOLO: standard pre-trained model detecting objects like phones.

**Q34: What is the "majority" voting mode?**
A detection is only confirmed if 2 out of 3 sources independently agree. This drastically reduces false positives — if only the rule-based detector sees "leaning" but neither model agrees, it's likely a false positive. Currently, the system uses "any" mode (1 source suffices) for maximum recall.

**Q35: Is the hybrid detector used in production right now?**
No. The production pipeline uses `frame_processor.py` with COCO pre-trained models + rule-based keypoint analysis. The hybrid detector (`enhanced_hybrid_detector.py`) is infrastructure for future integration when custom-trained models are ready.

## Advanced / Edge Cases

**Q36: What happens if the GPU runs out of memory?**
PyTorch will throw `torch.cuda.OutOfMemoryError`. The code doesn't explicitly handle this — in practice, two FP16 nano models use ~300MB, well within 4GB. If this occurred (e.g., running multiple instances), the fallback would be to use CPU inference (automatically via `device='cpu'`).

**Q37: What happens if CUDA is not available?**
All model loading code checks `torch.cuda.is_available()`. If False, models load on CPU. Inference is ~5-10x slower but functional. FP16 is disabled on CPU (not beneficial). The system would process at ~2-3 FPS instead of 13+ FPS.

**Q38: How do you handle partially visible people (occluded keypoints)?**
Every detection function checks keypoint confidence > 0.3 before using it. If critical keypoints (nose, shoulders) are occluded (confidence < 0.3), the detection returns False rather than producing false positives from unreliable positions.

**Q39: Can two people's leaning be detected simultaneously?**
Yes. The pipeline iterates over ALL detected people in a frame. If person A and person B are both leaning, both trigger the counter. However, the counter is global per action type (not per person), so one leaning person is sufficient to trigger recording.

**Q40: What about identical actions from different students?**
The current design detects actions globally, not per-student. If student A stops leaning and student B starts, the counter continues incrementing. This is a design tradeoff — per-student tracking would require person re-identification across frames (complex tracking), which is not implemented.

**Q41: Why is MediaPipe in requirements.txt but not used?**
MediaPipe was initially explored for pose estimation but replaced by YOLOv8-pose for consistency (single framework) and better multi-person support. The `mediapipe_detector.py` file exists as legacy code.

**Q42: What is the model_config.py preset system for?**
It allows switching between `pretrained` (COCO models, phone = class 67) and `custom` (custom-trained model, phone = class 0) without changing any detection code. Just change `ACTIVE_PRESET = 'custom'` and all model paths and class IDs update automatically.

## Conceptual / Theoretical

**Q43: What is pose estimation vs object detection?**
Object detection finds WHERE objects are (bounding boxes + class labels). Pose estimation finds WHERE body parts are (17 keypoints per person). We need both — objects for phone detection, pose for behavioral analysis (leaning, turning, hand raise).

**Q44: What are YOLO's 17 COCO keypoints?**
0: Nose, 1: Left Eye, 2: Right Eye, 3: Left Ear, 4: Right Ear, 5: Left Shoulder, 6: Right Shoulder, 7: Left Elbow, 8: Right Elbow, 9: Left Wrist, 10: Right Wrist, 11: Left Hip, 12: Right Hip, 13: Left Knee, 14: Right Knee, 15: Left Ankle, 16: Right Ankle. We primarily use indices 0, 1, 2, 5, 6, 9, 10.

**Q45: What is the difference between single-stage and two-stage detectors?**
Two-stage (Faster R-CNN): first a Region Proposal Network generates candidate bounding boxes, then each is classified. Slow but accurate. Single-stage (YOLO, SSD): processes entire image in one pass through the network. Much faster, slightly less accurate. YOLO achieves near-real-time speeds critical for our application.

**Q46: What is NMS (Non-Maximum Suppression)?**
YOLO often produces multiple overlapping boxes for the same object. NMS keeps only the highest-confidence box and removes boxes with IoU (Intersection over Union) > 0.45. Ultralytics handles this internally via the `nms` parameter.

**Q47: What is the role of the anchor boxes in YOLO?**
Earlier YOLO versions (v1-v4) used predefined anchor boxes as templates for prediction. YOLOv8 is anchor-free — it directly predicts bounding box center, width, and height without predefined anchors. This simplifies the architecture and improves performance on irregular object sizes.

**Q48: Why imgsz=320 for pose but imgsz=640 for object detection?**
Pose estimation only needs to find large, prominent keypoints on the human body — these are visible even at 320px. Phone detection requires identifying small objects (a phone might be only 30×60 pixels in the original frame), so higher resolution (640px) helps YOLO see small objects. This is a speed-accuracy tradeoff.

**Q49: What is the `verbose=False` parameter in YOLO inference?**
It suppresses per-frame console output (bounding box counts, inference times). Without it, YOLO prints a line for every frame — at 15 FPS that's 15 print statements per second, which floods logs and slows I/O.

**Q50: Explain transfer learning as it applies to your custom model training.**
Our custom model (not yet in production) would use a YOLO model pre-trained on COCO, then fine-tune it on exam-specific malpractice images. The pretrained weights already understand edges, shapes, and objects. Fine-tuning only adjusts the final layers to recognize exam-specific classes (cheat sheets, hand signals) rather than learning from scratch, requiring far less training data.

## Code-Specific Details

**Q51: What does `results[0].keypoints.data.cpu().numpy()` do?**
`results[0]` — first image result (batch size 1). `.keypoints` — pose keypoints tensor. `.data` — raw tensor without metadata. `.cpu()` — moves from GPU to CPU memory (NumPy can't access GPU). `.numpy()` — converts PyTorch tensor to NumPy array. Result shape: `(num_people, 17, 3)` where 3 is `[x, y, confidence]`.

**Q52: Why `collections.deque(maxlen=15)` for the pre-roll buffer?**
`deque` with `maxlen` automatically discards the oldest item when a new one is appended and the buffer is full. This gives O(1) append and automatic size management. A regular list would require manual `pop(0)` which is O(N).

**Q53: Why is frame encoding at JPEG quality 70?**
`cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])` — quality 70% reduces JPEG size by ~60% vs quality 95 with minimal visible difference. This is critical for WebSocket throughput — at 15 FPS, even small size savings compound significantly. 720p at q70 ≈ 30-50KB vs q95 ≈ 100-150KB per frame.

**Q54: What does `np.frombuffer(frame_bytes, np.uint8)` do?**
Converts raw bytes (from WebSocket binary message) into a 1D NumPy array of unsigned 8-bit integers. Then `cv2.imdecode(arr, cv2.IMREAD_COLOR)` decodes this JPEG buffer into a 3D BGR image array (height × width × 3 channels).

**Q55: In the threading.Lock pattern, what happens if a thread crashes while holding the lock?**
If an exception occurs inside `with _models_lock:`, the context manager automatically releases the lock (via `__exit__`). Without the context manager (`lock.acquire()` without `try/finally`), a crash would deadlock all other threads waiting for the lock.

## System Integration

**Q56: How does the ML pipeline communicate results to the frontend?**
Two channels: (1) The annotated JPEG frame is sent back via WebSocket binary message — the browser displays it as an `<img>` overlay. (2) Detection metadata (type, confidence, timestamp) is sent as JSON via the notification WebSocket, showing in the detection log panel.

**Q57: How are ML detections saved to the database?**
When video recording stops (detection ended + grace period expired), `_stop_recording()` creates a `MalpraticeDetection` database entry via Django ORM: `MalpraticeDetection.objects.create(date=..., time=..., malpractice=action_type, proof=filename, probability_score=score, lecture_hall=hall, source_type='live'/'recorded')`.

**Q58: What triggers model loading — server start or first connection?**
Lazy singleton loading: models load on the first WebSocket connection that needs ML. However, `prewarm_models()` can be called at server startup to eagerly load. In production, pre-warming is recommended to avoid first-frame latency.

**Q59: How many simultaneous camera streams can the ML handle?**
On RTX 3050, realistically 3-5 simultaneous live streams at 13 FPS each. GPU memory is the bottleneck — models are shared (singleton), but each stream's frames compete for GPU compute time. Beyond 5 streams, FPS per stream drops significantly.

**Q60: What happens if a teacher disconnects mid-stream?**
The WebSocket `disconnect()` handler in `CameraStreamConsumer` calls `_save_all_recordings()`, which stops all active VideoWriters, converts to H.264, computes probability scores, and saves to database. No evidence is lost.

## Comparison / Justification Questions

**Q61: Why not use a cloud AI service (AWS Rekognition, Google Vision)?**
(1) Latency — cloud roundtrip adds 200-500ms vs 60ms local GPU inference. (2) Cost — per-frame API pricing would be prohibitive for continuous monitoring. (3) Privacy — exam footage shouldn't leave institutional network. (4) Offline capability — our system works on a LAN without internet.

**Q62: Why not use OpenPose instead of YOLO for pose?**
OpenPose is a bottom-up approach (find all keypoints, then group into people). YOLOv8-pose is top-down (detect person, then find their keypoints). YOLO is faster for our use case (few people in frame), has a simpler API (Ultralytics), and we already need YOLO for object detection — one framework for both tasks.

**Q63: Why not use tracking (DeepSORT) for per-person detection?**
Tracking would enable per-student malpractice attribution (which student is cheating). However, it adds complexity (appearance features, Kalman filtering, ID management) and computational cost. Our current design detects actions globally — any detected malpractice in the frame triggers recording. Per-student tracking is a planned future enhancement.

**Q64: What improvements would you make with more time?**
(1) Per-student tracking with DeepSORT/ByteTrack for individual attribution. (2) Custom-trained YOLO model on exam-specific malpractice data. (3) Attention-based models (transformers) for temporal pattern recognition. (4) Multi-camera fusion to detect cross-camera passing. (5) Ensemble scoring with multiple probability algorithms.

---

> **Study Tips for Person 1:**
> - Practice drawing the architecture diagram from memory
> - Memorize the 7 detection algorithms and their exact thresholds/ratios
> - Work through 2-3 probability score calculations by hand
> - Know which keypoint indices are used for each detection
> - Understand WHY each threshold was chosen (not just the value)
> - Be able to explain FP16, cuDNN benchmark, and model singleton in plain English
> - Know the exact files you own and their line counts
