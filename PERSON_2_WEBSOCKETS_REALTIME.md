# Person 2 — WebSocket & Real-Time Communication System

## Your Role
You built the **real-time communication backbone** of the project — the WebSocket system that enables live video streaming from teachers' cameras to the admin dashboard, real-time notifications, camera management, and the async server infrastructure. You manage how frames travel from teacher's webcam → server → AI processing → back to teacher + admin grid.

## Key Files You Own
| File | Purpose | Lines |
|------|---------|-------|
| `app/consumers.py` | 3 WebSocket consumers (Notification, CameraStream, AdminGrid) | 1050 |
| `app/routing.py` | WebSocket URL routing | 13 |
| `app/asgi.py` | ASGI application configuration | ~20 |
| `app/settings.py` (Channel Layers section) | Redis/InMemory channel layer config | ~15 |

---

## PART A: Everything You Built

### 1. NotificationConsumer — Camera & Status Management
- Handles admin camera start/stop requests (admin → teacher)
- Manages teacher permission flow (teacher accepts/denies)
- Tracks teacher online/offline status
- Camera session lifecycle (requested → active → stopped → denied)
- Admin disconnect heartbeat (60-second timeout stops all streams)
- Multi-tab safety (prevents duplicate admin connections)
- Broadcasts real-time malpractice alerts
- Sends review completion notifications

### 2. CameraStreamConsumer — Live Video Pipeline
- Receives raw JPEG frames from teacher's webcam via binary WebSocket
- Feeds frames to ML pipeline (FrameProcessor) on a dedicated thread
- Frame-dropping to prevent backlog accumulation
- Sends annotated frames (with detection overlays) back to teacher
- Forwards raw frames to AdminGridConsumer for admin's grid view
- Manages per-stream video recording
- Detects and reports malpractice in real-time

### 3. AdminGridConsumer — Multi-Camera Grid
- Receives raw frames from all active teacher cameras
- Routes frames to admin's browser for grid layout display
- Tracks which teachers are streaming via `ADMIN_GRID_SENDERS`
- Handles admin connection/disconnection

### 4. WebSocket Routing
- 3 endpoints: `/ws/notifications/`, `/ws/camera/stream/`, `/ws/camera/admin-grid/`
- Django Channels routing with regex URL patterns

### 5. ASGI Configuration
- Configured Daphne as the ASGI server
- ProtocolTypeRouter for HTTP + WebSocket
- AuthMiddlewareStack for session-based WebSocket authentication

---

## PART B: How Each Thing Works (Simple + Technical)

---

### B1. What Are WebSockets?

**Simple:** Normally, your browser talks to a server like sending letters — you send a request, wait for a reply, done. WebSockets are like a phone call — once connected, both sides can talk to each other anytime, instantly, without hanging up and calling again.

**Technical:** WebSocket is a full-duplex, persistent communication protocol (RFC 6455) that operates over a single TCP connection. Unlike HTTP (request-response), WebSockets allow bidirectional real-time data transfer. The connection starts as an HTTP request (the "handshake"), then upgrades to WebSocket:

```
Client: GET /ws/camera/stream/ HTTP/1.1
        Upgrade: websocket
        Connection: Upgrade

Server: HTTP/1.1 101 Switching Protocols
        Upgrade: websocket
        Connection: Upgrade
```

After this handshake, both client and server can send messages at any time without HTTP overhead (headers, cookies, etc.).

---

### B2. Why WebSockets Instead of Alternatives?

| Alternative | Why We Didn't Use It |
|-------------|---------------------|
| **HTTP Polling** | Client repeatedly asks "any new frames?" every 100ms. Wastes bandwidth, adds 50-100ms latency per request, can't scale to 30fps video |
| **Server-Sent Events (SSE)** | One-directional (server→client only). We need bidirectional (teacher sends frames, receives annotated frames back) |
| **Socket.IO** | Adds a JavaScript dependency, wraps WebSockets with fallbacks we don't need. Django Channels gives us native WebSocket support |
| **WebRTC** | Designed for peer-to-peer video calling. Overkill for our use case (we need server-side processing). Complex NAT traversal, ICE/STUN/TURN setup |
| **gRPC Streaming** | Not browser-native. Would need a proxy layer. Too complex for our needs |

