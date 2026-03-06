# Person 4 — Frontend, UI/UX & Client-Side Logic

## Your Role
You built the **user-facing interface** — every HTML page, the CSS styling, the JavaScript that runs in the browser, the webcam capture, the admin camera grid, the real-time notification system on the client side, and the template structure. You make the project look good and feel responsive.

## Key Files You Own
| File | Purpose | Lines |
|------|---------|-------|
| `templates/index.html` | Landing page | ~300 |
| `templates/login.html` | Login page | ~120 |
| `templates/header.html` | Navigation bar (shared include) | ~150 |
| `templates/footer.html` | Footer (shared include) | ~80 |
| `templates/run_cameras.html` | Admin camera management dashboard | ~600 |
| `templates/teacher_cameras.html` | Teacher camera page | ~600 |
| `templates/malpractice_log.html` | Malpractice logs (admin + teacher) | ~1440 |
| `templates/upload_video.html` | Video upload + processing view | ~500 |
| `templates/manage_lecture_halls.html` | Lecture hall CRUD | ~300 |
| `templates/view_teachers.html` | Teacher list | ~120 |
| `templates/profile.html` | User profile page | ~150 |
| `templates/edit_profile.html` | Profile editing | ~120 |
| `templates/teacher_register.html` | Registration form | ~100 |
| `static/css/` | Stylesheets | varies |

---

## PART A: Everything You Built

### 1. Landing Page (index.html)
- Hero section with project title and description
- Feature cards highlighting key capabilities
- Animated statistics section
- Responsive layout for different screen sizes
- Navigation to login/register

### 2. Authentication Pages
- Login page with styled form and validation
- Teacher registration with form fields for all profile data
- Profile page showing user info, lecture hall, online status
- Profile editing with image upload
- Password change form

### 3. Admin Camera Dashboard (run_cameras.html)
- Real-time multi-camera grid layout
- WebSocket connection management (connects to NotificationConsumer + AdminGridConsumer)
- Camera start/stop controls per teacher
- "Start All" / "Stop All" buttons
- Teacher online/offline status indicators (green/red dots)
- Malpractice alert toasts (pop-up notifications)
- Camera session status display (requested/active/stopped)
- Auto-reconnect on WebSocket drop

### 4. Teacher Camera Page (teacher_cameras.html)
- Webcam capture using MediaStream API (`getUserMedia`)
- WebSocket connection to CameraStreamConsumer
- Captures JPEG frames from webcam and sends via binary WebSocket
- Displays annotated frames (with detection overlays) received back from server
- Camera permission request handling
- Camera start/stop from admin notification
- Stop-my-own-camera button

### 5. Malpractice Log Page (malpractice_log.html)
- Two views: Admin (all logs) and Teacher (reviewed logs only)
- Filter bar with 8 filter options (date, time, type, probability, source, building, faculty, assignment)
- Sort dropdown (newest/oldest/highest probability/lowest probability)
- Review toggle (AJAX) to switch between reviewed/unreviewed
- Log cards with color-coded probability badges
- Video proof viewer (modal popup with H.264 video player)
- Delete, bulk delete, select-all controls
- AI bulk action buttons (approve high, dismiss low)
- Responsive table/card layout

### 6. Video Upload Page (upload_video.html)
- Drag-and-drop file upload zone
- Lecture hall selection dropdown
- Live processing preview (MJPEG video player)
- Processing statistics display (FPS, frames processed, detections found)
- Progress indicator

### 7. Shared Components
- Navigation bar with role-based links (admin vs teacher)
- Footer with project info
- Toast notification system
- Loading spinners
- Responsive design patterns

---

## PART B: How Each Thing Works (Simple + Technical)

---

### B1. Django Template System

**Simple:** Templates are HTML files with special tags that Django fills in with real data before sending to the browser. For example, `{{ user.username }}` gets replaced with "rpranav" before the page is sent. Tags like `{% if admin %}` let us show different content to admins and teachers.

**Technical:**

