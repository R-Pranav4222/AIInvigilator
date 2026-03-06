# AIInvigilator — Project Evaluation Study Guide

## Project Overview

**AIInvigilator** is a real-time AI-powered examination surveillance system that uses computer vision and deep learning to automatically detect malpractice during classroom exams. It supports both live webcam monitoring (where teachers' cameras stream to an admin dashboard) and pre-recorded video analysis (where uploaded exam footage is processed for cheating).

### What Problem Does It Solve?

Traditional exam invigilation relies on human observers who:
- Can only watch one area at a time
- Get fatigued over long exam sessions
- May miss subtle cheating behaviors
- Cannot review incidents after the fact

AIInvigilator automates this by analyzing video frames using AI models (YOLO) to detect 7 types of malpractice, record video evidence, calculate probability scores, and notify teachers — all in real-time.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT SIDE                                     │
│                                                                              │
│   ┌─────────────────┐         ┌──────────────────────┐                      │
│   │  Admin Browser   │         │  Teacher Browser      │                    │
│   │  (run_cameras)   │◄──WS──►│  (teacher_cameras)    │                    │
│   │  - Grid view     │         │  - Webcam capture     │                    │
│   │  - Controls      │         │  - Annotated feed     │                    │
│   │  - Notifications │         │  - Camera controls    │                    │
│   └────────┬─────────┘         └──────────┬────────────┘                    │
│            │ WebSocket                     │ WebSocket                        │
└────────────┼───────────────────────────────┼────────────────────────────────┘
             │                               │
┌────────────┼───────────────────────────────┼────────────────────────────────┐
│            │         SERVER SIDE           │                                 │
│            ▼                               ▼                                 │
│   ┌─────────────────────────────────────────────────────────┐               │
│   │           Django Channels (ASGI/Daphne)                  │               │
│   │                                                          │               │
│   │  ┌──────────────────┐  ┌─────────────────────┐         │               │
│   │  │NotificationConsumer│ │CameraStreamConsumer │         │               │
│   │  │- Camera requests  │  │- Receive JPEG frames │         │               │
│   │  │- Permission flow  │  │- ML Processing      │         │               │
│   │  │- Status updates   │  │- Video recording     │         │               │
│   │  └──────────────────┘  │- Send annotated back  │         │               │
│   │                         └──────────┬────────────┘         │               │
│   │  ┌──────────────────┐             │                      │               │
│   │  │AdminGridConsumer  │◄───────────┘                      │               │
│   │  │- Receive teacher  │  (forwards raw frames)            │               │
│   │  │  frames for grid  │                                   │               │
│   │  └──────────────────┘                                    │               │
│   └──────────────────────────────────────────────────────────┘               │
│                         │                                                     │
│                         ▼                                                     │
│            ┌─────────────────────────┐                                       │
│            │   ML Pipeline (PyTorch) │                                       │
│            │   ┌─────────────────┐   │                                       │
│            │   │ YOLOv8n-pose    │   │  ← Pose estimation (17 keypoints)     │
│            │   │ YOLOv11n        │   │  ← Object detection (cell phone)      │
│            │   │ FrameProcessor  │   │  ← Detection logic + recording        │
│            │   └─────────────────┘   │                                       │
│            │   GPU: RTX 3050 (CUDA)  │                                       │
│            └────────────┬────────────┘                                       │
│                         │                                                     │
│                         ▼                                                     │
│            ┌─────────────────────────┐                                       │
│            │   MySQL Database        │                                       │
│            │   - MalpracticeDetection│                                       │
│            │   - CameraSession       │                                       │
│            │   - LectureHall         │                                       │
│            │   - TeacherProfile      │                                       │
│            │   - ReviewSession       │                                       │
│            └─────────────────────────┘                                       │
│                                                                               │
│            ┌─────────────────────────┐                                       │
│            │   File System (media/)  │                                       │
│            │   - Video proof clips   │                                       │
│            │   - Detection snapshots │                                       │
│            │   - Profile pictures    │                                       │
│            └─────────────────────────┘                                       │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Work Division Among 4 Members

| Person | Area | Key Files | Key Technologies |
|--------|------|-----------|-----------------|
| **Person 1** | ML/AI Detection Pipeline | `frame_processor.py`, `process_uploaded_video_stream.py`, `model_config.py`, `gpu_config.py` | PyTorch, YOLO (v8-pose + v11n), OpenCV, CUDA, NumPy |
| **Person 2** | Backend — WebSockets & Real-Time Communication | `consumers.py`, `routing.py`, `asgi.py`, `models.py` | Django Channels, Daphne (ASGI), WebSockets, Redis, Channel Layer |
| **Person 3** | Backend — Django Views, Database & Notifications | `views.py`, `urls.py`, `settings.py`, `models.py`, `.env`, `forms.py`, `utils.py` | Django, MySQL, Email (SMTP), Twilio (SMS), REST APIs |
| **Person 4** | Frontend — UI/UX, Templates & Client-Side Logic | All `.html` templates, `static/css/theme.css`, `header.html`, `footer.html`, JS in templates | HTML5, CSS3, JavaScript (vanilla), Bootstrap, WebSocket API, MediaStream API |

---

## Key Technologies & Why We Chose Them

| Technology | Purpose | Why This Over Alternatives? |
|------------|---------|----------------------------|
| **Django** | Web framework | Full-featured (auth, admin, ORM, forms). Flask is too minimal. FastAPI lacks built-in auth/admin. |
| **Daphne + Channels** | ASGI server + WebSocket handling | Native Django integration. Uvicorn lacks Channels support. Socket.IO adds JS dependency. |
| **PyTorch + CUDA** | ML inference on GPU | Industry standard, best NVIDIA GPU support. TensorFlow is heavier and harder to debug. |
| **YOLOv8n-pose** | Pose estimation (17 keypoints) | Fastest pose model, real-time capable. OpenPose is 10x slower. MediaPipe is less accurate for multi-person. |
| **YOLOv11n** | Object detection (phone) | Latest YOLO, best speed/accuracy. COCO-pretrained, detects 80 classes including cell phones (class 67). |
| **MySQL** | Database | Required by project specs. PostgreSQL would also work. SQLite can't handle concurrent writes from WebSockets. |
| **Redis** | Channel layer (WebSocket message routing) | In-memory, extremely fast pub/sub. Required by Django Channels for production. InMemoryChannelLayer used for development. |
| **OpenCV** | Frame decoding/encoding, video writing | De facto standard for computer vision. Fastest JPEG decode/encode. VideoWriter for evidence clips. |
| **H.264/ffmpeg** | Browser-compatible video encoding | OpenCV writes mp4v codec which browsers can't play. H.264 is universally supported. |
| **Twilio** | SMS notifications | Reliable API, good Python SDK. Free tier available. Alternatives: Vonage, AWS SNS (more complex). |
| **Gmail SMTP** | Email notifications | Simple setup, free. SendGrid/Mailgun are alternatives for production. |

---

## Detection Types Summary

| # | Detection | Method | Key Keypoints / Logic |
|---|-----------|--------|----------------------|
| 1 | **Mobile Phone** | YOLOv11n object detection | COCO class 67 + smart phone/calculator filter (aspect ratio + area) |
| 2 | **Turning Back** | Pose-based (eye-shoulder ratio) | If `|left_eye.x - right_eye.x| / |left_shoulder.x - right_shoulder.x| < 0.3` → turned |
| 3 | **Leaning** | Pose-based (nose-shoulder offset) | If `|nose.x - mid_shoulder.x| / shoulder_width > 0.6` → leaning |
| 4 | **Hand Raising** | Pose-based (wrist above shoulder) | If `wrist.y < shoulder.y` for either arm → hand raised |
| 5 | **Paper Passing** | Multi-person proximity | If wrists from DIFFERENT people are within threshold distance → passing |
| 6 | **Looking Around** | Head angle analysis | Combined peeking sideways + looking down detection |
| 7 | **Suspicious Movement** | Keypoint trajectory | Rapid head movement variance over 30-frame window |

---

## Probability Scoring System

Every detection gets a 0-100% score using these weighted factors:

```
Score = (Duration × 0.30) + (Density × 0.25) + (Confidence × 0.20) + (Sustainability × 0.15) + (TypePrior × 0.10)
```

| Factor | Weight | What It Measures |
|--------|--------|-----------------|
| Duration | 30% | How long was the action detected? Longer = more likely real |
| Density | 25% | What fraction of frames had this detection? Higher = more consistent |
| Confidence | 20% | Average YOLO confidence score for the detections |
| Sustainability | 15% | How continuous was the detection? (vs. flickering on/off) |
| Type Prior | 10% | Base probability by malpractice type (phone = 0.80, hand raise = 0.30) |

---

## Individual Study Guides

Each person's detailed study guide is in a separate file:

1. **[Person 1 — ML/AI Pipeline](PERSON_1_ML_AI_PIPELINE.md)**
2. **[Person 2 — WebSockets & Real-Time](PERSON_2_WEBSOCKETS_REALTIME.md)**
3. **[Person 3 — Django Backend & Database](PERSON_3_DJANGO_BACKEND.md)**
4. **[Person 4 — Frontend & UI](PERSON_4_FRONTEND_UI.md)**