**Winner: Django Channels** — Native WebSocket support for Django, uses the same auth system, supports channel groups for broadcasting.

---

### B3. Django Channels Architecture

**Simple:** Think of Django Channels as a post office. Each teacher and admin has a "mailbox" (channel). When someone sends a message, it gets routed to the right mailbox. Groups are like mailing lists — one message reaches everyone in the group.

**Technical:**

```
┌─────────────────────────────────────────────────────┐
│                  ASGI Application                      │
│                                                        │
│  ProtocolTypeRouter                                   │
│  ├── "http"  → Django ASGI app (views, templates)     │
│  └── "websocket" → AuthMiddlewareStack                │
│       └── URLRouter                                   │
│            ├── /ws/notifications/ → NotificationConsumer│
│            ├── /ws/camera/stream/ → CameraStreamConsumer│
│            └── /ws/camera/admin-grid/ → AdminGridConsumer│
└─────────────────────────────────────────────────────┘
```

**Key Concepts:**
1. **Consumer** = WebSocket equivalent of a Django view. Each WebSocket connection gets its own consumer instance.
2. **Channel** = A named mailbox. Each consumer instance has a unique `self.channel_name` (e.g., `specific.abc123`).
3. **Channel Group** = A named group of channels. Send one message, all members receive it.
4. **Channel Layer** = The message routing backend. We use `InMemoryChannelLayer` for development, `RedisChannelLayer` for production.

---

### B4. NotificationConsumer — How Camera Requests Work

**Simple:** When the admin clicks "Start Camera" for a teacher, a message goes through the WebSocket to that teacher's browser. The teacher's browser asks for permission and sends back "yes" or "no". If yes, the camera starts streaming.

**Technical Flow (step-by-step):**

```
1. Admin clicks "Start Camera" (Teacher: subashk)
   → Browser JS sends: {type: "camera_request", teacher_id: 2}

2. NotificationConsumer.handle_camera_request()
   → Creates CameraSession in DB (status: "requested")
   → Sends to teacher's personal channel:
     channel_layer.send(teacher_channel, {
         type: "camera.request",
         session_id: 15,
         teacher_id: 2,
         requested_by: "rpranav"
     })

3. Teacher's browser receives the request
   → Shows "Admin wants your camera" prompt
   → Teacher clicks Accept

4. Teacher's browser sends: {type: "camera_response", accepted: true, session_id: 15}

5. NotificationConsumer.handle_camera_response()
   → Updates CameraSession (status: "active", started_at: now)
   → Broadcasts to admin group:
     channel_layer.group_send("admin_group", {
         type: "session.update",
         session_id: 15,
         status: "active"
     })

6. Teacher's browser opens CameraStreamConsumer connection
   → Starts MediaStream (getUserMedia API)
   → Sends JPEG frames via binary WebSocket
```

**Permission Flow Diagram:**
```
Admin                  Server                 Teacher
  │                      │                      │
  │──camera_request──►   │                      │
  │                      │──camera.request──►   │
  │                      │                      │ [Teacher sees prompt]
  │                      │◄──camera_response──  │ [Accept/Deny]
  │◄──session.update──  │                      │
  │ [Grid updates]       │                      │ [Camera starts streaming]
```

---

### B5. CameraStreamConsumer — Live Frame Processing Pipeline

**Simple:** The teacher's webcam captures a photo 30 times per second. Each photo is sent to the server, which runs it through the AI, draws boxes around detected malpractice, and sends the annotated photo back. At the same time, the raw photo is forwarded to the admin's grid view.