Django Template Language (DTL) tags:
```html
<!-- Variable output -->
{{ variable_name }}
{{ log.malpractice }}
{{ log.probability_score|floatformat:1 }}  <!-- Filter: format to 1 decimal -->

<!-- Logic -->
{% if admin %}
    <button>Admin-only button</button>
{% else %}
    <p>Teacher view</p>
{% endif %}

<!-- Loops -->
{% for log in logs %}
    <div class="log-card">{{ log.malpractice }}</div>
{% empty %}
    <p>No logs found</p>
{% endfor %}

<!-- Template inclusion -->
{% include 'header.html' %}

<!-- CSRF Token (required for forms) -->
<form method="post">
    {% csrf_token %}
    <input type="text" name="username">
</form>
```

**Why Django's template system and not React/Vue/Angular?**
| Alternative | Why We Didn't Use It |
|-------------|---------------------|
| React | SPA framework — adds massive complexity (Node.js, webpack, API layer). Our app is server-rendered, no need for SPA |
| Vue.js | Similar to React — overkill. Would need a REST API backend instead of Django views |
| Angular | Enterprise-grade SPA. Way too heavy for our project |
| Jinja2 | Nearly identical to Django templates. Django's built-in is fine |

Server-side rendering (Django templates) is simpler: one codebase, no build step, no API layer, works immediately. We only use JavaScript for interactive features (WebSocket, camera, Ajax).

---

### B2. Webcam Capture (MediaStream API)

**Simple:** When the teacher clicks "Start Camera," the browser asks for webcam permission, then captures 30 photos per second from the webcam, converts each to JPEG, and sends it to the server via WebSocket.

**Technical:**
```javascript
// Request webcam access
const stream = await navigator.mediaDevices.getUserMedia({
    video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 30 }
    }
});

// Show preview in video element
videoElement.srcObject = stream;

// Capture frames at 30fps
const canvas = document.createElement('canvas');
canvas.width = 1280;
canvas.height = 720;
const ctx = canvas.getContext('2d');

setInterval(() => {
    // Draw current video frame to canvas
    ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
    
    // Convert canvas to JPEG blob
    canvas.toBlob((blob) => {
        // Send as binary WebSocket message
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(blob);
        }
    }, 'image/jpeg', 0.75);  // 75% quality → ~50-80KB per frame
}, 1000 / 30);  // Every 33ms = 30fps
```

**Why 75% JPEG quality?** Balance between image clarity and bandwidth. At 100% quality, each frame is ~200KB (6MB/s). At 75%, it's ~60KB (1.8MB/s). The quality loss is barely noticeable but saves 70% bandwidth.

**Why Canvas instead of MediaRecorder?** MediaRecorder produces video streams (WebM/H.264), but we need individual frames for ML processing. Canvas gives us per-frame control and JPEG conversion.

---

### B3. Admin Camera Grid

**Simple:** The admin sees a grid of small video feeds, one for each teacher who has their camera on. Each feed updates 30 times per second with the latest frame from the teacher's webcam.

**Technical:**
```javascript
// Connect to Admin Grid WebSocket
const gridWs = new WebSocket(`ws://${window.location.host}/ws/camera/admin-grid/`);

gridWs.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'camera_frame') {
        // Find or create the teacher's video tile
        let tile = document.getElementById(`teacher-${data.teacher_id}`);
        if (!tile) {
            tile = createTeacherTile(data.teacher_id, data.teacher_name);
            gridContainer.appendChild(tile);
        }
        
        // Update the image with the new frame (base64 JPEG)
        const img = tile.querySelector('img');
        img.src = `data:image/jpeg;base64,${data.frame}`;
    }
};
```

**Grid Layout (CSS Grid):**
```css
.camera-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 16px;
    padding: 16px;
}

.camera-tile {
    border: 2px solid #333;
    border-radius: 8px;
    overflow: hidden;
    position: relative;
}
```

`auto-fill` + `minmax(400px, 1fr)` means: fit as many columns as possible, each at least 400px wide. This automatically creates 1-column on mobile, 2 on tablet, 3+ on desktop.

---

### B4. Real-Time Notification System

**Simple:** When the AI detects malpractice, a pop-up toast notification appears on the admin's screen with the type of malpractice and the teacher's name. When the admin sends a camera request, the teacher sees a prompt asking for permission.

**Technical (Client-side WebSocket):**
```javascript
const notifWs = new WebSocket(`ws://${window.location.host}/ws/notifications/`);

