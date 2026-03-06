# AIInvigilator — Comprehensive Study Guide
# PERSON 2: Django Backend, WebSocket & Real-Time Communication

---

## TABLE OF CONTENTS

- [Part A — Work Assignment & Overview](#part-a--work-assignment--overview)
- [Part B — Implementation Deep-Dive](#part-b--implementation-deep-dive)
  - [B1. Django ASGI Architecture — Why Not WSGI](#b1-django-asgi-architecture--why-not-wsgi)
  - [B2. Django Channels & Channel Layers](#b2-django-channels--channel-layers)
  - [B3. WebSocket Routing (routing.py + asgi.py)](#b3-websocket-routing-routingpy--asgipy)
  - [B4. NotificationConsumer — The Command Center](#b4-notificationconsumer--the-command-center)
  - [B5. CameraStreamConsumer — Live ML Pipeline Bridge](#b5-camerastreamconsumer--live-ml-pipeline-bridge)
  - [B6. AdminGridConsumer — High-Performance Frame Delivery](#b6-admingridconsumer--high-performance-frame-delivery)
  - [B7. Binary WebSocket Protocol Design](#b7-binary-websocket-protocol-design)
  - [B8. Admin Heartbeat & Presence System](#b8-admin-heartbeat--presence-system)
  - [B9. Views — Authentication & User Management](#b9-views--authentication--user-management)
  - [B10. Views — Malpractice Log (Complex Filtering)](#b10-views--malpractice-log-complex-filtering)
  - [B11. Views — Review System & Notifications](#b11-views--review-system--notifications)
  - [B12. Views — Video Serving with H.264 + HTTP Range](#b12-views--video-serving-with-h264--http-range)
  - [B13. Views — Video Upload & MJPEG Streaming](#b13-views--video-upload--mjpeg-streaming)
  - [B14. Views — Lecture Hall & Teacher Management](#b14-views--lecture-hall--teacher-management)
  - [B15. Views — Camera Script Triggering (Legacy)](#b15-views--camera-script-triggering-legacy)
  - [B16. Utility Layer (utils.py) — SMS, SSH, Script Runner](#b16-utility-layer-utilspy--sms-ssh-script-runner)
  - [B17. Custom Email Backend](#b17-custom-email-backend)
  - [B18. Security Implementation](#b18-security-implementation)
- [Part C — Testing & Results](#part-c--testing--results)
- [Part D — Viva Q&A Bank (60+ Questions)](#part-d--viva-qa-bank-60-questions)

---

# Part A — Work Assignment & Overview

## What Person 2 Owns

You are responsible for the **entire Django backend**, including all WebSocket consumers (real-time communication), HTTP views (page rendering + API endpoints), utility functions (email/SMS/SSH), security configuration, and the ASGI server architecture. You are the bridge between the ML pipeline (Person 1), the frontend (Person 3), and the database (Person 4).

### Files You Must Know Inside-Out

| File | Lines | Purpose |
|------|-------|---------|
| `app/consumers.py` | 1050 | 3 WebSocket consumers — notifications, camera streaming, admin grid |
| `app/views.py` | 1431 | All HTTP views — auth, malpractice log, review, video, admin pages |
| `app/urls.py` | 44 | URL routing — 30+ HTTP endpoint mappings |
| `app/routing.py` | 13 | WebSocket URL routing — 3 WS endpoints |
| `app/asgi.py` | 23 | ASGI entrypoint — HTTP + WebSocket protocol routing |
| `app/utils.py` | ~110 | Twilio SMS, SSH remote exec, local script runner, security |
| `app/custom_email_backend.py` | 30 | Custom SMTP backend (fixes starttls compatibility) |
| `app/settings.py` | 236 | Django configuration — DB, channels, security, email |
| `app/forms.py` | 20 | EditProfileForm + TeacherProfileForm |
| `start_server.py` | 160 | One-click server starter (Daphne + optional ngrok) |

### Key Libraries

| Library | Version | Role |
|---------|---------|------|
| Django | 6.0.2 | Web framework (ORM, views, templates, auth) |
| Channels | 4.3.2 | WebSocket support for Django (ASGI consumers) |
| Daphne | 4.2.1 | ASGI server (HTTP + WebSocket protocol server) |
| Twilio | 9.5.1 | SMS notification delivery |
| Paramiko | 3.5.1 | SSH remote script execution |
| SCP | 0.15.0 | Secure file copy over SSH |
| WhiteNoise | 6.9.0 | Static file serving in production |
| django-environ | 0.12.0 | Environment variable management (.env files) |

### High-Level Summary (Explain This Simply)

> "The backend is a Django application running on Daphne, an ASGI server that handles both regular HTTP requests and persistent WebSocket connections. We have three WebSocket endpoints: one for notifications and camera control commands between admin and teachers, one for streaming webcam frames from teachers with ML processing, and one for delivering processed frames to the admin's camera grid. The HTTP layer handles user authentication, malpractice log management with 10+ filters, a review workflow with email/SMS notifications, video upload with live MJPEG streaming, and lecture hall administration."

---

# Part B — Implementation Deep-Dive

---

## B1. Django ASGI Architecture — Why Not WSGI

### Simple Explanation
Regular Django uses WSGI (Web Server Gateway Interface) which handles one request at a time per worker — when a request comes in, it gets processed and a response is sent back. But WebSockets need **persistent connections** that stay open for minutes or hours. ASGI (Asynchronous Server Gateway Interface) supports both regular HTTP requests AND long-lived WebSocket connections simultaneously.

### Technical Explanation

#### WSGI vs ASGI Comparison

| Feature | WSGI (gunicorn) | ASGI (daphne) |
|---------|-----------------|---------------|
| Protocol | HTTP only | HTTP + WebSocket + HTTP/2 |
| Connection model | Request → Response → Close | Persistent connections supported |
| Concurrency | Thread/process per request | async/await event loop |
| Django support | `wsgi.py` | `asgi.py` |
| Use case | Traditional web apps | Real-time apps (chat, streaming) |

#### Our ASGI Configuration (asgi.py)

```python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from app.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),          # Regular Django views
    "websocket": AuthMiddlewareStack(        # WebSocket with auth
        URLRouter(websocket_urlpatterns)
    ),
})
```

#### How ProtocolTypeRouter Works

```
Incoming Connection
       │
       ├──► HTTP request? → get_asgi_application() → Django views (views.py)
       │
       └──► WebSocket upgrade? → AuthMiddlewareStack → URLRouter → consumers.py
```

**ProtocolTypeRouter**: Inspects the incoming connection protocol and routes accordingly. HTTP goes to standard Django. WebSocket connections are wrapped in `AuthMiddlewareStack` (which populates `self.scope['user']` from the session cookie) and then routed by URL pattern to the appropriate consumer.

**AuthMiddlewareStack**: Extracts the user from the Django session (uses the same session cookie as HTTP). This is why `self.scope['user']` is available in every consumer — the WebSocket handshake includes the browser's cookies.

#### Why Daphne (not Uvicorn or Hypercorn)?

Daphne is the **reference ASGI server** built by the Django Channels team. It has first-class support for Channels' layer protocol and is battle-tested with Django's async features. It handles:
- HTTP/1.1 requests → Django views
- WebSocket upgrade → Channels consumers
- Binary WebSocket messages (critical for our frame streaming)

---

## B2. Django Channels & Channel Layers

### Simple Explanation
Django Channels extends Django to handle WebSockets. A "channel layer" is a message bus — when the admin sends a "start camera" command, it goes to the channel layer, which delivers it to the specific teacher's WebSocket connection. Think of it like a post office that routes messages between connected clients.

### Technical Explanation

#### Channel Layer Configuration (settings.py)

```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
        'CONFIG': {
            'capacity': 1000,   # Max messages pending per channel
            'expiry': 10,       # Messages expire after 10 seconds
        },
    },
}
```

#### InMemoryChannelLayer vs Redis

| Feature | InMemoryChannelLayer | RedisChannelLayer |
|---------|---------------------|-------------------|
| Setup | Zero config | Requires Redis server |
| Multi-server | ❌ Single process only | ✅ Works across servers |
| Persistence | ❌ Lost on restart | Messages persist briefly |
| Performance | Fast (no network) | Slight network overhead |
| Our choice | ✅ Dev/Demo (single server) | Commented out (production) |

**Why InMemory?** Our demo runs on a single machine. InMemoryChannelLayer is simpler and avoids needing a Redis server. For production deployment across multiple servers, you'd switch to Redis:

```python
# Production config (commented in settings.py):
'BACKEND': 'channels_redis.core.RedisChannelLayer',
'CONFIG': {
    'hosts': [('127.0.0.1', 6379)],
},
```

#### Key Concepts

**Channel**: A unique mailbox for each WebSocket connection (e.g., `specific.abc123def`). Each consumer instance gets a unique `self.channel_name`.

**Group**: A named collection of channels. Messages sent to a group are delivered to ALL channels in that group.

```python
# Our groups:
'notifications_global'      # Everyone
'admin_notifications'        # Admin users only
'user_{teacher_id}'         # Specific teacher
'camera_stream_{teacher_id}' # Teacher's camera stream
'admin_camera_grid'          # Admin grid viewers
```

**group_send**: Sends a message to all channels in a group.
```python
await self.channel_layer.group_send(
    'admin_notifications',        # Target group
    {
        'type': 'session.update',  # Maps to session_update() method
        'session': session_data,
    }
)
```

**Important**: The `type` field uses dot notation (`session.update`), which Django Channels converts to an underscore method name (`session_update`) on the receiving consumer. This is how message routing works inside consumers.

---

## B3. WebSocket Routing (routing.py + asgi.py)

### Simple Explanation
Just like `urls.py` maps HTTP URLs to views, `routing.py` maps WebSocket URLs to consumers. We have 3 WebSocket endpoints — one for notifications, one for camera streaming, and one for the admin camera grid.

### Technical Explanation

```python
# routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'ws/camera/stream/$', consumers.CameraStreamConsumer.as_asgi()),
    re_path(r'ws/camera/admin-grid/$', consumers.AdminGridConsumer.as_asgi()),
]
```

#### Endpoint Map

| WebSocket URL | Consumer | Who Connects | Data Direction |
|--------------|----------|--------------|----------------|
| `ws/notifications/` | NotificationConsumer | Admin + Teachers | Bidirectional JSON |
| `ws/camera/stream/` | CameraStreamConsumer | Teachers only | Binary (frames) ↔ Binary (annotated) + JSON |
| `ws/camera/admin-grid/` | AdminGridConsumer | Admin only | Server → Client (binary frames) |

#### Connection Flow

```
Browser: new WebSocket('ws://host:8000/ws/notifications/')
    │
    ├── HTTP Upgrade request (includes session cookie)
    │
    ▼
Daphne ASGI Server
    │
    ├── ProtocolTypeRouter → "websocket"
    │
    ├── AuthMiddlewareStack → extracts user from session cookie
    │
    ├── URLRouter → matches /ws/notifications/ → NotificationConsumer
    │
    └── NotificationConsumer.connect() called
         ├── self.scope['user'] = authenticated user
         ├── Joins groups (notifications_global, user_X, admin_notifications)
         └── self.accept() → handshake complete, bidirectional channel open
```

---

## B4. NotificationConsumer — The Command Center

### Simple Explanation
This is the central communication hub. When the admin clicks "Start Camera" for a teacher, the command goes through this consumer. When a teacher accepts, the response comes back through here. It also tracks which teachers are online/offline and broadcasts malpractice alerts.

### Technical Explanation

#### Class Structure

```python
class NotificationConsumer(AsyncJsonWebsocketConsumer):
    # Inherits from AsyncJsonWebsocketConsumer:
    # - Automatically serializes/deserializes JSON
    # - send_json() and receive_json() instead of raw text
    # - Async methods (non-blocking)
```

#### Connection Setup (connect method)

```python
async def connect(self):
    self.user = self.scope['user']
    if self.user.is_anonymous:
        await self.close()         # Reject unauthenticated
        return

    # 1. Join global notification group
    self.notification_group = 'notifications_global'
    await self.channel_layer.group_add(self.notification_group, self.channel_name)

    # 2. Join personal group (for targeted messages)
    self.user_group = f'user_{self.user.id}'
    await self.channel_layer.group_add(self.user_group, self.channel_name)

    # 3. Admin-specific group + presence tracking
    if self.user.is_superuser:
        self.admin_group = 'admin_notifications'
        await self.channel_layer.group_add(self.admin_group, self.channel_name)
        CONNECTED_ADMINS.add(self.channel_name)
        # Cancel disconnect timer if admin reconnects
        if _admin_disconnect_timer:
            _admin_disconnect_timer.cancel()

    await self.accept()

    # 4. Mark teacher online + broadcast status
    if not self.user.is_superuser:
        await self.set_teacher_online(True)
        await self.broadcast_teacher_status()

    # 5. Send initial state snapshot
    await self.send_initial_state()
```

#### Message Types Handled (receive_json)

| Incoming `type` | Sender | What It Does |
|-----------------|--------|-------------|
| `camera_request` | Admin | Create CameraSession (DB) → notify specific teacher |
| `camera_request_all` | Admin | Loop all online teachers → create sessions → notify each |
| `camera_response` | Teacher | Update session to active/denied → notify admin |
| `camera_stop` | Admin | Stop specific camera → update DB → notify teacher |
| `camera_stop_all` | Admin | Stop all active cameras → notify all teachers |
| `camera_stop_by_teacher` | Teacher | Stop own camera → notify admin |
| `camera_error` | Teacher | Camera hardware/permission error → notify admin with reason |
| `get_teachers` | Admin | Return current teacher list |
| `get_active_sessions` | Admin | Return active camera sessions |

#### Channel Layer Event Handlers

These methods are called when **other consumers** use `group_send`. The naming convention is: `type: 'session.update'` → method `session_update()`:

```python
async def session_update(self, event):
    """Called by group_send({'type': 'session.update', 'session': ...})"""
    await self.send_json({
        'type': 'session_update',
        'session': event['session'],
    })
```

Full list of event handlers:
- `camera_request` → Forward camera request to teacher
- `camera_stop` → Forward stop command to teacher
- `admin_disconnected` → Warn teacher that admin left
- `session_update` → Update admin with session status change
- `bulk_session_update` → Update admin with multiple session changes
- `teacher_status` → Broadcast teacher online/offline to admin
- `malpractice_alert` → Real-time detection alert to admin
- `review_notification` → Review completion to teacher
- `camera_stopped_by_teacher` → Inform admin of teacher-initiated stop
- `camera_error_notification` → Camera error details to admin

#### Database Operations Pattern

All database calls use `@database_sync_to_async` decorator because Django's ORM is synchronous, but our consumers are async:

```python
@database_sync_to_async
def create_camera_session(self, teacher_id):
    """Runs in a thread pool, not blocking the event loop."""
    teacher = User.objects.get(id=teacher_id)
    profile = TeacherProfile.objects.get(user=teacher)
    
    # Close any existing active sessions
    CameraSession.objects.filter(
        teacher=teacher, status__in=['requested', 'active']
    ).update(status='stopped', stopped_at=timezone.now())
    
    session = CameraSession.objects.create(
        teacher=teacher,
        lecture_hall=profile.lecture_hall,
        status='requested',
    )
    return {  # Return serializable dict (not ORM object)
        'id': session.id,
        'teacher_id': teacher.id,
        'teacher_name': f'{teacher.first_name} {teacher.last_name}'.strip(),
        'lecture_hall': str(session.lecture_hall),
        ...
    }
```

**Why return dicts, not ORM objects?** ORM objects can't cross async boundaries safely (lazy attributes, DB connections). We extract everything into plain dicts before passing to async code.

#### Camera Request Flow (Complete Sequence)

```
Admin clicks "Start Camera" for Teacher #5
     │
     ▼
Admin Browser → ws.send({type: 'camera_request', teacher_id: 5})
     │
     ▼
NotificationConsumer.receive_json() → handle_camera_request()
     │
     ├── 1. create_camera_session(5) → DB: CameraSession(teacher=5, status='requested')
     │
     ├── 2. group_send('user_5', {type: 'camera.request', session_id: 42})
     │       → Delivered to Teacher #5's NotificationConsumer
     │       → Teacher's browser shows "Admin requests camera" modal
     │
     └── 3. group_send('admin_notifications', {type: 'session.update', session: {...}})
             → Admin's UI updates: Teacher #5 status → "Requested"

Teacher clicks "Accept"
     │
     ▼
Teacher Browser → ws.send({type: 'camera_response', session_id: 42, accepted: true})
     │
     ▼
NotificationConsumer.receive_json() → handle_camera_response()
     │
     ├── 1. update_camera_session(42, True) → DB: status='active', started_at=now
     │
     ├── 2. group_send('admin_notifications', {type: 'session.update', ...})
     │       → Admin sees: Teacher #5 status → "Active"
     │
     └── 3. send_json({type: 'camera_approved', session_id: 42})
             → Teacher opens second WebSocket: /ws/camera/stream/
             → Camera starts streaming frames
```

---

## B5. CameraStreamConsumer — Live ML Pipeline Bridge

### Simple Explanation
When a teacher's camera is active, this consumer receives raw webcam frames (as binary JPEG data), sends them to the ML pipeline for processing, sends annotated frames back to the teacher, forwards raw frames to the admin grid, and manages video recording for evidence.

### Technical Explanation

#### Connection Requirements

```python
async def connect(self):
    self.user = self.scope['user']
    # Must be: (1) authenticated, (2) not admin, (3) have active session
    if self.user.is_anonymous or self.user.is_superuser:
        await self.close()
        return
    
    self.session = await self.get_active_session()
    if not self.session:
        await self.close()  # No active CameraSession → reject
        return
```

Teachers can only connect if they have an `active` CameraSession in the database (created by the admin's camera request flow).

#### Global State Dictionaries

```python
# Tracks all active camera streams
ACTIVE_STREAMS = {}  # {teacher_id: {'channel_name': ..., 'hall_id': ...}}

# Direct send functions for admin grid (bypass channel layer)
ADMIN_GRID_SENDERS = {}  # {channel_name: send_func}
```

These module-level dictionaries provide O(1) lookup for stream management without database queries.

#### Frame Processing Flow

```python
async def process_frame(self, frame_bytes):
    """Called for EVERY received frame from teacher webcam."""
    self.frame_count += 1
    
    # 1. ALWAYS store latest frame (for ML — frame dropping)
    self._latest_frame = frame_bytes
    
    # 2. ALWAYS buffer frame (for video recording — no drops)
    if self.frame_processor:
        asyncio.ensure_future(
            loop.run_in_executor(ml_executor, self.frame_processor.buffer_frame, frame_bytes)
        )
    
    # 3. Forward to admin grid (every 2nd frame → ~10 FPS)
    self.admin_frame_count += 1
    if self.admin_frame_count % 2 == 0 and ADMIN_GRID_SENDERS:
        asyncio.ensure_future(self._forward_to_admin_binary(frame_bytes))
    
    # 4. ML processing (only if not already busy)
    if self.detection_active and not self._ml_busy and self.frame_processor:
        self._ml_busy = True
        asyncio.ensure_future(self._run_ml_processing())
```

#### The Frame-Dropping Pattern

```
Frame 1 arrives ──► _latest_frame = Frame 1, ML not busy → start ML
Frame 2 arrives ──► _latest_frame = Frame 2, ML busy → skip ML (frame dropped)
Frame 3 arrives ──► _latest_frame = Frame 3, ML busy → skip ML (frame dropped)
ML finishes    ──► _ml_busy = False
Frame 4 arrives ──► _latest_frame = Frame 4, ML not busy → start ML on Frame 4
                    (Frame 4 is processed, Frames 2-3 were dropped for ML)
```

**Critical:** Frames are only dropped for ML processing. They are STILL:
- Buffered for video recording (every frame)
- Forwarded to admin grid (every 2nd frame)

This means evidence clips have full frame rate, but ML only processes what it can handle.

#### Thread Pool Executor

```python
ml_executor = ThreadPoolExecutor(max_workers=3)
```

ML inference runs in a thread pool (not the async event loop) to prevent blocking other WebSocket connections. `max_workers=3` limits concurrent ML processing to 3 streams — prevents GPU memory exhaustion.

```python
async def _run_ml_processing(self):
    try:
        frame_bytes = self._latest_frame
        loop = asyncio.get_running_loop()
        
        # Run ML in thread pool (non-blocking)
        result = await loop.run_in_executor(
            ml_executor,
            self.frame_processor.process_frame,
            frame_bytes
        )
        
        if result:
            # Send annotated frame back to teacher (binary)
            await self.send(bytes_data=result['annotated_frame'])
            
            # Handle completed detections (saved video clips)
            if result.get('detections'):
                for detection in result['detections']:
                    saved = await self.save_detection(detection)
                    if saved:
                        # Notify teacher with JSON
                        await self.send(text_data=json.dumps({
                            'type': 'detection',
                            'action': detection.get('action'),
                            'probability': detection.get('probability'),
                        }))
                        # Notify admin via channel layer
                        await self.channel_layer.group_send(
                            'admin_notifications',
                            {'type': 'malpractice.alert', 'detection': saved}
                        )
    finally:
        self._ml_busy = False
```

#### Disconnect Handling — No Lost Evidence

```python
async def disconnect(self, close_code):
    if hasattr(self, 'teacher_id'):
        # Finalize ALL active recordings (save partial clips)
        if self.frame_processor:
            completed = await loop.run_in_executor(
                ml_executor, self.frame_processor.finalize_all_recordings
            )
            for detection in completed:
                saved = await self.save_detection(detection)
                # Notify admin of saved detection
        
        # Remove from active streams
        ACTIVE_STREAMS.pop(self.teacher_id, None)
        
        # Notify admin grid that stream ended
        await self.channel_layer.group_send(
            'admin_camera_grid',
            {'type': 'stream.ended', 'teacher_id': self.teacher_id}
        )
```

If the teacher closes their browser, disconnects WiFi, or stops the camera, `disconnect()` ensures any in-progress recordings are saved to database and the admin is notified.

---

## B6. AdminGridConsumer — High-Performance Frame Delivery

### Simple Explanation
The admin sees a grid of all camera feeds on one page. This consumer receives raw frames from all active teachers and displays them. To minimize latency, it bypasses the channel layer entirely — frames are sent directly to the admin's WebSocket using a stored reference to the `send()` function.

### Technical Explanation

#### Why Bypass the Channel Layer?

```python
# Normal Channels pattern (SLOW for high-frequency data):
await self.channel_layer.group_send('admin_camera_grid', {
    'type': 'camera.frame',
    'frame': base64_encoded_frame,  # ~100KB base64 string
})
# Problem: InMemoryChannelLayer serializes, queues, deserializes
# At 10 FPS × 5 teachers = 50 messages/sec → channel layer becomes bottleneck

# Our pattern (FAST):
ADMIN_GRID_SENDERS[self.channel_name] = self.send  # Store send function
# In CameraStreamConsumer:
for send_func in ADMIN_GRID_SENDERS.values():
    await send_func(bytes_data=binary_data)  # Direct call, zero overhead
```

#### The ADMIN_GRID_SENDERS Pattern

```python
class AdminGridConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Only admin
        if not self.user.is_superuser:
            await self.close()
            return
        
        await self.accept()
        
        # Register for DIRECT frame sends
        ADMIN_GRID_SENDERS[self.channel_name] = self.send
        
        # Send list of currently streaming teachers
        await self.send(text_data=json.dumps({
            'type': 'active_streams',
            'streams': [
                {'teacher_id': tid, 'teacher_name': info['teacher_name'], ...}
                for tid, info in ACTIVE_STREAMS.items()
            ]
        }))
    
    async def disconnect(self, close_code):
        ADMIN_GRID_SENDERS.pop(self.channel_name, None)
```

The channel layer is still used for `stream_started` and `stream_ended` events (low frequency). Only high-frequency frame data uses the direct send pattern.

#### Dead Channel Cleanup

```python
# In CameraStreamConsumer._forward_to_admin_binary():
dead_channels = []
for ch_name, send_func in list(ADMIN_GRID_SENDERS.items()):
    try:
        await send_func(bytes_data=binary_data)
    except Exception:
        dead_channels.append(ch_name)  # Connection died
for ch in dead_channels:
    ADMIN_GRID_SENDERS.pop(ch, None)  # Remove dead entries
```

If an admin closes their browser without proper WebSocket close, the `send()` call will fail. We catch the exception and remove the dead entry to prevent repeated failures.

---

## B7. Binary WebSocket Protocol Design

### Simple Explanation
Instead of encoding video frames as base64 text (which is 33% larger), we send raw binary data through the WebSocket. Each binary message is prefixed with 4 bytes that identify which teacher the frame belongs to, so the admin's browser knows which camera grid cell to update.

### Technical Explanation

#### Binary Frame Protocol

```
┌──────────────────┬───────────────────────────┐
│ 4 bytes          │ Variable length           │
│ Teacher ID       │ Raw JPEG image data       │
│ (big-endian)     │                           │
└──────────────────┴───────────────────────────┘
```

#### Encoding (Python — Server Side)

```python
async def _forward_to_admin_binary(self, frame_bytes):
    header = self.teacher_id.to_bytes(4, 'big')  # 4 bytes, big-endian
    binary_data = header + frame_bytes            # Concatenate
    for send_func in ADMIN_GRID_SENDERS.values():
        await send_func(bytes_data=binary_data)   # Send as binary WS message
```

#### Decoding (JavaScript — Client Side)

```javascript
socket.onmessage = function(event) {
    if (event.data instanceof Blob) {
        var reader = new FileReader();
        reader.onload = function() {
            var buf = new Uint8Array(reader.result);
            // Extract 4-byte teacher ID (big-endian)
            var teacherId = (buf[0] << 24) | (buf[1] << 16) | (buf[2] << 8) | buf[3];
            // Extract JPEG data (everything after first 4 bytes)
            var jpegBlob = new Blob([buf.slice(4)], {type: 'image/jpeg'});
            var url = URL.createObjectURL(jpegBlob);
            // Display in correct camera cell
            updateCameraFrame(teacherId, url);
        };
        reader.readAsArrayBuffer(event.data);
    }
};
```

#### Why Binary Instead of Base64+JSON?

| Method | Frame Size (720p JPEG) | Overhead | CPU Cost |
|--------|----------------------|----------|----------|
| Base64 in JSON | ~65KB → ~87KB | +33% size | base64 encode/decode |
| Raw Binary | ~65KB → ~65KB + 4 bytes | +0.006% | Zero encoding |

At 10 FPS × 5 teachers = 50 frames/sec, this saves:
- **~1.1 MB/sec** bandwidth
- Eliminates base64 CPU overhead on both server and client
- No JSON parsing for frame data

---

## B8. Admin Heartbeat & Presence System

### Simple Explanation
If the admin closes their browser while teachers are streaming, nobody is watching the cameras. We detect this and warn teachers after 60 seconds. If the admin comes back within 60 seconds, the timer cancels.

### Technical Explanation

```python
# Module-level state
CONNECTED_ADMINS = set()  # Set of admin channel_names
_admin_disconnect_timer = None
ADMIN_TIMEOUT_SECONDS = 60

# On admin connect:
async def connect(self):
    if self.user.is_superuser:
        CONNECTED_ADMINS.add(self.channel_name)
        if _admin_disconnect_timer:
            _admin_disconnect_timer.cancel()  # Cancel pending warning

# On admin disconnect:
async def disconnect(self, close_code):
    if self.user.is_superuser:
        CONNECTED_ADMINS.discard(self.channel_name)
        if not CONNECTED_ADMINS and ACTIVE_STREAMS:
            # LAST admin left while cameras are active
            loop = asyncio.get_running_loop()
            _admin_disconnect_timer = loop.call_later(
                60,  # 60 second grace period
                lambda: asyncio.ensure_future(self._admin_timeout_handler())
            )

# Timeout handler:
async def _admin_timeout_handler(self):
    if CONNECTED_ADMINS:
        return  # Admin reconnected in time
    
    # Warn all active teachers
    for teacher_id in ACTIVE_STREAMS:
        await self.channel_layer.group_send(
            f'user_{teacher_id}',
            {
                'type': 'admin.disconnected',
                'message': 'Admin has been disconnected for over 60 seconds. '
                           'Your camera is still streaming but no one is monitoring.',
            }
        )
```

#### Why a Grace Period?
Admins might refresh their page, temporarily lose WiFi, or switch tabs. An immediate warning would cause unnecessary panic. 60 seconds is long enough for a page refresh but short enough for genuine disconnects.

#### Multiple Admin Support
`CONNECTED_ADMINS` is a **set**, not a single flag. Multiple admins can monitor simultaneously. The timer only starts when the **last** admin disconnects AND there are active streams.

---

## B9. Views — Authentication & User Management

### Simple Explanation
We handle user registration (teachers only — admins are created via Django admin panel), login with session-based auth, profile management with photo upload, and password changes. All auth views are standard Django patterns with `@login_required` protection.

### Technical Explanation

#### Teacher Registration (teacher_register)

```python
def teacher_register(request):
    if request.method == "POST":
        # Extract form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        username = request.POST.get('username')
        password = request.POST.get('password')
        phone = request.POST.get('phone')
        profile_picture = request.FILES.get('profile_picture')
        
        # Create Django User
        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name
        )
        
        # Create linked TeacherProfile
        profile = TeacherProfile(user=user, phone=phone)
        if profile_picture:
            profile.profile_picture = profile_picture
        profile.save()
        
        return redirect('login')
```

**`User.objects.create_user()`** handles password hashing automatically (PBKDF2-SHA256 by default in Django).

#### Login Flow (addlogin)

```python
def addlogin(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            auth_login(request, user)  # Creates session
            return redirect('index')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
```

**`authenticate()`** checks credentials against the database. **`auth_login()`** creates a session and sets the session cookie. This cookie is then used by `AuthMiddlewareStack` for WebSocket authentication.

#### Profile Editing (edit_profile)

Uses Django's ModelForm system with two linked forms:

```python
user_form = EditProfileForm(instance=user)          # User model: first_name, last_name, email
profile_form = TeacherProfileForm(instance=profile)  # TeacherProfile: phone, profile_picture
```

Both forms validate and save independently. The `profile_picture` field uses `ImageField` with `upload_to='profile_pics/'` — Django handles file upload, renaming, and storage automatically.

#### Password Change (change_password)

```python
form = PasswordChangeForm(user=request.user, data=request.POST)
if form.is_valid():
    user = form.save()  # Hashes new password + saves
    update_session_auth_hash(request, user)  # CRITICAL: prevents logout
```

**`update_session_auth_hash()`** is critical — without it, changing your password invalidates your session hash and you're immediately logged out. This re-creates the session with the new password hash.

#### Decorators Used

| Decorator | What It Does |
|-----------|-------------|
| `@login_required` | Redirects to `/login/` if not authenticated |
| `@user_passes_test(is_admin)` | Returns 403 if `user.is_superuser` is False |
| `@staff_member_required` | Similar to `@user_passes_test` but for `is_staff` |
| `@require_POST` | Returns 405 if method is not POST |

---

## B10. Views — Malpractice Log (Complex Filtering)

### Simple Explanation
The malpractice log page shows all detected malpractice events with 10+ filter options. Admins see all logs and can filter by review status. Teachers only see logs that the admin has reviewed and approved as malpractice for their assigned lecture hall.

### Technical Explanation

#### Role-Based Base Queryset

```python
if request.user.is_superuser:
    logs = MalpraticeDetection.objects.all()
    # Admin filters: reviewed / not_reviewed / all
    if review_filter == 'reviewed':
        logs = logs.filter(verified=True)
    elif review_filter == 'not_reviewed':
        logs = logs.filter(verified=False)
else:
    # Teacher: ONLY sees reviewed + approved + visible logs for their hall
    assigned_halls = LectureHall.objects.filter(assigned_teacher=request.user)
    logs = MalpraticeDetection.objects.filter(
        lecture_hall__in=assigned_halls,
        verified=True,           # Admin has reviewed it
        is_malpractice=True,     # Admin confirmed it's malpractice
        teacher_visible=True     # Admin has released it to teacher
    )
```

This three-layer visibility filter (`verified=True, is_malpractice=True, teacher_visible=True`) ensures teachers never see unreviewed or dismissed logs.

#### 10+ Filter Parameters

| Filter | Parameter | Query |
|--------|-----------|-------|
| Date | `date=2025-01-15` | `logs.filter(date=date_filter)` |
| Time | `time=FN` or `AN` | Forenoon: `time < 12:00`, Afternoon: `time >= 12:00` |
| Malpractice Type | `malpractice_type=Leaning` | `logs.filter(malpractice=malpractice_filter)` |
| Building | `building=MAIN` | `logs.filter(lecture_hall__building=building_filter)` |
| Hall Search | `q=LH1` | `logs.filter(lecture_hall__hall_name__icontains=query)` |
| Faculty | `faculty=5` | `logs.filter(lecture_hall__assigned_teacher__id=faculty_filter)` |
| Assignment | `assigned=assigned` | `lecture_hall__assigned_teacher__isnull=False` |
| Review Status | `review=reviewed` | `logs.filter(verified=True)` |
| Probability | `probability=above_50` | `logs.filter(probability_score__gte=50)` |
| Source | `source=live` | `logs.filter(source_type='live')` |
| Sort | `sort=prob_high` | `logs.order_by('-probability_score')` |

#### Retroactive Probability Scoring

```python
def ensure_probability_scores(logs_queryset):
    """Fill in scores for logs that predate the scoring system."""
    logs_without_score = logs_queryset.filter(probability_score__isnull=True)
    updated_logs = []
    for log in logs_without_score:
        log.probability_score = calculate_retroactive_probability(log)
        updated_logs.append(log)
    if updated_logs:
        MalpraticeDetection.objects.bulk_update(updated_logs, ['probability_score'], batch_size=200)
```

Older malpractice logs were created before the probability scoring system. This function retroactively computes scores using a simplified 2-factor model: 60% video clip duration + 40% type prior. Uses `bulk_update()` with batch sizing for efficiency — a single SQL UPDATE per batch instead of N individual saves.

```python
# Retroactive formula (simplified):
probability = (duration_score * 0.60 + type_score * 0.40) * 100
```

Duration is measured by opening the evidence video with OpenCV and calculating `total_frames / fps`.

#### New Log Alert System

```python
record_count = logs.count()
if "record_count" in request.session:
    if request.session["record_count"] < record_count:
        alert = True  # New logs since last visit
        request.session["record_count"] = record_count
```

Session-based tracking — if more logs exist than the last time this user visited the page, show an alert banner.

---

## B11. Views — Review System & Notifications

### Simple Explanation
The admin reviews each malpractice log and marks it as "Yes (malpractice)" or "No (not malpractice)". When confirmed as malpractice, an email and SMS are sent to the assigned teacher. The admin can also complete a review session (batch review) which sends a summary email.

### Technical Explanation

#### Single Log Review (review_malpractice)

```python
@login_required
@user_passes_test(is_admin)
@require_POST
def review_malpractice(request):
    data = json.loads(request.body)
    proof_filename = data.get('proof')
    decision = data.get('decision')  # 'yes' or 'no'
    
    log = MalpraticeDetection.objects.get(proof=proof_filename)
    log.verified = True
    log.is_malpractice = (decision == 'yes')
    if log.is_malpractice:
        log.teacher_visible = True  # Release to teacher
    log.save()
    
    # If malpractice confirmed → notify teacher
    if log.is_malpractice and log.lecture_hall.assigned_teacher:
        Thread(target=send_notifications_background, args=(log.id,)).start()
```

#### Background Notification Sending

```python
def send_notifications_background(log_id):
    """Runs in a daemon thread — doesn't block the HTTP response."""
    log = MalpraticeDetection.objects.get(id=log_id)
    teacher_user = log.lecture_hall.assigned_teacher
    
    # 1. Send Email
    send_mail(subject, message_body, settings.EMAIL_HOST_USER, 
              [teacher_user.email], fail_silently=False)
    
    # 2. Send SMS (via Twilio)
    teacher_profile = teacher_user.teacherprofile
    if teacher_profile.phone:
        send_sms_notification(f"+91{teacher_profile.phone}", sms_body)
```

**Why daemon thread?** The HTTP response should return immediately (< 200ms). Email might take 2-5 seconds (SMTP handshake) and SMS another 1-2 seconds (Twilio API call). Running in a daemon thread means these happen in the background after the admin sees "Success."

#### Batch Review (complete_review_session)

```python
def complete_review_session(request):
    data = json.loads(request.body)
    teacher_id = data.get('teacher_id')
    hall_id = data.get('hall_id')
    
    # 1. Mark all reviewed logs as visible to teacher
    reviewed_logs.filter(is_malpractice=True).update(teacher_visible=True)
    
    # 2. Create ReviewSession record
    review_session = ReviewSession.objects.create(
        admin_user=request.user,
        lecture_hall=hall,
        teacher=teacher,
        logs_reviewed=total_reviewed,
        logs_flagged=flagged_count,
    )
    
    # 3. Send summary email + SMS in background thread
    Thread(target=send_review_email, args=(review_session.id,)).start()
```

#### AI Bulk Action (ai_bulk_action)

Two automated review actions based on probability scores:

```python
if action == 'approve_high':
    # All logs with probability >= 50% → confirmed malpractice
    high_prob_logs = list(unreviewed_logs.filter(probability_score__gte=50))
    for log in high_prob_logs:
        log.verified = True
        log.is_malpractice = True
        log.teacher_visible = True
    MalpraticeDetection.objects.bulk_update(
        high_prob_logs, ['verified', 'is_malpractice', 'teacher_visible'], batch_size=200
    )
    # Send a single bounded notification thread

elif action == 'dismiss_low':
    # All logs with probability < 50% → dismissed
    low_prob_logs = unreviewed_logs.filter(probability_score__lt=50)
    low_prob_logs.update(verified=True, is_malpractice=False)
```

---

## B12. Views — Video Serving with H.264 + HTTP Range

### Simple Explanation
Evidence videos are recorded by the ML pipeline in mp4v format (.avi), which browsers can't play. This view converts them to H.264 (.mp4) using a 3-strategy fallback, caches the converted file, and serves it with HTTP Range support so users can seek/scrub through the video.

### Technical Explanation

#### Conversion Strategy Chain

```python
def serve_video(request):
    filename = os.path.basename(request.GET.get('file', ''))  # Sanitized
    video_path = os.path.join(settings.MEDIA_ROOT, filename)
    
    cache_dir = os.path.join(settings.MEDIA_ROOT, '_h264_cache')
    cached_path = os.path.join(cache_dir, filename)
    
    # Check cache first
    if os.path.exists(cached_path):
        serve_path = cached_path
    else:
        # Strategy 1: System ffmpeg
        # Strategy 2: imageio-ffmpeg (bundled)
        # Strategy 3: OpenCV H.264 codecs (avc1, H264, X264, h264)
        # Strategy 4: Serve original (last resort)
```

#### HTTP Range Request Support

Range requests allow the browser's `<video>` player to seek to any position without downloading the entire file:

```python
range_header = request.META.get('HTTP_RANGE', '')  # "bytes=5000-9999"

if range_header:
    range_start, range_end = parse_range(range_header)
    
    f = open(serve_path, 'rb')
    f.seek(range_start)
    data = f.read(content_length)
    f.close()
    
    response = HttpResponse(data, content_type='video/mp4', status=206)  # 206 Partial Content
    response['Content-Range'] = f'bytes {range_start}-{range_end}/{file_size}'
    response['Content-Length'] = content_length
    response['Accept-Ranges'] = 'bytes'
else:
    # Full file response
    response = FileResponse(open(serve_path, 'rb'), content_type='video/mp4')
    response['Accept-Ranges'] = 'bytes'
```

#### Why HTTP Range Matters

Without Range support, clicking the middle of a video timeline would require downloading everything from the start. With Range support:
1. Browser sends `Range: bytes=500000-` (from 500KB onward)
2. Server responds with `206 Partial Content` and just that byte range
3. Video starts playing from the seeked position immediately

---

## B13. Views — Video Upload & MJPEG Streaming

### Simple Explanation
Teachers can upload recorded exam videos for offline ML analysis. The upload is saved to disk, then a background thread runs the ML pipeline on it while the browser watches the processing live via an MJPEG stream (like a live video feed of the AI analyzing the video).

### Technical Explanation

#### Upload Flow (process_video)

```python
@login_required
def process_video(request):
    if request.method == 'POST' and request.FILES.get('video'):
        video_file = request.FILES['video']
        
        # 1. Validate file type
        allowed_types = ['video/mp4', 'video/avi', 'video/x-msvideo', ...]
        if video_file.content_type not in allowed_types:
            return JsonResponse({'status': 'error', 'message': 'Invalid file type'})
        
        # 2. Validate file size (500MB max)
        if video_file.size > 500 * 1024 * 1024:
            return JsonResponse({'status': 'error', 'message': 'File too large'})
        
        # 3. Save to disk
        session_id = f"{timestamp}_{request.user.id}"
        filepath = os.path.join(upload_dir, f"{timestamp}_{video_file.name}")
        with open(filepath, 'wb+') as destination:
            for chunk in video_file.chunks():
                destination.write(chunk)
        
        # 4. Store session in memory
        VIDEO_SESSIONS[session_id] = {
            'filepath': filepath,
            'lecture_hall_id': lecture_hall_id,
            'status': 'ready',
            'user_id': request.user.id
        }
        
        return JsonResponse({'status': 'success', 'session_id': session_id})
```

#### MJPEG Streaming (stream_video_processing)

```python
@login_required
def stream_video_processing(request, session_id):
    # Verify session ownership
    session = VIDEO_SESSIONS[session_id]
    if session['user_id'] != request.user.id:
        return HttpResponse('Unauthorized', status=403)
    
    async def async_generate():
        """Async generator bridging sync ML to ASGI streaming."""
        frame_queue = asyncio.Queue(maxsize=30)
        
        def _run_sync_processing():
            """Background thread: runs ML and pushes frames to queue."""
            for frame_data in stream_process_video(filepath, hall_id):
                future = asyncio.run_coroutine_threadsafe(
                    frame_queue.put(frame_data), loop
                )
                future.result(timeout=30)
            # Signal completion
            asyncio.run_coroutine_threadsafe(frame_queue.put(None), loop)
        
        loop.run_in_executor(pool, _run_sync_processing)
        
        while True:
            frame_data = await frame_queue.get()
            if frame_data is None:
                break
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' 
                   + frame_data + b'\r\n')
    
    return StreamingHttpResponse(
        async_generate(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )
```

#### The Sync-to-Async Bridge Pattern

```
Background Thread                    Async Event Loop
(sync ML processing)                 (StreamingHttpResponse)
         │                                    │
         │  frame_data                        │
         ├───── asyncio.Queue(30) ──────────►│ yield MJPEG frame
         │  frame_data                        │
         ├───── asyncio.Queue(30) ──────────►│ yield MJPEG frame
         │  None (done)                       │
         └───── asyncio.Queue(30) ──────────►│ break (stream ends)
```

**Why `asyncio.run_coroutine_threadsafe()`?** The background thread can't use `await` (it's sync). This function safely schedules an async coroutine (queue.put) on the event loop from a sync thread.

**Why `Queue(maxsize=30)`?** Backpressure — if the browser can't consume frames fast enough, the producer blocks rather than accumulating unlimited memory.

#### Stats Collection (get_processing_stats)

After processing completes, the browser polls for results:

```python
def get_processing_stats(request, session_id):
    stats = VIDEO_SESSIONS[session_id].get('stats', {})
    return JsonResponse({
        'status': stats.get('status'),
        'duration': stats.get('duration'),
        'frames_yielded': stats.get('frames_yielded'),
        'detections': stats.get('detections'),
        'detection_types': stats.get('detection_types'),
    })
```

Sessions auto-cleanup after 5 minutes:
```python
if stats.get('status') == 'completed':
    if time.time() - stats.get('end_time', 0) > 300:
        VIDEO_SESSIONS.pop(session_id, None)
```

---

## B14. Views — Lecture Hall & Teacher Management

### Simple Explanation
Admin pages for managing the physical infrastructure — creating lecture halls, assigning teachers to halls, viewing teacher lists. A teacher must be assigned to a lecture hall before they can use the camera system.

### Technical Explanation

#### manage_lecture_halls — CRUD Operations

Handles 4 POST actions via form submission:

```python
if 'add_hall' in request.POST:
    # Create new hall (check for duplicates)
    if LectureHall.objects.filter(hall_name=hall_name, building=building).exists():
        error_message = f"Already exists!"
    else:
        LectureHall.objects.create(hall_name=hall_name, building=building)

elif 'map_teacher' in request.POST:
    # Assign teacher to hall (1:1 mapping)
    # Step 1: Clear teacher's previous hall assignment
    old_hall = LectureHall.objects.filter(assigned_teacher=teacher).first()
    if old_hall:
        old_hall.assigned_teacher = None
        old_hall.save()
        TeacherProfile.objects.filter(user=teacher).update(lecture_hall=None)
    # Step 2: Clear hall's previous teacher
    if hall.assigned_teacher:
        TeacherProfile.objects.filter(user=hall.assigned_teacher).update(lecture_hall=None)
    # Step 3: Create new assignment (both directions)
    hall.assigned_teacher = teacher
    hall.save()
    TeacherProfile.objects.filter(user=teacher).update(lecture_hall=hall)

elif 'unmap_teacher' in request.POST:
    # Remove assignment
    
elif 'delete_hall' in request.POST:
    # CASCADE delete: clear teacher link, delete all malpractice logs,
    # review sessions, camera sessions, then the hall itself
    MalpraticeDetection.objects.filter(lecture_hall=hall).delete()
    ReviewSession.objects.filter(lecture_hall=hall).delete()
    CameraSession.objects.filter(lecture_hall=hall).delete()
    hall.delete()
```

**Why manual cascade?** Django's `on_delete=SET_NULL` on the LectureHall→MalpraticeDetection FK doesn't delete the logs — it nullifies the FK. But we want full cleanup, so we explicitly delete related records.

#### Teacher-Hall Assignment Dual-Write

When assigning a teacher to a hall, we update BOTH:
1. `LectureHall.assigned_teacher` (FK on LectureHall)
2. `TeacherProfile.lecture_hall` (FK on TeacherProfile)

This redundancy ensures both `hall.assigned_teacher` and `teacher.teacherprofile.lecture_hall` are consistent, allowing queries from either direction.

#### view_teachers — Read-Only Listing

```python
teachers = User.objects.filter(is_superuser=False).select_related('lecturehall')
# Filters: assigned/unassigned, building, search (name/email/username)
if query:
    teachers = teachers.filter(
        Q(username__icontains=query) | Q(first_name__icontains=query) | 
        Q(last_name__icontains=query) | Q(email__icontains=query)
    )
```

**`select_related('lecturehall')`** uses SQL JOIN to fetch the related LectureHall in a single query instead of N+1 queries.

---

## B15. Views — Camera Script Triggering (Legacy)

### Simple Explanation
Before the WebSocket-based camera system, ML scripts were launched directly on the server or remote machines via SSH. This is the legacy triggering system — the admin clicks "Start Cameras" and scripts are launched via subprocess or SSH.

### Technical Explanation

```python
@login_required
@user_passes_test(lambda u: u.is_superuser)
def trigger_camera_scripts(request):
    client_configs = [
        {
            "name": "Top Corner - Host(Allen 2)",
            "script_path": "e:\\witcher\\...\\ML\\front.py",
            "mode": "local"
        },
        # Remote clients configured similarly
    ]
    
    for config in client_configs:
        threading.Thread(target=run_on_client, args=(config,)).start()
```

#### Local vs Remote Execution

- **Local**: `subprocess.Popen(['python', script_name], cwd=script_dir)` — runs ML script as a child process
- **Remote**: SSH via Paramiko → open PTY → execute script → store SSH channel for later Ctrl+C

#### Stopping Scripts

```python
def stop_camera_scripts(request):
    for key in list(RUNNING_SCRIPTS.keys()):
        handle = RUNNING_SCRIPTS[key]
        if handle["mode"] == "remote":
            handle["channel"].send("\x03")  # Send Ctrl+C
            handle["ssh"].close()
        elif handle["mode"] == "local":
            handle["process"].terminate()
        RUNNING_SCRIPTS.pop(key)
```

> **Note**: This is the legacy approach. The current production system uses the WebSocket-based camera flow (NotificationConsumer + CameraStreamConsumer) which is more reliable and doesn't require SSH.

---

## B16. Utility Layer (utils.py) — SMS, SSH, Script Runner

### Simple Explanation
Helper functions for external communication: sending SMS via Twilio, executing scripts on remote machines via SSH, and running local ML scripts safely.

### Technical Explanation

#### Twilio SMS Integration

```python
def send_sms_notification(to_phone, message_body):
    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )
    client.messages.create(
        body=message_body,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=to_phone  # E.164 format: +919876543210
    )
```

**E.164 format**: International phone format with country code. All Indian numbers are prefixed with `+91`.

#### SSH Remote Execution (ssh_run_script)

```python
def ssh_run_script(ip, username, password, script_path, use_venv=True, venv_path=None):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())  # Security: warns on unknown hosts
    ssh.connect(ip, username=username, password=password)
    
    # Open PTY (pseudo-terminal) for Ctrl+C support
    channel = ssh.get_transport().open_session()
    channel.get_pty()
    channel.exec_command(command)
    
    # Store for later termination
    RUNNING_SCRIPTS[key] = {"mode": "remote", "ssh": ssh, "channel": channel}
```

**Why PTY?** A pseudo-terminal is needed to send signals (like Ctrl+C/`\x03`) to the remote process. Without a PTY, `channel.send("\x03")` wouldn't interrupt the process.

#### Local Script Runner with Whitelist

```python
ALLOWED_SCRIPTS = {
    'front.py', 'top_corner.py', 'hand_raise.py', 'leaning.py',
    'passing_paper.py', 'mobile_detection.py', 'hybrid_detector.py',
    'process_uploaded_video.py', 'process_uploaded_video_stream.py',
}

def local_run_script(script_path):
    script_name = os.path.basename(script_path)
    
    # Security: only whitelisted scripts can run
    if script_name not in ALLOWED_SCRIPTS:
        return False, f"Script '{script_name}' not allowed."
    
    # Security: no shell=True (prevents command injection)
    process = subprocess.Popen(
        ['python', script_name],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=script_dir, text=True
    )
```

**Why whitelist?** Without it, an attacker who compromises the admin account could execute arbitrary scripts. The whitelist limits execution to known ML scripts only.

**Why no `shell=True`?** `shell=True` passes the command through the OS shell (cmd.exe on Windows), which allows shell injection via crafted filenames. `['python', script_name]` executes Python directly, passing `script_name` as a safe argument.

---

## B17. Custom Email Backend

### Simple Explanation
Gmail's SMTP requires TLS (encrypted connection). Python's default `starttls()` method sometimes fails when custom SSL certificates are used. Our custom backend calls `starttls()` without the `keyfile`/`certfile` parameters that cause the error.

### Technical Explanation

```python
class CustomEmailBackend(DjangoEmailBackend):
    def open(self):
        if self.connection:
            return False
        
        connection = self.connection_class(self.host, self.port, timeout=self.timeout)
        connection.ehlo()
        if self.use_tls:
            connection.starttls()  # No keyfile/certfile args
            connection.ehlo()
        if self.username and self.password:
            connection.login(self.username, self.password)
        self.connection = connection
        return True
```

```python
# settings.py reference:
EMAIL_BACKEND = 'app.custom_email_backend.CustomEmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
```

**Why not Django default?** In some Python/OS combinations, Django's default `EmailBackend.open()` passes `keyfile=self.ssl_keyfile, certfile=self.ssl_certfile` to `starttls()`, and Python 3.12+ deprecated those parameters, causing `DeprecationWarning` or outright failure. Our override avoids this entirely.

---

## B18. Security Implementation

### Simple Explanation
We implemented multiple security layers: authentication on all sensitive endpoints, CSRF protection for all POST requests, input sanitization, file upload validation, secure session configuration, and production-ready SSL headers.

### Technical Explanation

#### Authentication & Authorization

```python
# Every sensitive view has these decorators:
@login_required                        # Must be logged in
@user_passes_test(is_admin)            # Must be superuser (admin-only views)
@require_POST                          # Must be POST method (prevents CSRF via GET)

# WebSocket consumers:
if self.user.is_anonymous:
    await self.close()                 # Reject unauthenticated WebSockets
if not self.user.is_superuser:
    return                             # Silently ignore non-admin commands
```

#### CSRF Protection

```python
# settings.py
CSRF_COOKIE_HTTPONLY = False  # JS must read CSRF token for AJAX
```

All AJAX requests include the CSRF token in the header:
```javascript
headers: {'X-CSRFToken': getCookie('csrftoken')}
```

`@require_POST` on all state-changing views ensures GET requests can't trigger actions (prevents CSRF via image tags, etc.).

#### Session Security

```python
SESSION_COOKIE_AGE = 3600                    # 1 hour timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE = True       # No persistent sessions
SESSION_COOKIE_HTTPONLY = True                # JS can't read session cookie
```

#### Input Sanitization

```python
# Video serving — prevent directory traversal:
filename = os.path.basename(filename)  # Strips ../../../etc/passwd → passwd

# File upload validation:
allowed_types = ['video/mp4', 'video/avi', ...]
if video_file.content_type not in allowed_types:
    return JsonResponse({'status': 'error'}, status=400)
if video_file.size > 500 * 1024 * 1024:  # 500MB
    return JsonResponse({'status': 'error'}, status=400)
```

#### Production Security (when DEBUG=False)

```python
if not DEBUG:
    SECURE_SSL_REDIRECT = True           # Force HTTPS
    SESSION_COOKIE_SECURE = True         # Cookie only over HTTPS
    CSRF_COOKIE_SECURE = True            # CSRF token only over HTTPS
    SECURE_HSTS_SECONDS = 31536000       # 1 year HSTS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
```

---

# Part C — Testing & Results

## How to Test Backend Components

### 1. Start the Development Server

```bash
python start_server.py              # LAN only
python start_server.py --ngrok      # With public tunnel
python start_server.py --port 9000  # Custom port
```

`start_server.py` performs 4 checks:
1. MySQL connectivity
2. Run pending migrations
3. Detect LAN IP
4. Optionally start ngrok tunnel

### 2. Test WebSocket Connectivity

Open browser DevTools → Console:
```javascript
ws = new WebSocket('ws://localhost:8000/ws/notifications/');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.onopen = () => console.log('Connected');
```

### 3. Test Authentication Flow

```
1. Visit /register/teacher/ → Create account
2. Visit /login/ → Login with credentials
3. Visit /profile/ → Should show profile (redirects to /login/ if not authed)
4. Visit /malpractice_log/ → Should show filtered logs based on role
```

### 4. Test Camera Request Flow

```
1. Admin: Open /run_cameras/
2. Teacher: Open /teacher_cameras/ (different browser/incognito)
3. Admin: Click "Start Camera" on a teacher
4. Teacher: Should see camera request modal
5. Teacher: Click "Accept"
6. Admin: Should see live camera feed in grid
```

### 5. Test Video Upload

```
1. Visit /upload_video/
2. Select lecture hall + video file
3. Click "Start Processing"
4. Should see live MJPEG stream of annotated processing
5. After completion: should show stats (time, frames, detections)
```

## Expected Performance

| Metric | Value |
|--------|-------|
| Login response time | < 100ms |
| WebSocket connection time | < 50ms |
| Camera request → teacher notification | < 200ms |
| Malpractice log page (1000 logs) | < 500ms |
| Video upload (100MB) | 5-10s (network dependent) |
| MJPEG stream latency | < 200ms |

---

# Part D — Viva Q&A Bank (60+ Questions)

## ASGI & Architecture

**Q1: Why did you choose ASGI over WSGI?**
WSGI (Web Server Gateway Interface) handles one request at a time — it's synchronous and connection-less. Our application needs persistent WebSocket connections for real-time camera streaming and notifications. ASGI (Asynchronous Server Gateway Interface) supports both HTTP and WebSocket protocols simultaneously. Daphne, our ASGI server, handles HTTP requests normally while maintaining long-lived WebSocket connections for camera data.

**Q2: What is ProtocolTypeRouter and how does it work?**
It sits at the ASGI application entry point and inspects each incoming connection's protocol. HTTP connections are routed to Django's standard `get_asgi_application()`. WebSocket connections are routed through `AuthMiddlewareStack` (for session-based auth) and then `URLRouter` (for matching WS URLs to consumers). This single entry point handles both protocols on the same port.

**Q3: What is AuthMiddlewareStack?**
It extracts the authenticated user from the session cookie sent during the WebSocket handshake. When a browser opens a WebSocket to `ws://host/ws/notifications/`, the HTTP upgrade request includes cookies. AuthMiddlewareStack reads the session cookie, queries the database for the user, and populates `self.scope['user']` — making the user available in our consumer code.

**Q4: Why Daphne and not Uvicorn?**
Daphne is the reference ASGI server by the Django Channels team. It has first-class support for Channels' protocols, handles both HTTP and WebSocket on the same port, and supports binary WebSocket messages natively. While Uvicorn is faster for pure HTTP, Daphne's WebSocket handling is more mature with Django Channels specifically.

**Q5: What happens if you use WSGI (gunicorn) instead of ASGI?**
WebSocket connections would fail entirely — WSGI doesn't support the WebSocket protocol. All real-time features (camera streaming, notifications, teacher status) would break. Only HTTP views would work.

## Django Channels

**Q6: What is a Channel Layer and what does it do?**
A channel layer is a message transportation system that allows different parts of the application (different consumers, different servers) to communicate. When an admin sends a "start camera" command, the channel layer routes it from the admin's consumer to the specific teacher's consumer. It's like a message bus or pub-sub system.

**Q7: Explain the difference between InMemoryChannelLayer and RedisChannelLayer.**
InMemoryChannelLayer stores messages in Python process memory — it's simple and fast but only works within a single server process. RedisChannelLayer uses an external Redis server to store messages, enabling communication across multiple server instances (horizontal scaling). We use InMemory for our single-server demo; production would use Redis.

**Q8: What is a group in Django Channels?**
A group is a named collection of WebSocket channels. When you send a message to a group, every consumer in that group receives it. We use groups like `admin_notifications` (all admin connections), `user_5` (teacher #5's connections), and `admin_camera_grid` (admin grid viewers). Consumers join groups in `connect()` and leave in `disconnect()`.

**Q9: How does the `type` field in group_send relate to consumer methods?**
The `type` field uses dots (e.g., `session.update`) which Channels converts to underscores to find the handler method (`session_update`). This is automatic name resolution — you don't need explicit routing tables. The method must accept `self` and `event` parameters.

**Q10: Why do you use `@database_sync_to_async`?**
Django's ORM is synchronous — it blocks until the database query completes. Our consumers are async (running in the event loop). Calling sync ORM code directly would block the entire event loop, freezing all WebSocket connections. `@database_sync_to_async` runs the ORM code in a thread pool, keeping the event loop free to handle other connections.

## WebSocket Consumers

**Q11: Explain the three WebSocket consumers and their roles.**
(1) **NotificationConsumer** — bidirectional JSON: camera requests/responses between admin and teachers, teacher online/offline status, malpractice alerts. (2) **CameraStreamConsumer** — binary frames from teacher webcam → ML processing → annotated frames back + forwarding to admin grid. (3) **AdminGridConsumer** — admin receives binary frames from all active teacher cameras for the grid view.

**Q12: Why does CameraStreamConsumer reject admin connections?**
Only teachers stream webcam data. The admin views streams through AdminGridConsumer. Allowing admin connections to CameraStreamConsumer would confuse the pipeline — the ML processor expects teacher webcam frames, not admin data.

**Q13: Explain the frame-dropping pattern in CameraStreamConsumer.**
Webcam sends frames at ~20 FPS but ML takes ~60-80ms per frame (~13 FPS). Instead of queuing frames (which would grow unboundedly and increase latency), we store only the latest frame in `_latest_frame`. ML processes this when it's free, skipping intermediate frames. This ensures we always process the most recent data, maintaining real-time responsiveness.

**Q14: Why bypass the channel layer for admin grid frames?**
The channel layer serializes messages, queues them, and deserializes on delivery. At 10 FPS × 5 teachers = 50 messages/second, each containing 60KB+ JPEG data, the channel layer becomes a bottleneck. By storing admin consumers' `send()` function directly in `ADMIN_GRID_SENDERS` and calling it from the camera consumer, we eliminate all serialization overhead.

**Q15: What is ADMIN_GRID_SENDERS and how is it used?**
A module-level dictionary mapping `{channel_name: send_function}`. When an admin connects to AdminGridConsumer, their `self.send` method is stored. When a teacher's frame arrives in CameraStreamConsumer, we iterate over all stored send functions and call them directly with binary data. Dead connections are detected via try/except and cleaned up.

**Q16: How do you handle teacher disconnection during recording?**
The `disconnect()` method of CameraStreamConsumer calls `self.frame_processor.finalize_all_recordings()`. This stops all active VideoWriters, converts clips to H.264, computes probability scores, saves to database, and notifies the admin. No evidence is lost even on abrupt disconnection.

**Q17: What is the binary WebSocket frame protocol?**
Each binary message is: [4 bytes teacher_id big-endian] + [raw JPEG bytes]. The admin's JavaScript reads the first 4 bytes to identify the teacher, then converts the rest to a blob for display. This avoids JSON/base64 encoding overhead — 33% bandwidth savings.

## Views & HTTP

**Q18: How does the malpractice log handle role-based access?**
Admins see all logs with optional review filter (reviewed/not_reviewed). Teachers only see logs where: `lecture_hall` matches their assignment, `verified=True` (admin has reviewed), `is_malpractice=True` (confirmed malpractice), and `teacher_visible=True` (admin has released). This three-layer filter ensures teachers never see unreviewed or dismissed logs.

**Q19: Explain the review_malpractice workflow.**
Admin POSTs JSON with `{proof: filename, decision: 'yes'/'no'}`. The view finds the MalpraticeDetection record, sets `verified=True`, `is_malpractice=True/False`. If malpractice, sets `teacher_visible=True` and spawns a background thread that sends email (via SMTP/Gmail) and SMS (via Twilio) to the assigned teacher.

**Q20: Why use background threads for email/SMS?**
SMTP email takes 2-5 seconds (DNS lookup, TLS handshake, authentication, delivery). Twilio API takes 1-2 seconds. The HTTP response should return in < 200ms. Running notifications in a daemon thread ensures the admin's browser gets an immediate "success" response while emails/SMS are delivered asynchronously.

**Q21: What does `ensure_probability_scores()` do?**
It's a retroactive compatibility function. Older malpractice logs (created before the probability scoring system) have `probability_score=NULL`. This function detects those logs, opens their evidence video with OpenCV to measure duration, and applies a simplified 2-factor formula (60% duration + 40% type prior) to backfill scores.

**Q22: How does serve_video handle browser compatibility?**
ML records videos in mp4v codec (.avi) which browsers can't play. serve_video converts to H.264 (.mp4) using a 3-strategy chain: (1) system ffmpeg, (2) imageio-ffmpeg Python package, (3) OpenCV H.264 codecs. Converted files are cached in `_h264_cache/` directory. Serves with `Accept-Ranges: bytes` header for seeking support.

**Q23: Explain HTTP Range requests for video seeking.**
When a user clicks the middle of a video timeline, the browser sends `Range: bytes=500000-`. The server opens the file, seeks to byte 500000, reads the requested range, and returns status 206 (Partial Content) with `Content-Range` header. This allows instant seeking without downloading the entire file.

**Q24: How does MJPEG streaming work for uploaded videos?**
`StreamingHttpResponse` with `content_type='multipart/x-mixed-replace; boundary=frame'`. An async generator yields JPEG frames in multipart format. The browser's `<img>` tag natively renders this as a video stream. A background thread runs ML processing and pushes frames to an `asyncio.Queue`, which the async generator consumes.

**Q25: What is the sync-to-async bridge pattern in stream_video_processing?**
ML processing is synchronous (PyTorch blocks). Django's `StreamingHttpResponse` with Daphne requires an async generator. We bridge these worlds: a background thread runs sync ML code and uses `asyncio.run_coroutine_threadsafe()` to push frames to an `asyncio.Queue`. The async generator awaits `queue.get()` and yields frames.

**Q26: What is the VIDEO_SESSIONS dictionary for?**
It stores upload session metadata in memory: `{session_id: {filepath, hall_id, status, user_id, stats}}`. Created during upload, used during streaming to locate the file and track processing stats. Auto-cleaned 5 minutes after completion. Not persisted to DB because it's transient processing state.

## Authentication & Security

**Q27: How does session-based authentication work in Django?**
On login, `auth_login()` creates a session record in the DB, generates a session ID, and sets it as a cookie. On subsequent requests, Django's `SessionMiddleware` reads the cookie, looks up the session in the DB, and populates `request.user`. For WebSockets, `AuthMiddlewareStack` does the same using the handshake cookies.

**Q28: Why is `CSRF_COOKIE_HTTPONLY = False`?**
AJAX requests need to include the CSRF token in the `X-CSRFToken` header. JavaScript reads this from the `csrftoken` cookie. If `HTTPONLY=True`, JavaScript can't read the cookie, and AJAX POST requests would fail with 403 Forbidden. The session cookie remains `HTTPONLY=True` (JS doesn't need it).

**Q29: How do you prevent directory traversal in serve_video?**
`os.path.basename(filename)` strips all directory components. An input like `../../../etc/passwd` becomes just `passwd`. Then we join it with `MEDIA_ROOT`, ensuring files are only served from the media directory.

**Q30: Explain the script whitelist in utils.py.**
`ALLOWED_SCRIPTS` is a set of ML script filenames that `local_run_script()` is permitted to execute. Before spawning a subprocess, the requested script name is checked against this whitelist. This prevents an attacker (or compromised admin account) from executing arbitrary system commands through the script triggering feature.

**Q31: Why use `subprocess.Popen(['python', name])` instead of `shell=True`?**
`shell=True` passes the command through cmd.exe (Windows), enabling shell metacharacter injection. A malicious script name like `script.py & del /q C:\` would execute the delete command. List form (`['python', name]`) passes arguments directly to the Python executable — the `name` is treated as a literal argument, not interpreted by a shell.

**Q32: What security headers are configured?**
`X_FRAME_OPTIONS='DENY'` (prevents clickjacking via iframe), `SECURE_CONTENT_TYPE_NOSNIFF=True` (prevents MIME sniffing). In production: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS=31536000`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`. Note: `SECURE_BROWSER_XSS_FILTER` was removed as it is deprecated in Django 6.0+ (modern browsers handle XSS protection natively).

**Q33: How is session timeout configured?**
`SESSION_COOKIE_AGE = 3600` (1 hour). `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` (session dies when browser closes). `SESSION_COOKIE_HTTPONLY = True` (JS can't access session cookie). Combined: sessions last max 1 hour or until browser close, whichever comes first.

## Notifications & External Services

**Q34: How does the Twilio SMS integration work?**
Twilio provides a REST API for sending SMS. Our `send_sms_notification()` creates a Twilio `Client` with account SID + auth token (from settings/env vars), then calls `client.messages.create(body=message, from_=twilio_number, to=teacher_phone)`. Phone numbers must be in E.164 format (+919876543210).

**Q35: How does email notification work?**
Django's `send_mail()` uses our `CustomEmailBackend` which connects to `smtp.gmail.com:587` with TLS. Gmail requires an "App Password" (not the regular password) when 2FA is enabled. Credentials are stored in `.env` as `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD`.

**Q36: Why a custom email backend?**
Python 3.12+ deprecated the `keyfile` and `certfile` parameters in `smtplib.SMTP.starttls()`. Django's default backend passes these parameters, causing warnings or failures. Our `CustomEmailBackend` overrides `open()` to call `starttls()` without those parameters, ensuring compatibility.

**Q37: What happens if email or SMS fails?**
Both services run in daemon threads with try/except wrapping. Failures are logged (`print`) but don't crash the application or affect the HTTP response. The malpractice review is saved successfully regardless of notification delivery. The `email_sent` field on ReviewSession tracks whether the email was actually delivered.

## Admin Heartbeat

**Q38: How does the admin heartbeat system work?**
`CONNECTED_ADMINS` (a set) tracks all admin WebSocket connections. When the last admin disconnects and active streams exist, a 60-second timer starts via `asyncio.get_running_loop().call_later()`. If no admin reconnects within 60 seconds, all active teachers receive an "admin disconnected" warning via WebSocket.

**Q39: Why use a 60-second grace period?**
Admins may briefly disconnect (page refresh, WiFi hiccup, browser tab switch). Immediately warning teachers would cause unnecessary disruption. 60 seconds allows for transient disconnections while still alerting teachers of genuine admin absence.

**Q40: What happens to camera streams when admin disconnects?**
Streams continue running — the teacher's camera keeps recording and ML keeps processing. Only the admin's monitoring view is interrupted. After 60s, teachers see a warning banner but cameras aren't automatically stopped. Evidence continues to be captured.

## Django ORM & Data

**Q41: What is `select_related()` and why do you use it?**
`select_related()` performs a SQL JOIN to fetch related objects in a single query. Without it, accessing `hall.assigned_teacher.first_name` would trigger a separate query per hall (N+1 problem). With it: `LectureHall.objects.select_related('assigned_teacher')` fetches everything in one query.

**Q42: What is the Q object used for in view_teachers?**
`Q` objects allow complex queries with OR operators. Django's `.filter()` only supports AND. `Q(username__icontains=query) | Q(first_name__icontains=query) | Q(email__icontains=query)` matches rows where ANY of these fields contain the search term.

**Q43: Why does `on_delete=SET_NULL` vs `CASCADE` matter?**
`CASCADE`: deleting the parent deletes all children (e.g., deleting a User deletes all their CameraSession records). `SET_NULL`: deleting the parent nullifies the FK (e.g., deleting a teacher sets `LectureHall.assigned_teacher = NULL` — the hall remains). We use SET_NULL for teacher-to-hall so deleting a teacher doesn't remove the hall.

**Q44: How does the review filter system work in the malpractice log?**
URL parameters like `?review=not_reviewed&probability=above_50&sort=prob_high` are read from `request.GET`. Each filter progressively narrows the queryset using Django's ORM chaining: `logs.filter(verified=False).filter(probability_score__gte=50).order_by('-probability_score')`.

## Video Processing

**Q45: Explain the complete video upload-to-processing pipeline.**
(1) Teacher selects file + hall → AJAX POST to `/process_video/` → file saved to disk, session_id returned. (2) Browser sets `<img src="/stream_video_processing/{session_id}/">` → MJPEG stream starts. (3) Background thread reads video with OpenCV, runs ML on every 3rd frame, pushes annotated frames to asyncio.Queue. (4) Async generator yields MJPEG frames to browser. (5) Browser polls `/get_processing_stats/{session_id}/` for completion stats.

**Q46: Why do you clean up the uploaded video file after processing?**
The original uploaded file is only needed during processing. Evidence clips are saved separately by the ML pipeline. Keeping all uploaded videos would consume disk space rapidly (exam videos can be 100-500MB each). Cleanup happens in the async generator's `finally` block.

**Q47: What is `multipart/x-mixed-replace`?**
An HTTP content type where the server sends multiple parts (separated by boundaries) and each new part REPLACES the previous one in the browser's display. For MJPEG: each "part" is a JPEG image. The browser displays each JPEG as it arrives, creating the illusion of video. No JavaScript needed — native `<img>` tag support.

## start_server.py

**Q48: What does start_server.py do?**
It's a one-click development server launcher that: (1) checks MySQL connectivity, (2) runs pending migrations, (3) detects the machine's LAN IP, (4) optionally starts an ngrok tunnel for public access, (5) starts Daphne ASGI server bound to 0.0.0.0, (6) prints a formatted banner with all access URLs.

**Q49: Why bind to 0.0.0.0?**
`0.0.0.0` means "listen on all network interfaces." Binding to `127.0.0.1` would only accept connections from localhost. Since we need LAN access (teachers connect from different machines on the same WiFi), we bind to 0.0.0.0 so the server accepts connections from any IP.

**Q50: What is ngrok and why is it used?**
ngrok creates a secure tunnel from a public URL to our local server. For demo purposes — when the evaluator's machine isn't on the local WiFi, ngrok provides a `https://xyz.ngrok.io` URL that routes to our local Daphne server. The `--ngrok` flag enables this.

## Advanced Architecture

**Q51: How does the async generator in StreamingHttpResponse work with Daphne?**
Daphne, being an ASGI server, natively supports async generators. It repeatedly `await`s the next value from the generator and sends each yielded chunk to the HTTP response. Sync generators would be buffered (Daphne collects all output before sending) — async generators stream in real-time.

**Q52: What is `run_in_executor()` and why is it critical?**
`loop.run_in_executor(pool, func, args)` runs a synchronous function in a thread pool and returns an awaitable Future. Our ML inference (PyTorch) and ORM queries (Django) are both synchronous. Without `run_in_executor`, they'd block the event loop, freezing all WebSocket connections.

**Q53: Why ThreadPoolExecutor(max_workers=3) for ML?**
Each ML stream requires ~1.2GB GPU memory. With RTX 3050 (4GB), 3 concurrent ML streams use ~3.6GB, leaving headroom for GPU overhead. A 4th stream would likely cause CUDA out-of-memory. The thread pool also prevents CPU contention from too many parallel inference passes.

**Q54: How do multiple consumers share state?**
Module-level dictionaries (`ACTIVE_STREAMS`, `ADMIN_GRID_SENDERS`, `CONNECTED_ADMINS`). Since Daphne runs in a single Python process, all consumers share the same memory space. These dicts provide O(1) lookup without database queries. Thread-safety is inherent because async code runs on the event loop (no parallel execution within the same loop).

**Q55: What is the difference between `self.send()` and `self.channel_layer.group_send()`?**
`self.send()` sends data directly to THIS consumer's WebSocket client. `group_send()` sends to ALL consumers in a named group — each recipient's handler method is called. Use `send()` for targeted responses (e.g., returning annotated frame to teacher). Use `group_send()` for broadcasts (e.g., notifying all admins of a detection).

## Error Handling & Edge Cases

**Q56: What happens if MySQL is down when the server starts?**
`start_server.py`'s `check_mysql()` function calls `connection.ensure_connection()`. If it fails, the script prints an error message and exits with `sys.exit(1)`. The server won't start without a working database connection.

**Q57: How do you handle concurrent camera sessions for the same teacher?**
In `create_camera_session()`, before creating a new session, we close any existing active sessions: `CameraSession.objects.filter(teacher=teacher, status__in=['requested', 'active']).update(status='stopped')`. This prevents duplicate sessions if the admin clicks "Start" multiple times.

**Q58: What if the admin deletes a lecture hall that's actively streaming?**
The `delete_hall` view explicitly deletes all associated CameraSession, MalpraticeDetection, and ReviewSession records. However, the in-memory `ACTIVE_STREAMS` dict still has the teacher's entry. The camera would continue streaming until the teacher disconnects, at which point `save_detection()` would fail gracefully (hall not found → caught by except).

**Q59: How do you prevent race conditions with ADMIN_GRID_SENDERS?**
Because Daphne's event loop is single-threaded (asyncio), there's no true parallelism between async coroutines. `_forward_to_admin_binary()` iterates over `ADMIN_GRID_SENDERS` atomically within one event loop tick. The `list()` snapshot prevents issues if the dict changes during iteration.

**Q60: What happens if Twilio credentials are invalid?**
`send_sms_notification()` would raise a Twilio `AuthenticationError`. Since it runs in a daemon thread with try/except, the error is logged but doesn't affect the HTTP response. The malpractice review succeeds; only the SMS notification fails.

## Comparison Questions

**Q61: Why Django and not Flask/FastAPI?**
Django provides: (1) built-in ORM with migrations, (2) admin panel, (3) authentication system, (4) session management, (5) CSRF protection — all out-of-the-box. Flask/FastAPI would require assembling these from third-party packages. Django Channels adds WebSocket support, making Django feature-complete for our needs.

**Q62: Why not use Socket.IO instead of Django Channels?**
Socket.IO is a standalone WebSocket library requiring a separate server (usually Node.js). Django Channels integrates WebSocket handling directly into our Django application — sharing the same authentication, database, and codebase. One codebase, one deployment, one framework.

**Q63: Why are notifications JSON but camera frames binary?**
Notifications are small, structured data ({"type": "camera_request", "teacher_id": 5}) — JSON is ideal. Camera frames are large binary blobs (60KB+ JPEGs) — encoding as base64 JSON would add 33% overhead. Using the appropriate format for each data type optimizes bandwidth and CPU usage.

**Q64: Why Twilio for SMS and not a free service?**
Twilio provides: (1) reliable delivery, (2) Indian phone number support, (3) well-documented Python SDK, (4) delivery receipts. Free alternatives (email-to-SMS gateways) are unreliable and carrier-dependent. For a production exam monitoring system, notification reliability is critical.

**Q65: What would you change for a 1000-user deployment?**
(1) Switch to RedisChannelLayer for multi-server support. (2) Add Celery for background task processing (email/SMS). (3) Use Nginx as reverse proxy with SSL termination. (4) Separate ML processing to dedicated GPU servers. (5) Add PostgreSQL connection pooling. (6) Horizontal scaling with multiple Daphne workers behind a load balancer.

---

> **Study Tips for Person 2:**
> - Draw the WebSocket connection flow from memory (browser → Daphne → ProtocolTypeRouter → AuthMiddleware → URLRouter → Consumer)
> - Practice explaining the camera request lifecycle end-to-end (admin clicks → DB session → WS message → teacher accepts → stream starts)
> - Know the difference between `send()`, `send_json()`, and `group_send()` 
> - Understand WHY we bypass the channel layer for frames but not for notifications
> - Be able to explain the binary frame protocol (4-byte header + JPEG)
> - Memorize the 3 consumers, their connection requirements, and their data directions
> - Know all security measures: decorators, CSRF, session config, file validation, script whitelist
> - Practice explaining the sync-to-async bridge pattern for MJPEG streaming