**Technical:**

```python
class CameraStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.teacher_id = self.user.id
        
        # Create FrameProcessor for ML detection
        self.processor = FrameProcessor(
            lecture_hall=self.lecture_hall_name,
            teacher_id=self.teacher_id
        )
        
        # Start ML processing thread
        self.ml_thread = Thread(target=self._ml_processing_loop, daemon=True)
        self.ml_thread.start()
        
        await self.accept()
    
    async def receive(self, bytes_data=None, text_data=None):
        if bytes_data:
            # Binary data = JPEG frame from camera
            self.latest_frame = bytes_data  # Replace (frame-dropping)
            self.frame_event.set()           # Wake ML thread
            
            # Buffer for video recording (ALL frames, not just ML-processed ones)
            self.processor.buffer_frame(bytes_data)
            
            # Forward raw frame to admin grid
            await self.channel_layer.group_send(
                "admin_grid",
                {
                    "type": "camera.frame",
                    "teacher_id": self.teacher_id,
                    "teacher_name": self.user.username,
                    "frame": base64.b64encode(bytes_data).decode()
                }
            )
```

**Frame-Dropping Explained:**

```python
def _ml_processing_loop(self):
    """Runs on dedicated thread — processes only the LATEST frame"""
    while self.running:
        self.frame_event.wait()  # Block until new frame arrives
        self.frame_event.clear()
        
        frame = self.latest_frame  # Grab latest (may skip frames)
        result = self.processor.process_frame(frame)
        
        if result:
            # Send annotated frame back to teacher
            asyncio.run_coroutine_threadsafe(
                self.send(bytes_data=result['annotated_frame']),
                self.loop
            )
            
            # Handle completed detections (save to DB)
            for detection in result.get('detections', []):
                asyncio.run_coroutine_threadsafe(
                    self._save_detection(detection),
                    self.loop
                )
```

**Why frame-dropping?** Webcam sends 30fps. ML takes ~70ms per frame (14fps). Without frame-dropping, after 1 minute we'd have a 16-second backlog (30-14 = 16 frames/sec accumulating). Frame-dropping ensures we always process the most recent frame.

---

### B6. AdminGridConsumer — Multi-Camera Grid

**Simple:** The admin sees a grid of live camera feeds from all teachers. Each teacher's stream is forwarded from the CameraStreamConsumer to the AdminGridConsumer, which sends it to the admin's browser.

**Technical:**
```python
class AdminGridConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Only admins can connect
        if not self.scope["user"].is_superuser:
            await self.close()
            return
        
        await self.channel_layer.group_add("admin_grid", self.channel_name)
        CONNECTED_ADMINS.add(self.channel_name)
        await self.accept()
    
    async def camera_frame(self, event):
        """Receive frame from CameraStreamConsumer, forward to admin browser"""
        await self.send(text_data=json.dumps({
            "type": "camera_frame",
            "teacher_id": event["teacher_id"],
            "teacher_name": event["teacher_name"],
            "frame": event["frame"]  # base64-encoded JPEG
        }))
```

**Data Flow:**
```
Teacher Webcam → [binary JPEG] → CameraStreamConsumer
                                        │
                    ┌───────────────────┼──────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            ML Processing        Admin Grid          Video Buffer
            (annotated frame)    (raw frame)         (recording)
                    │                   │
                    ▼                   ▼
            Teacher Browser      Admin Browser
            (sees annotations)   (sees raw grid)
```

---

### B7. Admin Disconnect Heartbeat

**Simple:** If the admin closes their browser, the system waits 60 seconds, then stops all camera streams automatically. But if the admin reconnects within 60 seconds (e.g., browser crashed), everything continues working.