notifWs.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch (data.type) {
        case 'camera_request':
            // Show permission prompt to teacher
            showCameraPermissionDialog(data.session_id, data.requested_by);
            break;
            
        case 'session_update':
            // Update admin's camera tile status
            updateCameraStatus(data.session_id, data.status);
            break;
            
        case 'malpractice_alert':
            // Show toast notification
            showToast(`⚠️ ${data.malpractice_type} detected in ${data.lecture_hall}!`, 'warning');
            break;
            
        case 'teacher_status':
            // Update online/offline indicator
            updateTeacherStatus(data.teacher_id, data.is_online);
            break;
    }
};
```

**Toast Notification System:**
```javascript
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${type === 'warning' ? '⚠️' : 'ℹ️'}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    document.getElementById('toast-container').appendChild(toast);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => toast.remove(), 5000);
}
```

---

### B5. Malpractice Log — Filter Bar & AJAX Toggle

**Simple:** The log page has a bar of dropdown filters. When you select "Newest First" in the Sort dropdown and click the filter button, the page reloads with logs sorted by newest date. The Review toggle button switches between reviewed and unreviewed logs WITHOUT reloading the page (using Ajax).

**Technical:**

**Filter Form (HTML):**
```html
<form method="get" action="/malpractice_log/">
    <div class="form-row">
        <select name="date"><option value="">All Dates</option>...</select>
        <select name="time"><option value="">All</option>...</select>
        <select name="malpractice_type"><option value="">All Types</option>...</select>
        <select name="sort">
            <option value="newest" {% if sort_order == 'newest' %}selected{% endif %}>Newest First</option>
            <option value="oldest" {% if sort_order == 'oldest' %}selected{% endif %}>Oldest First</option>
            <option value="prob_high" {% if sort_order == 'prob_high' %}selected{% endif %}>Highest Probability</option>
            <option value="prob_low" {% if sort_order == 'prob_low' %}selected{% endif %}>Lowest Probability</option>
        </select>
        <button type="submit">🔍 Apply Filters</button>
    </div>
</form>
```

**AJAX Review Toggle:**
```javascript
document.getElementById('reviewToggle').addEventListener('change', function() {
    const showReviewed = this.checked ? 'true' : 'false';
    const sortOrder = document.getElementById('sort').value;
    
    // Build URL with current filters preserved
    const url = `/malpractice_log/?show_reviewed=${showReviewed}&sort=${sortOrder}`;
    
    // Fetch new content without page reload
    fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.text())
    .then(html => {
        // Replace log table with new content
        document.getElementById('log-container').innerHTML = html;
    });
});
```

**Why AJAX for toggle?** Without AJAX, switching between reviewed/unreviewed would reload the entire page (including navigation, styles, scripts). AJAX replaces only the log table, making the switch feel instant.

---

### B6. Video Proof Player (Modal)

**Simple:** When the admin clicks "View" on a log, a popup window appears with a video player showing the proof clip. The video is streamed from the server in H.264 format.

**Technical:**
```html
<!-- Modal HTML -->
<div id="videoModal" class="modal">
    <div class="modal-content">
        <span class="close">&times;</span>
        <video controls autoplay id="proofVideo">
            <source src="" type="video/mp4">
        </video>
    </div>
</div>

<script>
function playProofVideo(proofPath) {
    const modal = document.getElementById('videoModal');
    const video = document.getElementById('proofVideo');
    
    // Use serve_video endpoint (handles H.264 conversion)
    video.querySelector('source').src = `/serve_video/?path=${encodeURIComponent(proofPath)}`;
    video.load();
    modal.style.display = 'block';
}
</script>
```

---

### B7. Video Upload with Live Processing Preview

**Simple:** The teacher drags a video file onto the upload area. After upload, the browser shows a live video feed of the AI processing the video — you can see the detection boxes being drawn in real-time as each frame is analyzed.

**Technical:**
```javascript
// Upload video via FormData
const formData = new FormData();
formData.append('video', fileInput.files[0]);
formData.append('lecture_hall', hallSelect.value);

const response = await fetch('/process_video/', {
    method: 'POST',
    body: formData,
    headers: { 'X-CSRFToken': csrfToken }
});

const data = await response.json();
const sessionId = data.session_id;

// Start MJPEG stream preview
const streamImg = document.getElementById('processing-preview');
streamImg.src = `/stream_video_processing/${sessionId}/`;
// Browser handles MJPEG natively — img.src with multipart response = auto-updating image

// Poll for processing stats
const statsInterval = setInterval(async () => {
    const stats = await fetch(`/get_processing_stats/${sessionId}/`).then(r => r.json());
    document.getElementById('fps').textContent = stats.fps;
    document.getElementById('frames').textContent = stats.frames_processed;
    document.getElementById('detections').textContent = stats.detections_found;
    
    if (stats.status === 'complete') {
        clearInterval(statsInterval);
        showCompletionSummary(stats);
    }
}, 1000);
```

**MJPEG in `<img>` tag:** When you set an `<img>` tag's src to an MJPEG stream URL, the browser continuously updates the image as new frames arrive. No JavaScript needed for the actual display — the browser handles it natively.

---

### B8. Responsive Design

**Simple:** The website looks good on big screens (desktops), medium screens (tablets), and small screens (phones). The layout adjusts automatically based on screen width.

**Technical (CSS Media Queries):**
```css
/* Default: desktop layout */
.filter-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
}

.log-card {
    display: grid;
    grid-template-columns: 1fr 2fr 1fr 1fr;
}

/* Tablet */
@media (max-width: 992px) {
    .log-card {
        grid-template-columns: 1fr 1fr;
    }
    
    .camera-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

/* Mobile */
@media (max-width: 576px) {
    .log-card {
        grid-template-columns: 1fr;
    }
    
    .camera-grid {
        grid-template-columns: 1fr;
    }
    
    .filter-bar {
        flex-direction: column;
    }
}
```

**Bootstrap Grid System:** We use Bootstrap's 12-column grid (`col-md-4`, `col-md-2`, etc.) for layout. `col-md-4` means "take 4 of 12 columns (33%) on medium+ screens, full width on small screens."

---

### B9. CSRF Token Handling in JavaScript

**Simple:** Django requires a security token in every form submission to prevent attacks. For regular forms, we add `{% csrf_token %}`. For JavaScript (Ajax), we read the token from a cookie and include it in the request header.

**Technical:**
```javascript
// Read CSRF token from cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(
                    cookie.substring(name.length + 1)
                );
                break;
            }
        }
    }
    return cookieValue;
}

const csrfToken = getCookie('csrftoken');