**Technical:**
```python
async def disconnect(self, close_code):
    if self.is_admin:
        CONNECTED_ADMINS.discard(self.channel_name)
        
        if len(CONNECTED_ADMINS) == 0:
            # No admin connected — start 60-second timer
            _admin_disconnect_timer = asyncio.get_event_loop().call_later(
                ADMIN_TIMEOUT_SECONDS,
                lambda: asyncio.ensure_future(self._admin_timeout_handler())
            )

async def _admin_timeout_handler(self):
    """Called after 60 seconds with no admin connected"""
    if len(CONNECTED_ADMINS) == 0:
        # Still no admin — stop all streams
        await self.stop_all_camera_sessions()
        
        # Notify all teachers
        await self.channel_layer.group_send(
            "teachers",
            {"type": "admin.disconnected", "message": "Admin disconnected"}
        )
```

**Why 60 Seconds?** Long enough for an admin to refresh their browser or switch tabs. Short enough that cameras don't run unsupervised for too long (wasting bandwidth and processing).

---

### B8. ASGI / Daphne — The Server

**Simple:** Normal Django uses WSGI, which can only handle one request at a time per worker. ASGI (used by Daphne) can handle thousands of WebSocket connections simultaneously because it's asynchronous — it doesn't wait for one connection to finish before handling the next.

**Technical:**

| Feature | WSGI (Gunicorn) | ASGI (Daphne) |
|---------|-----------------|---------------|
| Protocol | HTTP only | HTTP + WebSocket |
| Concurrency | Thread-based (1 thread = 1 connection) | Async I/O (1 event loop = thousands of connections) |
| Model | Synchronous | Asynchronous (async/await) |
| Use case | Traditional web apps | Real-time apps, WebSockets, long-polling |

```python
# asgi.py
import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from app.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

**Why Daphne and not Uvicorn?**
- Daphne is built specifically for Django Channels
- Uvicorn is a general ASGI server that doesn't natively understand Channel Layers
- Daphne handles WebSocket protocol negotiation and Django session auth seamlessly
- In `settings.py`: `INSTALLED_APPS` includes `'daphne'` to use it as the dev server

---

### B9. Channel Layer — Message Routing

**Simple:** When the admin sends a camera request to "Teacher 5", how does the server know which WebSocket connection belongs to Teacher 5? The Channel Layer is like a phone directory — each connection registers a name, and messages are routed by name.

**Technical:**

**Development (InMemoryChannelLayer):**
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
        'CONFIG': {
            'capacity': 1000,   # Max messages in a channel before dropping
            'expiry': 10,       # Messages expire after 10 seconds
        },
    },
}
```

**Production (Redis):**
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    },
}
```

**Why Redis for production?**
- InMemoryChannelLayer doesn't work across multiple server processes/workers
- Redis is an in-memory data store that acts as a shared message broker
- Supports pub/sub pattern natively
- < 1ms message delivery latency

**Key operations:**
```python
# Send to a specific channel
await self.channel_layer.send(teacher_channel_name, message)

# Send to all members of a group
await self.channel_layer.group_send("admin_group", message)

# Add a channel to a group
await self.channel_layer.group_add("teachers", self.channel_name)