// Use in fetch requests
fetch('/review_malpractice/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify({ log_id: 15, is_malpractice: true })
});
```

**Why `CSRF_COOKIE_HTTPONLY = False`?** HTTP-only cookies can't be read by JavaScript. Since our AJAX calls need the CSRF token, the cookie must be readable. This is safe because CSRF tokens protect against cross-site attacks, not same-origin JavaScript.

---

### B10. Color-Coded Probability Badges

**Simple:** Each malpractice log shows its probability score as a colored badge: red for high probability (≥70%), yellow/orange for medium (50-69%), and green for low (<50%). This helps the admin quickly spot which detections need urgent attention.

**Technical:**
```html
{% if log.probability_score >= 70 %}
    <span class="badge badge-danger">{{ log.probability_score|floatformat:1 }}%</span>
{% elif log.probability_score >= 50 %}
    <span class="badge badge-warning">{{ log.probability_score|floatformat:1 }}%</span>
{% else %}
    <span class="badge badge-success">{{ log.probability_score|floatformat:1 }}%</span>
{% endif %}
```

```css
.badge-danger  { background: #dc3545; color: white; }  /* Red */
.badge-warning { background: #ffc107; color: black; }  /* Yellow */
.badge-success { background: #28a745; color: white; }  /* Green */
```

---

## PART C: Testing & Results

### How You Tested
1. **Cross-browser:** Chrome, Firefox, Edge — all pages, WebSocket connections, video playback
2. **Responsive testing:** Desktop (1920×1080), tablet (768×1024), mobile (375×667)
3. **WebSocket testing:** Connect/disconnect, auto-reconnect, multiple tabs
4. **Camera testing:** Permission grant/deny, camera access on different devices
5. **Filter testing:** All filter combinations, sort options, AJAX toggle
6. **Accessibility:** Keyboard navigation, form labels, color contrast

### Results
| Metric | Value |
|--------|-------|
| Page load time (initial) | < 1.5 seconds |
| WebSocket connection time | < 100ms |
| Camera frame capture rate | 30 FPS |
| AJAX toggle response time | < 200ms |
| Camera grid update latency | < 100ms (LAN) |
| Responsive breakpoints tested | 3 (desktop, tablet, mobile) |

### What Can Be Improved
1. **Dark mode** — Add toggle for dark/light theme
2. **Service Worker** — Enable offline access for log viewing
3. **WebP format** — Switch from JPEG to WebP for 30% smaller frames
4. **Virtual scrolling** — For 1000+ log entries, render only visible rows
5. **Accessibility (WCAG)** — Add ARIA labels, screen reader support

---

## PART D: Evaluation Q&A

### Core Questions

**Q1: What technologies did you use for the frontend?**
A: HTML5 for structure, CSS3 for styling (with Bootstrap 4 grid system), and vanilla JavaScript for interactivity. We use Django's template language for server-side rendering. No JavaScript frameworks (React/Vue/Angular) — we use vanilla JS with WebSocket API and MediaStream API for the interactive features.

**Follow-up: Why vanilla JS instead of React?**
A: Our app is server-rendered (Django generates HTML on the server). React is designed for Single-Page Applications where the browser renders everything. Using React would require building a separate REST API backend, adding webpack/build tools, and doubling the codebase. Vanilla JS handles our interactive needs (WebSocket, camera, Ajax) without this overhead.

---

**Q2: How does the webcam capture work?**
A: We use the MediaStream API (`navigator.mediaDevices.getUserMedia()`) to access the webcam. This returns a video stream that we display in a `<video>` element. Every 33ms (30fps), we draw the current video frame to an invisible `<canvas>`, convert it to a JPEG blob using `canvas.toBlob()`, and send the blob as a binary WebSocket message.

**Follow-up: What happens if the user denies camera permission?**
A: The browser shows a permission dialog. If denied, `getUserMedia()` rejects with a `NotAllowedError`. We catch this and display a message telling the user to enable camera access in browser settings. We also send a `camera_error` WebSocket message to notify the admin.

---

**Q3: How does the admin camera grid display work?**
A: The admin connects to the AdminGridConsumer via WebSocket. When a teacher's camera sends a frame, it's forwarded to the admin grid group. The admin's JavaScript receives each frame (base64-encoded JPEG in JSON), finds or creates an `<img>` element for that teacher, and sets `img.src = 'data:image/jpeg;base64,...'`. This updates the image 30 times per second, appearing as a live video feed.

**Follow-up: Why base64 instead of binary?**
A: The admin grid uses the Channel Layer (InMemory/Redis) to route frames. Channel Layer messages must be JSON-serializable, which requires text data. Base64 encodes binary JPEG as ASCII text. The ~33% size overhead is acceptable for a LAN setup.

---

**Q4: What is AJAX and how do you use it for the review toggle?**
A: AJAX (Asynchronous JavaScript and XML) allows the browser to send HTTP requests without reloading the page. When the admin toggles "Reviewed/Unreviewed," JavaScript sends a `fetch()` request to the server, receives new HTML, and replaces the log table content. No page reload — only the log list changes.

**Follow-up: What's the difference between `fetch()` and `XMLHttpRequest`?**
A: Both send HTTP requests from JavaScript. `fetch()` is the modern API with Promises (`async/await` support), cleaner syntax, and better error handling. `XMLHttpRequest` is the older API. We use `fetch()` throughout.

---

**Q5: How do you handle responsive design?**
A: We use CSS media queries (`@media`) and Bootstrap's grid system. Bootstrap divides the screen into 12 columns. `col-md-4` means "4 columns (33%) on medium screens and larger, full width on small screens." We have 3 breakpoints: mobile (< 576px), tablet (577-992px), and desktop (> 992px).

---

**Q6: How does the Django template system work?**
A: Templates are HTML files with special Django tags. `{{ variable }}` outputs data, `{% if condition %}` adds logic, `{% for item in list %}` creates loops. The view function passes a "context" dictionary to the template via `render(request, 'template.html', context)`. Django processes all tags server-side and sends pure HTML to the browser.

**Follow-up: What are template filters?**
A: Filters modify variables in templates. For example: `{{ log.probability_score|floatformat:1 }}` formats 72.345 as 72.3. `{{ user.get_full_name|default:user.username }}` shows the full name, or username if full name is empty. They're applied with the pipe `|` character.

---

**Q7: How does the MJPEG processing preview work?**
A: MJPEG (Motion JPEG) is a video format where each frame is a separate JPEG image. The server sends a `multipart/x-mixed-replace` HTTP response where each part is a JPEG. When we set an `<img>` tag's `src` to this URL, the browser automatically replaces the image with each new frame, creating a video-like effect. No JavaScript needed for display.

---

**Q8: How do WebSocket messages on the client side work?**
A: 
```javascript
const ws = new WebSocket('ws://host/ws/path/');
ws.onopen = () => {};      // Connection established
ws.onmessage = (e) => {};  // Message received (e.data = content)
ws.onclose = () => {};     // Connection closed
ws.onerror = () => {};     // Error occurred
ws.send(data);              // Send data (text or binary)
```
For text messages (notifications): `ws.send(JSON.stringify({type: 'camera_request', ...}))` and `JSON.parse(event.data)` on receive.
For binary messages (camera frames): `ws.send(blob)` and `event.data` is a Blob or ArrayBuffer.

---

**Q9: What is `{% csrf_token %}` and why is it needed?**
A: Django requires a CSRF (Cross-Site Request Forgery) token in every POST form. It's a unique random value per session that proves the form submission came from OUR site, not an attacker's site. In templates: `{% csrf_token %}` renders a hidden input field. In JavaScript: we read the `csrftoken` cookie and include it as `X-CSRFToken` header.

**Follow-up: What if you forget to include it?**
A: Django returns a `403 Forbidden` error. The form submission is rejected entirely.

---

**Q10: How does the template inheritance work?**
A: We use `{% include %}` to insert shared components:
```html
{% include 'header.html' %}
<main>Page-specific content</main>
{% include 'footer.html' %}
```
The header contains the navigation bar with role-based links (admin sees "Cameras", "Manage Halls"; teacher sees "My Camera", "Logs"). The footer contains copyright and project info. This avoids duplicating the same HTML across 13 pages.

---

### Scenario Questions

**Q: What if the teacher's camera resolution is very low (e.g., 320×240)?**
A: The system still works. YOLO accepts any resolution and resizes to 640×640 internally. However, detection accuracy decreases because keypoint resolution is lower. The admin grid would show a small, blurry feed but it would still function.

**Q: What if two admins open the camera page at the same time?**
A: Both receive the same WebSocket notifications and camera feeds. Both can send camera start/stop requests. There's no conflict because requests are idempotent (starting an already-started camera is a no-op). The last action wins for conflicting operations (e.g., one admin starts, another stops).

**Q: What if JavaScript is disabled in the browser?**
A: The base pages (login, log list, profile) would still load because they're server-rendered HTML. However, the camera features, WebSocket notifications, AJAX toggle, and video preview would not work since they depend on JavaScript. We don't support JS-disabled browsers because real-time features fundamentally require JavaScript.

**Q: How does the browser handle 30 images per second in the grid?**
A: Setting `img.src` to a data URI is extremely fast (< 1ms per frame). The browser's rendering engine efficiently handles image replacement. With 3 teachers at 30fps = 90 image updates/second, which is well within modern browser capabilities. For 10+ teachers, performance might degrade, and we'd switch to canvas-based rendering.