# Remove from group
await self.channel_layer.group_discard("teachers", self.channel_name)
```

---

### B10. Auto-Reconnect System

**Simple:** If the internet glitches for a moment, the WebSocket drops. Instead of the teacher having to refresh the page, the browser automatically tries to reconnect every 3 seconds.

**Technical (Client-side JS in template):**
```javascript
function connectWebSocket() {
    const ws = new WebSocket(`ws://${window.location.host}/ws/notifications/`);
    
    ws.onopen = () => {
        console.log("Connected");
        reconnectAttempts = 0;
    };
    
    ws.onclose = (event) => {
        // Don't reconnect if manually closed
        if (event.code === 1000) return;
        
        reconnectAttempts++;
        const delay = Math.min(3000 * reconnectAttempts, 30000); // Exponential backoff
        console.log(`Reconnecting in ${delay/1000}s...`);
        setTimeout(connectWebSocket, delay);
    };
}
```

**Exponential backoff:** First retry at 3 seconds, then 6, 9, 12... up to 30 seconds max. This prevents hammering the server if it's temporarily down.

---

## PART C: Testing & Results

### How You Tested
1. **Connection Testing:** Open/close WebSocket connections rapidly, verify no memory leaks
2. **Multi-user Testing:** Admin + 2 teachers simultaneously streaming cameras
3. **Network Disruption:** Disconnecting WiFi mid-stream, verifying auto-reconnect
4. **Race Condition Testing:** Rapid start/stop camera requests, multiple admin tabs
5. **Browser Compatibility:** Chrome, Firefox, Edge (all support WebSocket API)

### Results
| Metric | Value |
|--------|-------|
| WebSocket connection time | < 100ms |
| Frame delivery latency (teacher → admin grid) | < 50ms on LAN |
| Admin disconnect detection | Immediate (WebSocket close event) |
| Auto-reconnect time | 3 seconds (first attempt) |
| Max concurrent streams tested | 3 (limited by GPU, not WebSocket) |
| Memory per WebSocket connection | ~5MB |

### What Can Be Improved
1. **WebSocket compression** — Enable per-message deflate to reduce bandwidth by ~60%
2. **Multiple admin support** — Allow multiple admins to view the grid simultaneously
3. **WebRTC for streams** — Bypass server for video, use server only for ML processing
4. **Load balancing** — Redis-backed channel layer + multiple Daphne workers for scale

---

## PART D: Evaluation Q&A

### Core Questions

**Q1: What is a WebSocket and how is it different from HTTP?**
A: HTTP is request-response: the client sends a request, server responds, connection closes. WebSocket is persistent and bidirectional: once connected, either side can send data at any time without re-establishing the connection. This eliminates the overhead of HTTP headers (500+ bytes per request) and the latency of connection establishment.

**Follow-up: What's the WebSocket handshake?**
A: It starts as a normal HTTP GET request with `Upgrade: websocket` header. The server responds with HTTP 101 (Switching Protocols). After that, the protocol switches to WebSocket and HTTP is no longer used.

---

**Q2: Explain the 3 WebSocket consumers and their roles.**
A: 
- **NotificationConsumer (`/ws/notifications/`):** Handles camera management, teacher status, and real-time notifications. It's the "control plane" — no video data flows through it.
- **CameraStreamConsumer (`/ws/camera/stream/`):** Handles actual video streaming. Receives binary JPEG data from teacher's webcam, processes it with AI, and sends annotated frames back. It's the "data plane."
- **AdminGridConsumer (`/ws/camera/admin-grid/`):** Receives raw frames forwarded by CameraStreamConsumer and displays them in the admin's grid view. It's a "display-only" consumer.

**Follow-up: Why separate consumers instead of one big one?**
A: Separation of concerns. Notifications use JSON (text/small data), while camera streams use binary (large data). Mixing them in one consumer would make the code complex and create performance issues (small notification messages getting delayed behind large video frames).

---

**Q3: What is Django Channels and why did you use it?**
A: Django Channels extends Django to handle WebSocket connections. Without it, Django can only handle traditional HTTP requests. Channels provides:
1. WebSocket consumer classes (like views for WebSockets)
2. Channel layer for message routing between consumers
3. Integration with Django's auth, sessions, and middleware
4. ASGI support (async processing)

We chose it over alternatives like Socket.IO (which requires Node.js) or raw asyncio (which doesn't integrate with Django).

---

**Q4: How does frame-dropping work and why is it important?**
A: The webcam sends 30 frames/second, but ML processing takes ~70ms/frame (14fps). Without frame-dropping, unprocessed frames queue up — after 1 minute, we'd have a 16-second delay. Frame-dropping solves this by always replacing the pending frame with the newest one:
```python
self.latest_frame = bytes_data  # Always overwrite with newest
self.frame_event.set()           # Wake ML thread
```
The ML thread processes whatever `latest_frame` is when it wakes up, skipping any frames that arrived while it was processing.

---

**Q5: What is a Channel Layer? Why Redis?**
A: A Channel Layer is a message broker that routes messages between consumers. When Consumer A sends a message to "group X", the channel layer delivers it to all consumers that joined "group X".

InMemoryChannelLayer works for development (single process) but doesn't work across multiple workers/processes because each process has its own memory. Redis works across processes because it's an external shared server. Redis is also extremely fast (in-memory, < 1ms latency).

---

**Q6: How does the admin disconnect heartbeat work?**
A: When an admin disconnects, we start a 60-second timer. If no admin reconnects within 60 seconds, all camera streams are automatically stopped (to avoid cameras running without anyone watching). The timer is cancelled if an admin reconnects within the window.

**Follow-up: Why 60 seconds?**
A: It's a balance: long enough for browser refresh/tab switch (5-10 seconds), short enough to not waste resources (battery, bandwidth) on unmonitored streams.

---

**Q7: How do you handle authentication in WebSockets?**
A: Django Channels provides `AuthMiddlewareStack`, which reads Django session cookies from the WebSocket handshake request. The `self.scope["user"]` is automatically populated with the authenticated Django user. In `connect()`, we check `self.scope["user"].is_authenticated` and `is_superuser` to determine if it's a teacher or admin.

**Follow-up: What if someone opens a WebSocket without logging in?**
A: The `connect()` method checks authentication and calls `self.close()` if the user is not logged in, rejecting the WebSocket connection.

---

**Q8: How are frames sent — text or binary?**
A: Camera frames are sent as **binary WebSocket messages** (raw JPEG bytes). This is more efficient than base64 encoding (which would increase size by 33%). For the admin grid, frames are base64-encoded and sent as JSON text because the Channel Layer requires serializable data.

**Follow-up: What's the bandwidth requirement?**
A: At 720p, each JPEG frame is ~50-80KB. At 30fps, that's ~1.5-2.4 MB/s = ~12-20 Mbps per stream. On a LAN, this is easily handled. For WAN, you'd want frame compression or resolution reduction.

---

**Q9: What happens if multiple admins open the page?**
A: Multiple admins can connect to NotificationConsumer (they all join the "admin_group" and receive updates). For AdminGridConsumer, all connected admin browsers receive the same frame updates. The `CONNECTED_ADMINS` set tracks all admin channel names, so the heartbeat timer only fires when ALL admins disconnect.

---

**Q10: How does the system handle a teacher stopping their own camera?**
A: 
1. Teacher clicks "Stop Camera" → browser sends `{type: "camera_stop_by_teacher"}` via NotificationConsumer
2. Server updates CameraSession status to "stopped"
3. Server broadcasts to admin group: `{type: "camera_stopped_by_teacher", teacher_name: "subashk"}`
4. Admin's grid view removes that teacher's feed
5. CameraStreamConsumer is closed, finalizing any active recordings

---

### Scenario Questions

**Q: What if a teacher's internet is very slow?**
A: Frames arrive slowly, so the admin grid update rate for that teacher decreases. The ML processing still works on whatever frames arrive. Auto-reconnect handles temporary disconnections. No data corruption because WebSocket guarantees ordered delivery.

**Q: Can the system scale to 100 teachers?**
A: The WebSocket infrastructure itself can handle 1000+ connections (Daphne with async I/O). The bottleneck is GPU processing for ML. For 100 cameras, you'd need either multiple GPUs, a GPU server cluster, or process only a subset of frames per camera.

**Q: What if Redis goes down?**
A: With InMemoryChannelLayer (current setup), Redis isn't used. If Redis were used in production and went down, new WebSocket connections would fail to establish. Existing connections would continue but couldn't send group messages. A Redis Sentinel or Redis Cluster setup would provide high availability.
