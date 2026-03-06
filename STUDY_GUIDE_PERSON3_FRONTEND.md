# STUDY GUIDE — PERSON 3: Frontend / UI / Client-Side Logic

## AI Invigilator — B.Tech Final Year Project Evaluation Guide

---

# PART A — WORK ASSIGNMENT & SCOPE

## A.1 What You "Built"

You are responsible for the **entire visual interface and client-side behaviour** of the AI Invigilator system. This covers:

| Area | Files | Lines (approx.) |
|------|-------|-----------------|
| Shared Layout | `header.html`, `footer.html` | ~230 |
| Landing Page | `index.html` | 344 |
| Authentication | `login.html`, `teacher_register.html` | ~190 |
| Malpractice Log (Core Data Page) | `malpractice_log.html` | 1,427 |
| Admin Camera Dashboard | `run_cameras.html` | 860 |
| Teacher Camera Page | `teacher_cameras.html` | 783 |
| Video Upload & Processing | `upload_video.html` | 619 |
| Profile & Settings | `profile.html`, `edit_profile.html`, `change_password.html` | ~420 |
| Admin Management | `manage_lecture_halls.html`, `view_teachers.html` | ~530 |
| Design System | `static/css/theme.css` | 1,875 |
| Utility JS | `static/js/main.js` | 100 |
| **TOTAL** | **15 files** | **~7,400 lines** |

## A.2 Technology Stack (Frontend)

| Technology | Version | Role |
|-----------|---------|------|
| **Bootstrap** | 4.5.2 | Responsive grid, components (modals, dropdowns, alerts) |
| **jQuery** | 3.6.0 | DOM manipulation, AJAX (`$.ajax`), event binding |
| **GSAP** | 3.12.5 + ScrollTrigger | Scroll-triggered reveal animations, hero entrance, rotating rings |
| **Font Awesome** | 6.5.1 | 70+ icons across all pages |
| **Google Fonts** | Inter + JetBrains Mono | Body text + monospace data display |
| **WebSocket API** | Browser native | Real-time bidirectional communication for camera streams |
| **MediaDevices API** | `getUserMedia` | Webcam access for teacher camera streaming |
| **Canvas API** | `toBlob()` | Frame capture from video → JPEG blob for transmission |
| **Fetch API** | Native | AJAX for filtering, reviewing, deleting, AI actions |
| **URL API** | `createObjectURL / revokeObjectURL` | Binary frame rendering + memory management |

## A.3 Template Architecture

The project uses a Django **include-based** composition pattern (NOT `{% extends %}` template inheritance):

```
Every page:
  {% include 'header.html' %}   ← Navbar + CDN resources
  {% block content %}           ← Page-specific content
  {% endblock %}
  (footer is included inside some pages or via header)
```

Each page includes its own **inline `<style>`** and **inline `<script>`** blocks — functioning like scoped CSS/JS components. This approach means:
- No build step (no Webpack/Vite)
- Each page is self-contained
- The global design system lives in `theme.css`

---

# PART B — IMPLEMENTATION DEEP-DIVE

## B.1 CSS Design System (`theme.css` — 1,875 lines)

### B.1.1 Design Tokens (CSS Custom Properties)

The entire colour scheme is governed by ~60 CSS variables declared in `:root`:

```css
:root {
  /* Background palette — Dark theme */
  --bg-primary:     #0a0a1a;      /* Deepest background */
  --bg-secondary:   #111827;      /* Slightly lighter */
  --bg-surface:     #1a1a2e;      /* Card/panel surface */
  --bg-elevated:    #1e293b;      /* Elevated elements */
  --bg-card:        rgba(26, 26, 46, 0.6);
  --bg-glass:       rgba(17, 24, 39, 0.7);
  --bg-glass-heavy: rgba(10, 10, 26, 0.9);

  /* Accent colours */
  --accent-cyan:    #00d4ff;      /* Primary accent */
  --accent-purple:  #7c3aed;      /* Secondary accent */
  --accent-gradient: linear-gradient(135deg, #00d4ff 0%, #7c3aed 100%);

  /* Semantic states */
  --danger:  #ef4444;   --danger-dim:  rgba(239,68,68,0.1);
  --success: #10b981;   --success-dim: rgba(16,185,129,0.1);
  --warning: #f59e0b;   --warning-dim: rgba(245,158,11,0.1);
  --info:    #3b82f6;   --info-dim:    rgba(59,130,246,0.1);

  /* Typography */
  --font-body: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* Spacing & Radii */
  --radius-sm: 8px;  --radius-md: 12px;  --radius-lg: 16px; --radius-xl: 20px;

  /* Glow effects */
  --glow-cyan:   0 0 30px rgba(0, 212, 255, 0.15);
  --glow-subtle: 0 8px 32px rgba(0, 0, 0, 0.3);
}
```

**Why this matters for viva:** Design tokens make the entire theme changeable from one place. Changing `--accent-cyan` from `#00d4ff` to a different colour would propagate across all 15 templates instantly.

### B.1.2 Glassmorphism

The signature UI effect is **glassmorphism** — semi-transparent backgrounds with blur:

```css
.glass-card {
  background: var(--bg-glass);            /* rgba(17, 24, 39, 0.7) */
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
}
```

This technique layers the `backdrop-filter: blur()` CSS property so that content behind the card is visually blurred, creating a frosted glass effect. The `-webkit-` prefix ensures Safari compatibility.

### B.1.3 Animated Background Mesh

The global background uses layered radial gradients:

```css
.bg-mesh {
  position: fixed;
  background:
    radial-gradient(ellipse at 20% 50%, rgba(0,212,255,0.04) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, rgba(124,58,237,0.04) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 80%, rgba(0,212,255,0.02) 0%, transparent 50%);
  pointer-events: none;
}
```

### B.1.4 Dark Theme Bootstrap Overrides

Since Bootstrap 4 doesn't have a native dark mode, `theme.css` overrides ~40 Bootstrap component defaults:

- **`.form-control`** → dark background, cyan focus ring
- **`.btn-primary`** → replaces solid blue with `accent-gradient`
- **`.table`** → header uses `--bg-surface`, striped rows use `rgba(255,255,255,0.02)`
- **`.dropdown-menu`** → dark background + `dropdown-enter` animation
- **`.modal-content`** → dark surface, custom border
- **`.alert-*`** → Uses semantic `--danger-dim`, `--success-dim` etc.

### B.1.5 Custom Component Classes

| Class | Used In | Purpose |
|-------|---------|---------|
| `.btn-accent` | Multiple | Gradient button with hover lift |
| `.btn-accent-outline` | Index | Outlined cyan button |
| `.btn-glass` | Camera pages | Transparent button with backdrop-blur |
| `.btn-danger-dark` | Delete buttons | Red-tinted dark button |
| `.btn-ripple` | Buttons | CSS-only ripple effect on click |
| `.badge-cyber` | Malpractice log | Monospace pill badges |
| `.badge-high/medium/low` | Probability column | Red/yellow/green probability indicators |
| `.feature-card` | Index | Card with hover lift + gradient top-border reveal |
| `.process-step` | Index | Numbered process cards |
| `.skeleton` | Loading states | CSS shimmer loading animation |
| `.pulse-live` | Live indicators | Pulsing green dot animation |

### B.1.6 Responsive Design

```css
@media (max-width: 768px) {
  .hero-title { font-size: 2rem; }
  .section-dark, .section-surface { padding: 3rem 0; }
  .navbar-dark-theme { padding: 0.6rem 1rem; }
  .stat-number { font-size: 1.75rem; }
}

@media (max-width: 576px) {
  .login-card-dark { padding: 1.5rem; }
  .hero-actions { flex-direction: column; }
}
```

Hero title uses `clamp()` for fluid scaling: `font-size: clamp(2.5rem, 6vw, 4.5rem)`.

---

## B.2 Shared Navbar (`header.html` — 147 lines)

### B.2.1 CDN Resources Loaded

```html
<!-- CSS -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="{% static 'css/theme.css' %}">

<!-- JS (at bottom) -->
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.1/dist/umd/popper.min.js"></script>
<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js"></script>
```

### B.2.2 Role-Based Navigation

The navbar renders different links based on authentication status and role:

```django
{% if request.user.is_authenticated %}
  {% if request.user.is_superuser %}
    <!-- ADMIN NAV: Home, Logs, Halls, View Teachers, Cameras, Upload -->
    <a href="{% url 'malpractice_log' %}">Malpractice Logs</a>
    <a href="{% url 'manage_lecture_halls' %}">Lecture Halls</a>
    <a href="{% url 'view_teachers' %}">View Teachers</a>
    <a href="{% url 'run_cameras' %}">Run Cameras</a>
    <a href="{% url 'upload_video' %}">Upload Video</a>
  {% else %}
    <!-- TEACHER NAV: Home, Logs, Camera, Upload -->
    <a href="{% url 'malpractice_log' %}">Malpractice Logs</a>
    <a href="{% url 'teacher_cameras' %}">Camera</a>
    <a href="{% url 'upload_video' %}">Upload Video</a>
  {% endif %}
  <!-- Profile dropdown with My Profile + Logout -->
{% else %}
  <!-- Login button only -->
{% endif %}
```

### B.2.3 Active Link Highlighting

```django
<a class="nav-link {% if request.resolver_match.url_name == 'malpractice_log' %}active{% endif %}"
   href="{% url 'malpractice_log' %}">
```

Uses Django's `request.resolver_match.url_name` to compare the current URL name against each nav link and conditionally add the `.active` class.

### B.2.4 Navbar Scroll Effect

```javascript
window.addEventListener('scroll', function() {
  const navbar = document.querySelector('.navbar-dark-theme');
  if (window.scrollY > 50) {
    navbar.classList.add('scrolled');
  } else {
    navbar.classList.remove('scrolled');
  }
});
```

When scrolled >50px, the navbar shrinks padding and increases background opacity:
```css
.navbar-dark-theme.scrolled {
  padding: 0.5rem 2rem;
  background: rgba(10, 10, 26, 0.95) !important;
}
```

---

## B.3 Landing Page (`index.html` — 344 lines)

### B.3.1 Page Sections

1. **Hero** — Full viewport, gradient text title, animated rings visual, conditional CTAs
2. **Stats Counter** — 4 stat items: 7 Detection Types, Real-Time Processing, 5 AI Models, CUDA GPU
3. **About** — Two-column layout with image and feature items
4. **Features** — 7 feature cards in responsive grid (each detection type)
5. **How It Works** — 4-step process (Connect → Analyze → Detect → Alert)
6. **CTA** — Call to action with glass card + glow effect

### B.3.2 GSAP Scroll Animations

```javascript
// Register the ScrollTrigger plugin
gsap.registerPlugin(ScrollTrigger);

// Reveal-up animation: Elements slide up and fade in
gsap.utils.toArray('.reveal-up').forEach(el => {
  gsap.fromTo(el,
    { y: 40, opacity: 0 },
    {
      y: 0, opacity: 1, duration: 0.8, ease: 'power2.out',
      scrollTrigger: {
        trigger: el,
        start: 'top 85%',    // Trigger when 85% viewport
        toggleActions: 'play none none none'
      }
    }
  );
});

// Other directions: reveal-left, reveal-right, reveal-scale
// Each uses different starting positions (x:-40, x:40, scale:0.9)
```

**Hero entrance animation** (runs immediately, not scroll-triggered):
```javascript
gsap.from('.hero-badge', { y: 30, opacity: 0, duration: 0.8, delay: 0.2 });
gsap.from('.hero-title', { y: 40, opacity: 0, duration: 1, delay: 0.4 });
gsap.from('.hero-subtitle', { y: 30, opacity: 0, duration: 0.8, delay: 0.7 });
gsap.from('.hero-actions', { y: 20, opacity: 0, duration: 0.8, delay: 1.0 });
```

**Rotating rings:**
```javascript
gsap.to('.ring-1', { rotation: 360, duration: 20, repeat: -1, ease: 'none' });
gsap.to('.ring-2', { rotation: -360, duration: 25, repeat: -1, ease: 'none' });
gsap.to('.ring-3', { rotation: 360, duration: 30, repeat: -1, ease: 'none' });
```

**Fallback** — If GSAP fails to load, CSS ensures elements are visible:
```javascript
// In a try-catch or error handler
document.querySelectorAll('.reveal-up, .reveal-left, .reveal-right, .reveal-scale')
  .forEach(el => { el.style.opacity = '1'; el.style.transform = 'none'; });
```

### B.3.3 Conditional CTAs

```django
{% if request.user.is_authenticated %}
  {% if request.user.is_superuser %}
    <a href="{% url 'run_cameras' %}" class="btn-accent">Launch Cameras</a>
  {% else %}
    <a href="{% url 'teacher_cameras' %}" class="btn-accent">Open Camera</a>
  {% endif %}
{% else %}
  <a href="{% url 'addlogin' %}" class="btn-accent">Get Started</a>
{% endif %}
```

---

## B.4 Authentication Pages

### B.4.1 Login Page (`login.html` — ~90 lines)

- **Glass card** centred in viewport with gradient top-border
- Form posts to `{% url 'addlogin' %}` with `{% csrf_token %}`
- **Password toggle** — JavaScript swaps input type and eye icon:
  ```javascript
  function togglePassword() {
    const input = document.getElementById('password');
    const icon = document.getElementById('toggleIcon');
    if (input.type === 'password') {
      input.type = 'text';
      icon.classList.replace('fa-eye', 'fa-eye-slash');
    } else {
      input.type = 'password';
      icon.classList.replace('fa-eye-slash', 'fa-eye');
    }
  }
  ```
- Error display: Django messages rendered in `.alert-danger-dark` div

### B.4.2 Registration (`teacher_register.html` — ~100 lines)

- `enctype="multipart/form-data"` — Required for profile picture upload
- Fields: first_name, last_name, email, username, password, phone, profile_picture (optional)
- Posts to `{% url 'addteacher' %}`

---

## B.5 Malpractice Log (`malpractice_log.html` — 1,427 lines)

This is the **most complex page** in the entire application with ~300 lines of CSS, ~500 lines of HTML, and ~500 lines of JavaScript.

### B.5.1 UI Components

#### Filter Bar
**Admin view** (2-row, 11+ filters):
- Teacher select, Lecture Hall select, Detection type, Source (live/recorded), Date range (from/to), Probability (high/medium/low), Confidence min/max, Session ID, Search text, Apply button

**Teacher view** (1-row, 6 filters):
- Detection type, Source, Date range, Probability, Apply button

All filters use Django template tags to pre-populate from current query parameters:
```django
<option value="{{ type }}" {% if type == detection_type_filter %}selected{% endif %}>
```

#### Review Toggle
A custom CSS slider switch (not Bootstrap's):
```html
<label class="review-toggle-slider">
  <input type="checkbox" id="reviewToggle" {% if review_filter == 'reviewed' %}checked{% endif %}>
  <span class="slider-track"><span class="slider-thumb"></span></span>
</label>
```

Toggle triggers AJAX page swap (see B.5.3).

#### Data Table
13 columns: Checkbox, Sl.No, Teacher, Hall, Type, Probability, Confidence, Source, Date, Proof (video/image), Reviewed, AI Actions, Delete

- **Probability badges**: Color-coded (red >0.7, yellow 0.4–0.7, green <0.4)
- **Source badges**: `live` = red pulsing dot, `recorded` = purple

### B.5.2 Review Toggle AJAX

```javascript
document.getElementById('reviewToggle').addEventListener('change', function() {
  const newFilter = this.checked ? 'reviewed' : 'not_reviewed';
  const url = new URL(window.location);
  url.searchParams.set('review', newFilter);

  fetch(url.toString())
    .then(response => response.text())
    .then(html => {
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const newTable = doc.querySelector('.table-container');
      document.querySelector('.table-container').innerHTML = newTable.innerHTML;
      history.pushState(null, '', url);   // Update URL without reload
    });
});
```

**Key technique:** Uses `DOMParser` to parse the full HTML response and extract just the `.table-container` section, replacing the existing table without a full page reload.

### B.5.3 AJAX Filter Submission

```javascript
document.getElementById('filterForm').addEventListener('submit', function(e) {
  e.preventDefault();
  const formData = new FormData(this);
  const url = new URL(window.location.pathname, window.location.origin);
  formData.forEach((value, key) => { if (value) url.searchParams.set(key, value); });

  fetch(url.toString())
    .then(response => response.text())
    .then(html => {
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      document.querySelector('.table-container').innerHTML =
        doc.querySelector('.table-container').innerHTML;
      history.pushState(null, '', url);
    });
});
```

### B.5.4 Selection Mode (Batch Operations)

```javascript
function toggleSelectionMode() {
  selectionMode = !selectionMode;
  document.querySelectorAll('.select-col').forEach(col => {
    col.style.display = selectionMode ? 'table-cell' : 'none';
  });
  document.getElementById('selectionControls').style.display =
    selectionMode ? 'flex' : 'none';
}

function selectAll() {
  document.querySelectorAll('.log-checkbox').forEach(cb => cb.checked = true);
}

function deselectAll() {
  document.querySelectorAll('.log-checkbox').forEach(cb => cb.checked = false);
}
```

When the user clicks "Delete Selected", the selected IDs are collected and submitted:
```javascript
function deleteSelected() {
  const ids = Array.from(document.querySelectorAll('.log-checkbox:checked'))
    .map(cb => cb.value);
  document.getElementById('selectedLogIds').value = ids.join(',');
  document.getElementById('selectedLogsCount').textContent = ids.length;
  $('#deleteSelectedModal').modal('show');
}
```

### B.5.5 Video Playback

```javascript
function playVideo(url) {
  const video = document.getElementById('videoPlayer');
  video.innerHTML = '';  // Clear previous sources
  const source = document.createElement('source');
  source.src = url;
  source.type = 'video/mp4';
  video.appendChild(source);
  video.load();
  video.play();
  $('#videoModal').modal('show');
}
```

Videos are served through a dedicated `/serve_video/<filename>` endpoint (Django view handles range requests for video streaming).

### B.5.6 AI Bulk Action

```javascript
let currentAIAction = '';

function showAIActionModal(action) {
  currentAIAction = action;
  // Set modal title and description based on action type
  document.getElementById('aiActionTitle').textContent = '...';
  document.getElementById('aiActionDescription').textContent = '...';
  $('#aiActionModal').modal('show');
}

function executeAIAction() {
  fetch('/ai_bulk_action/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': '{{ csrf_token }}'
    },
    body: JSON.stringify({ action: currentAIAction })
  })
  .then(response => response.json())
  .then(data => {
    $('#aiActionModal').modal('hide');
    if (data.success) location.reload();
    else alert('Error: ' + data.error);
  });
}
```

### B.5.7 Row Delete with Animation

```javascript
function deleteMalpractice(logId) {
  if (!confirm('Delete this log?')) return;

  fetch(`/delete_malpractice/${logId}/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': '{{ csrf_token }}' }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      const row = document.querySelector(`tr[data-log-id="${logId}"]`);
      row.style.transition = 'opacity 0.3s, transform 0.3s';
      row.style.opacity = '0';
      row.style.transform = 'translateX(30px)';
      setTimeout(() => row.remove(), 300);   // Remove after animation
    }
  });
}
```

### B.5.8 Review Malpractice

```javascript
function reviewMalpractice(button, decision) {
  const row = button.closest('tr');
  const logId = row.getAttribute('data-log-id');
  const downloadLink = row.querySelector('a[download]');
  const proof = downloadLink ? downloadLink.getAttribute('href').replace('/media/', '') : '';

  fetch('/review_malpractice/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': '{{ csrf_token }}'
    },
    body: JSON.stringify({ proof: proof, decision: decision })
  })
  .then(response => response.json())
  .then(data => {
    if (data.success && currentReviewFilter === "not_reviewed") {
      // Animate row out: fade + slide right
      row.style.transition = "opacity 0.3s ease, transform 0.3s ease";
      row.style.opacity = "0";
      row.style.transform = "translateX(30px)";
      setTimeout(() => row.remove(), 300);
    }
  });
}
```

### B.5.9 Complete Review Session

Admin can select a teacher and complete a review session, which triggers backend to:
- Make confirmed logs visible to the teacher
- Send summary email + SMS notification
- Create a review session record

```javascript
function completeReviewSession() {
  const teacherSelect = document.getElementById('reviewTeacher');
  const teacherId = teacherSelect.value;
  const hallId = teacherSelect.options[teacherSelect.selectedIndex]
                   .getAttribute('data-hall-id');
  const reviewDate = document.getElementById('reviewDate').value;

  const payload = { teacher_id: parseInt(teacherId), hall_id: parseInt(hallId) };
  if (reviewDate) payload.date = reviewDate;

  fetch('/complete_review_session/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': '{{ csrf_token }}' },
    body: JSON.stringify(payload)
  })
  .then(response => response.json())
  .then(data => {
    $('#completeReviewModal').modal('hide');
    alert(data.success ? data.message : 'Error: ' + data.error);
  });
}
```

---

## B.6 Admin Camera Dashboard (`run_cameras.html` — 860 lines)

This is the **real-time command centre** for the admin to manage all teacher cameras.

### B.6.1 Page Layout

```
┌─────────────────────────────────────────────┐
│         Stats Bar (Total/Online/Streaming)   │
├─────────────────────────────────────────────┤
│  Section 1: Camera Controls                  │
│  [Start All] [Stop All]                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│  │ T1 ● │ │ T2 ● │ │ T3 ● │ │ T4 ● │       │ ← Teacher tiles
│  │ Start│ │ Stop │ │ Start│ │ Start│       │
│  └──────┘ └──────┘ └──────┘ └──────┘       │
├─────────────────────────────────────────────┤
│  Section 2: Live Camera Grid                 │
│  ┌─────────────┐ ┌─────────────┐            │
│  │ [LIVE] T1   │ │ [LIVE] T3   │            │ ← Camera feeds
│  │  <img/>     │ │  <img/>     │            │
│  └─────────────┘ └─────────────┘            │
├─────────────────────────────────────────────┤
│  Section 3: Live Detection Alerts            │
│  • Phone detected - Teacher1 - 0.92 - 10:30 │
│  • Looking away - Teacher2 - 0.87 - 10:31   │
└─────────────────────────────────────────────┘
```

### B.6.2 Dual WebSocket Architecture

The admin page maintains **two** WebSocket connections simultaneously:

#### 1. Notification Socket (`notifSocket`)

```javascript
const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
const notifSocket = new WebSocket(
  wsScheme + '://' + window.location.host + '/ws/notifications/'
);
```

**Messages handled:**
| Message Type | Action |
|-------------|--------|
| `initial_state` | Populate teacher list + statuses |
| `teacher_status` | Update teacher tile (online/offline) |
| `session_update` | Update session status (requested/streaming/denied/stopped) |
| `bulk_session_update` | Update multiple sessions at once |
| `malpractice_alert` | Prepend to detection alert feed |
| `camera_stopped_by_teacher` | Update tile to show teacher self-stopped |
| `camera_error` | Show error toast with retry button |

#### 2. Grid Socket (`gridSocket`)

```javascript
const gridSocket = new WebSocket(
  wsScheme + '://' + window.location.host + '/ws/camera/admin-grid/'
);
```

**Handles binary frames** — the core of live video display.

### B.6.3 Binary Frame Protocol (Client-Side)

The most technically impressive piece of frontend code:

```javascript
gridSocket.onmessage = function(e) {
  if (e.data instanceof Blob) {
    // BINARY: First 4 bytes = teacher ID, rest = JPEG frame
    e.data.arrayBuffer().then(buffer => {
      const view = new DataView(buffer);
      const teacherId = view.getUint32(0);    // Extract 4-byte big-endian teacher ID
      const frameBlob = new Blob([buffer.slice(4)], { type: 'image/jpeg' });
      const url = URL.createObjectURL(frameBlob);

      const img = document.querySelector(`#cam-img-${teacherId}`);
      if (img) {
        // Memory management: revoke previous ObjectURL
        if (_camFrameState[teacherId]) {
          URL.revokeObjectURL(_camFrameState[teacherId]);
        }
        _camFrameState[teacherId] = url;
        img.src = url;
      }
    });
  } else {
    // JSON: stream_started, stream_ended, active_streams
    const data = JSON.parse(e.data);
    // Handle stream lifecycle events
  }
};
```

**Binary frame structure:**
```
Byte 0-3:  Teacher ID (uint32, big-endian)
Byte 4-N:  JPEG image data (ML-processed frame)
```

**Memory management** is critical here — without `URL.revokeObjectURL()`, each frame creates a new object URL that never gets garbage collected, leading to massive memory leaks. The `_camFrameState` object tracks the last URL per teacher:

```javascript
const _camFrameState = {};  // { teacherId: lastObjectURL }
```

### B.6.4 Dynamic Teacher Tile Rendering

```javascript
function renderTeachers(teachers) {
  const grid = document.getElementById('teacherGrid');
  grid.innerHTML = '';
  teachers.forEach(t => {
    const tile = document.createElement('div');
    tile.className = 'teacher-tile';
    tile.id = `tile-${t.id}`;
    tile.innerHTML = `
      <div class="teacher-name">${t.name}</div>
      <div class="teacher-hall">${t.hall || 'No Hall'}</div>
      <span class="status-dot ${getStatusClass(t.status)}"></span>
      <button class="btn btn-sm" onclick="startCamera(${t.id})">Start</button>
      <button class="btn btn-sm" onclick="stopCamera(${t.id})">Stop</button>
    `;
    grid.appendChild(tile);
  });
}
```

**Status dot colours:**
| Status | CSS Class | Colour | Effect |
|--------|-----------|--------|--------|
| online | `.status-online` | Green | Solid |
| streaming | `.status-streaming` | Cyan | Pulse animation |
| requested | `.status-requested` | Yellow/warning | Solid |
| denied | `.status-denied` | Red | Solid |
| offline | `.status-offline` | Gray | 50% opacity |

### B.6.5 Camera Grid (Add/Remove Cells)

```javascript
function addCameraCell(teacherId, teacherName) {
  const grid = document.getElementById('cameraGrid');
  const cell = document.createElement('div');
  cell.className = 'camera-cell';
  cell.id = `cam-cell-${teacherId}`;
  cell.innerHTML = `
    <div class="cam-label">${teacherName} <span class="live-badge">LIVE</span></div>
    <img id="cam-img-${teacherId}" src="" alt="Camera Feed">
  `;
  grid.appendChild(cell);
}

function removeCameraCell(teacherId) {
  const cell = document.getElementById(`cam-cell-${teacherId}`);
  if (cell) {
    // Cleanup object URL before removing
    if (_camFrameState[teacherId]) {
      URL.revokeObjectURL(_camFrameState[teacherId]);
      delete _camFrameState[teacherId];
    }
    cell.remove();
  }
}
```

**CSS Grid layout** for auto-filling available space:
```css
.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}
```

### B.6.6 Toast Notification System

```javascript
function showToast(type, message, duration = 4000) {
  const colours = {
    info:    { bg: 'var(--info-dim)',    border: 'var(--info)',    icon: 'fa-info-circle' },
    error:   { bg: 'var(--danger-dim)',  border: 'var(--danger)',  icon: 'fa-exclamation-circle' },
    warning: { bg: 'var(--warning-dim)', border: 'var(--warning)', icon: 'fa-exclamation-triangle' },
    success: { bg: 'var(--success-dim)', border: 'var(--success)', icon: 'fa-check-circle' }
  };

  const toast = document.createElement('div');
  toast.className = 'toast-notification';
  toast.innerHTML = `<i class="fas ${colours[type].icon}"></i> ${message}`;
  document.getElementById('toastContainer').appendChild(toast);

  if (duration > 0) {
    setTimeout(() => toast.remove(), duration);
  }
}
```

`showCameraErrorToast()` creates a persistent toast with a retry button.

### B.6.7 Camera Control Commands

```javascript
function startCamera(teacherId) {
  notifSocket.send(JSON.stringify({
    type: 'camera_request',
    teacher_id: teacherId
  }));
}

function stopCamera(teacherId) {
  notifSocket.send(JSON.stringify({
    type: 'camera_stop',
    teacher_id: teacherId
  }));
}

function startAllCameras() {
  notifSocket.send(JSON.stringify({ type: 'start_all_cameras' }));
}

function stopAllCameras() {
  notifSocket.send(JSON.stringify({ type: 'stop_all_cameras' }));
}
```

### B.6.8 Sleep/Wake Reconnection

```javascript
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    // Page is visible again (laptop wake / tab focus)
    if (notifSocket.readyState !== WebSocket.OPEN) {
      connectNotifications();
    }
    if (gridSocket.readyState !== WebSocket.OPEN) {
      connectGrid();
    }
  }
});

// Auto-reconnect on WebSocket close
notifSocket.onclose = function() {
  setTimeout(connectNotifications, 3000);
};
```

---

## B.7 Teacher Camera Page (`teacher_cameras.html` — 783 lines)

### B.7.1 Page Layout

```
┌─────────────────────────────────────────────┐
│  (Conditional: "No hall assigned" banner)     │
│  Hall Info: Building X - Hall Y               │
├─────────────────────────────────────────────┤
│  Status Banner: IDLE / REQUESTED / ACTIVE     │
├─────────────────────────────────────────────┤
│  Camera View Card                             │
│  ┌─────────────────────────────────────────┐ │
│  │  <video id="rawVideo">                  │ │ ← getUserMedia feed
│  │  <canvas> (hidden)                      │ │ ← Frame capture
│  │  <img id="processedImg"> (overlay)      │ │ ← ML-processed frame
│  │  ● LIVE         FPS: 18.5              │ │
│  └─────────────────────────────────────────┘ │
│  [Stop Camera]                                │
├─────────────────────────────────────────────┤
│  Detection Log                                │
│  • Phone detected - 0.89 - 10:32:15          │
│  • Looking away - 0.76 - 10:32:20            │
└─────────────────────────────────────────────┘
```

### B.7.2 WebSocket Flow

```
Admin sends "camera_request" via notifSocket
         ↓
Teacher receives "camera_request" → showConfirmModal()
         ↓
Teacher clicks Accept → respondToRequest('accept')
         ↓
Server sends "camera_approved" to teacher
         ↓
Teacher's startStreaming() runs:
  1. getUserMedia({video: {width:1280, height:720}})
  2. Opens streamSocket (ws/camera/stream/<teacher_id>/)
  3. setInterval(sendFrame, 1000/20) — 20 FPS
         ↓
Each frame: canvas.toBlob → streamSocket.send(blob)
         ↓
Server processes frame through ML → sends back processed frame as binary blob
         ↓
Teacher displays processed frame as ML overlay image
```

### B.7.3 Webcam Access (`getUserMedia`)

```javascript
function startStreaming() {
  navigator.mediaDevices.getUserMedia({
    video: { width: 1280, height: 720, facingMode: 'user' },
    audio: false    // No audio needed for proctoring
  })
  .then(stream => {
    webcamStream = stream;
    rawVideo.srcObject = stream;
    rawVideo.play();
    openStreamSocket();
  })
  .catch(error => {
    // Map browser errors to human-readable reasons
    let reason = 'unknown_error';
    switch (error.name) {
      case 'NotAllowedError':   reason = 'permission_denied'; break;
      case 'NotFoundError':     reason = 'no_camera_hardware'; break;
      case 'NotReadableError':  reason = 'camera_in_use'; break;
      default:                  reason = 'hardware_error';
    }
    // Send error back to admin
    notifSocket.send(JSON.stringify({
      type: 'camera_error',
      reason: reason,
      detail: error.message
    }));
  });
}
```

### B.7.4 Frame Capture at 20 FPS

```javascript
// Using setInterval, NOT requestAnimationFrame
sendInterval = setInterval(sendFrame, 1000 / 20);  // 50ms interval = 20 FPS

function sendFrame() {
  if (!streamSocket || streamSocket.readyState !== WebSocket.OPEN) return;
  if (!rawVideo.videoWidth) return;  // Video not ready yet

  canvas.width = rawVideo.videoWidth;
  canvas.height = rawVideo.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(rawVideo, 0, 0);

  canvas.toBlob(blob => {
    if (blob && streamSocket.readyState === WebSocket.OPEN) {
      streamSocket.send(blob);   // Send raw JPEG binary
    }
  }, 'image/jpeg', 0.65);    // 65% JPEG quality — balances quality vs bandwidth
}
```

**Why `setInterval` instead of `requestAnimationFrame`?**
`requestAnimationFrame` is throttled to 0fps or 1fps when the browser tab is in the background. Since the teacher's camera should keep streaming even if they switch tabs briefly, `setInterval` is used instead — it continues running at approximately the desired rate.

### B.7.5 ML Overlay Display

```javascript
streamSocket.onmessage = function(e) {
  if (e.data instanceof Blob) {
    // Server sent back the ML-processed frame as binary
    const url = URL.createObjectURL(e.data);
    processedImg.onload = function() {
      URL.revokeObjectURL(url);   // Free memory after image loads
    };
    processedImg.src = url;
    frameCount++;
    updateFPS();
  } else {
    // JSON: detection_alert, session_update, etc.
    const data = JSON.parse(e.data);
    if (data.type === 'detection') {
      appendDetectionLog(data);
    }
  }
};
```

The ML overlay `<img>` is positioned absolutely over the raw `<video>`:
```css
.camera-preview {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
}
#processedImg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
```

### B.7.6 FPS Counter

```javascript
let frameCount = 0;
let lastFPSTime = performance.now();

function updateFPS() {
  if (frameCount >= 30) {
    const now = performance.now();
    const elapsed = (now - lastFPSTime) / 1000;
    const fps = (frameCount / elapsed).toFixed(1);
    document.getElementById('fpsDisplay').textContent = `FPS: ${fps}`;
    frameCount = 0;
    lastFPSTime = now;
  }
}
```

Measures FPS every 30 frames for smooth display.

### B.7.7 Confirmation Modal (Custom, not Bootstrap)

```javascript
function showConfirmModal(adminName) {
  document.getElementById('confirmText').textContent =
    `${adminName} is requesting to activate your camera.`;
  document.getElementById('confirmModal').classList.add('show');
}

function respondToRequest(response) {
  document.getElementById('confirmModal').classList.remove('show');
  notifSocket.send(JSON.stringify({
    type: 'camera_response',
    response: response     // 'accept' or 'deny'
  }));
  if (response === 'accept') {
    startStreaming();
  }
}
```

CSS uses a custom overlay (not Bootstrap modal):
```css
.confirm-modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.7);
  display: none;
  z-index: 10000;
}
.confirm-modal-overlay.show { display: flex; }
```

### B.7.8 Stop Camera & Cleanup

```javascript
function stopStreaming() {
  activeSessionId = null;  // MUST clear first to prevent auto-reconnect

  if (sendInterval) {
    clearInterval(sendInterval);
    sendInterval = null;
  }
  if (streamSocket) {
    streamSocket.close();
    streamSocket = null;
  }
  if (webcamStream) {
    webcamStream.getTracks().forEach(track => track.stop());  // Release camera
    webcamStream = null;
  }
  rawVideo.srcObject = null;
  processedImg.src = '';
  // Reset UI to idle state
}

function teacherStopCamera() {
  stopStreaming();
  notifSocket.send(JSON.stringify({ type: 'camera_stop_by_teacher' }));
}
```

### B.7.9 `beforeunload` — Graceful Shutdown

```javascript
window.addEventListener('beforeunload', function() {
  if (activeSessionId) {
    notifSocket.send(JSON.stringify({ type: 'camera_stop_by_teacher' }));
  }
});
```

This ensures that if the teacher closes the tab or navigates away, the admin is notified that the camera session ended.

---

## B.8 Video Upload Page (`upload_video.html` — 619 lines)

### B.8.1 Drag-and-Drop Upload

```javascript
const dropZone = document.getElementById('dropZone');

dropZone.addEventListener('dragover', function(e) {
  e.preventDefault();
  $(this).addClass('dragover');    // Visual highlight
});

dropZone.addEventListener('dragleave', function() {
  $(this).removeClass('dragover');
});

dropZone.addEventListener('drop', function(e) {
  e.preventDefault();
  $(this).removeClass('dragover');
  const file = e.dataTransfer.files[0];
  handleFileSelection(file);
});
```

### B.8.2 AJAX Upload with Progress

```javascript
$('#processBtn').click(function() {
  const formData = new FormData();
  formData.append('video', selectedFile);
  formData.append('lecture_hall', $('#lectureHall').val());

  $.ajax({
    url: '/process_video/',
    type: 'POST',
    data: formData,
    processData: false,        // Required for FormData
    contentType: false,        // Required for FormData
    headers: { 'X-CSRFToken': getCookie('csrftoken') },
    success: function(response) {
      if (response.stream_url) {
        showMJPEGStream(response.stream_url);
        startStatsPolling(response.task_id);
      }
    }
  });
});
```

### B.8.3 CSRF Token Extraction

```javascript
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
```

This is the standard Django CSRF cookie extraction pattern for AJAX requests.

### B.8.4 MJPEG Live Stream Display

```javascript
function showMJPEGStream(streamUrl) {
  const streamImg = document.getElementById('videoStream');
  streamImg.src = streamUrl;   // Browser handles MJPEG natively via <img> tag

  // Detect stream end via error event
  streamImg.onerror = function() {
    // Stream ended — MJPEG connection closed by server
    showCompletionState();
  };
}
```

**MJPEG** (Motion JPEG) is rendered natively by the browser as a continuously updating `<img>` element. When the backend processing completes and closes the HTTP connection, the browser fires an `error` event on the image, which is used to detect completion.

### B.8.5 Stats Polling

```javascript
let pollCount = 0;
const maxPolls = 10;

function startStatsPolling(taskId) {
  function poll() {
    if (pollCount >= maxPolls) return;
    pollCount++;

    $.get(`/processing_stats/${taskId}/`, function(data) {
      updateStatsDisplay(data);
      if (data.status === 'completed') {
        showCompletionModal(data);
      } else {
        setTimeout(poll, 2000);   // Poll every 2 seconds
      }
    });
  }
  setTimeout(poll, 3000);  // Start after 3s delay
}
```

### B.8.6 Completion Modal

Displays a grid of processing statistics:
```
┌──────────────┬────────────────┬──────────────┐
│  Duration    │  Frames        │  Detections  │
│  2m 34s      │  1,847         │  23          │
├──────────────┴────────────────┴──────────────┤
│  Detection Types Breakdown:                   │
│  Phone: 8  │  Looking Away: 6  │  Talking: 5 │
│  Leaning: 3  │  Hand Raise: 1                │
└──────────────────────────────────────────────┘
```

---

## B.9 Profile & Settings Pages

### B.9.1 Profile (`profile.html` — ~200 lines)

- Glass card with gradient header section
- **Role badges**: Admin = gradient background, Teacher = cyan
- Profile picture with avatar circle + cyan border + glow shadow
- Admin highlight banner (if superuser)
- Profile info table: Username, Email, First/Last Name, Date Joined, Phone, Lecture Hall

### B.9.2 Edit Profile (`edit_profile.html`)

- Two-column layout: "Basic User Info" (left) + "Teacher Profile" (right)
- Uses Django's `{{ user_form.as_p }}` and `{{ profile_form.as_p }}` for form rendering
- `enctype="multipart/form-data"` for profile picture update
- Toast notification on success → auto-redirect to profile after 2 seconds:
  ```javascript
  setTimeout(function() {
    window.location.href = "{% url 'profile' %}";
  }, 2000);
  ```

### B.9.3 Change Password (`change_password.html`)

- Narrow card (max-width: 500px), glass card design
- Uses Django's built-in `{{ form.as_p }}` for `PasswordChangeForm`
- Django messages for success/error display

---

## B.10 Admin Management Pages

### B.10.1 Manage Lecture Halls (`manage_lecture_halls.html` — 397 lines)

**Features:**
- **Add Hall form**: Hall name + Building dropdown (Main Building, Block A–E)
- **Filter bar**: Search by name, filter by building, filter by assignment status
- **CRUD Table**: Hall name, building, assigned teacher, map new teacher (select + assign button), actions (deassign/delete)
- **Custom Confirmation Modal** (not Bootstrap): Handles both deassign and delete with different styling

```javascript
function showConfirm(action, hallId, teacherName, hallName) {
  if (action === 'deassign') {
    title.textContent = 'Deassign Teacher';
    message.innerHTML = `Remove <strong>${teacherName}</strong> from <strong>${hallName}</strong>?`;
    btn.className = 'btn-confirm-warn';
    btn.name = 'unmap_teacher';
  } else if (action === 'delete') {
    title.textContent = 'Delete Lecture Hall';
    message.innerHTML = `Permanently delete <strong>${hallName}</strong>?`;
    btn.className = 'btn-confirm-danger';
    btn.name = 'delete_hall';
  }
  modal.classList.add('show');
}
```

Modal keyboard accessibility:
```javascript
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') hideConfirm();
});
// Close on backdrop click
document.getElementById('confirmModal').addEventListener('click', function(e) {
  if (e.target === this) hideConfirm();
});
```

### B.10.2 View Teachers (`view_teachers.html` — ~130 lines)

- Admin-only page listing all teachers
- Filter bar: Building, Search (name/email/username), Assignment status
- Table columns: Sl.No, Full Name, Username, Email, Phone, Lecture Hall
- Uses `{% for teacher in teachers %}` / `{% empty %}` pattern
- `{{ forloop.counter }}` for serial numbering
- Related model access: `teacher.teacherprofile.phone`, `teacher.lecturehall.building`

---

## B.11 Cross-Cutting Technical Patterns

### B.11.1 CSRF Token Handling

All POST/AJAX requests include Django's CSRF token:

1. **Form submissions**: `{% csrf_token %}` renders a hidden `<input>` automatically
2. **Fetch API**: Manual header `'X-CSRFToken': '{{ csrf_token }}'`
3. **jQuery AJAX**: `getCookie('csrftoken')` extracts from cookie
4. **WebSocket**: Not needed (WebSocket handshake uses session cookie)

### B.11.2 Memory Management (ObjectURL Pattern)

**Problem:** `URL.createObjectURL()` creates a reference to in-memory blob data. If not revoked, these accumulate endlessly.

**Solution (run_cameras.html):**
```javascript
// Track last URL per teacher
const _camFrameState = {};

// Before setting new frame:
if (_camFrameState[teacherId]) {
  URL.revokeObjectURL(_camFrameState[teacherId]);  // Free old memory
}
_camFrameState[teacherId] = newUrl;
img.src = newUrl;
```

**Solution (teacher_cameras.html):**
```javascript
processedImg.onload = function() {
  URL.revokeObjectURL(this.src);  // Free memory after image renders
};
```

### B.11.3 WebSocket Reconnection Strategy

Both camera pages implement the same reconnection pattern:

1. **`onclose` handler**: Automatic retry after 3-second delay
2. **`visibilitychange` listener**: Reconnect when page becomes visible after sleep/wake
3. **Guard condition**: Only reconnect if session is still active (prevents reconnect after intentional stop)

```javascript
streamSocket.onclose = function() {
  // Only reconnect if webcam is still running (not intentional stop)
  if (webcamStream && activeSessionId) {
    setTimeout(openStreamSocket, 3000);
  }
};
```

### B.11.4 IIFE Pattern for Page Scripts

Camera pages wrap all JavaScript in an IIFE (Immediately Invoked Function Expression):

```javascript
(function() {
  'use strict';
  // All state variables and functions are scoped here
  let notifSocket = null;
  let streamSocket = null;
  let webcamStream = null;
  // ...
})();
```

This prevents global namespace pollution since each page includes its own inline script.

### B.11.5 Django Template Integration Points

| Template Feature | Example |
|-----------------|---------|
| URL resolution | `{% url 'malpractice_log' %}` |
| Static files | `{% static 'css/theme.css' %}` |
| CSRF tokens | `{% csrf_token %}`, `{{ csrf_token }}` |
| Conditionals | `{% if request.user.is_superuser %}` |
| Loops | `{% for teacher in teachers %}` |
| Filters | `{{ name\|default:"N/A" }}`, `{{ date\|date:"M d, Y" }}` |
| Include | `{% include 'header.html' %}` |
| Block | `{% block content %}...{% endblock %}` |
| Empty | `{% empty %}` fallback in for loops |

---

# PART C — TESTING & RESULTS

## C.1 How Pages Were Tested

| Page | Testing Method |
|------|---------------|
| index.html | Visual inspection, GSAP animations verified on scroll, responsive check at 768px/576px |
| login.html | Login flow, password toggle, error display, wrong credentials |
| teacher_register.html | Registration with/without profile pic, validation errors |
| malpractice_log.html | Filter combinations, review toggle, selection mode, batch delete, AI actions, video playback |
| run_cameras.html | Multi-teacher simultaneous streams, start/stop all, detection alerts, sleep/wake reconnection |
| teacher_cameras.html | Camera permission denied, camera in use, accept/deny flow, 20 FPS sustained, tab switch test |
| upload_video.html | Drag-drop, file selection, MJPEG stream, stats polling, completion modal |
| profile.html | Admin vs teacher view, profile pic display |
| manage_lecture_halls.html | Add/assign/deassign/delete hall, keyboard accessibility |

## C.2 Browser Compatibility

| Feature | Chrome | Firefox | Safari | Edge |
|---------|--------|---------|--------|------|
| Glassmorphism (backdrop-filter) | ✅ | ✅ | ✅ (with -webkit-) | ✅ |
| getUserMedia | ✅ | ✅ | ✅ | ✅ |
| WebSocket binary | ✅ | ✅ | ✅ | ✅ |
| CSS Grid (auto-fill) | ✅ | ✅ | ✅ | ✅ |
| GSAP + ScrollTrigger | ✅ | ✅ | ✅ | ✅ |
| MJPEG in `<img>` | ✅ | ✅ | ⚠️ partial | ✅ |

## C.3 Performance Observations

- **Frame rate**: Consistent 18-20 FPS on localhost, ~12-15 FPS on LAN
- **Memory**: Stable with `revokeObjectURL()` — no leaks observed over 30-min sessions
- **GSAP fallback**: Elements remain visible if CDN fails (tested by blocking CDN)
- **AJAX filtering**: Table swaps in <200ms (no full page reload needed)

---

# PART D — VIVA QUESTIONS & ANSWERS (60+ Questions)

## Category 1: CSS & Design System

**Q1: Why did you use CSS custom properties instead of hardcoded colour values?**
A: CSS custom properties (variables) provide a single source of truth for the entire colour scheme. Changing `--accent-cyan` in `:root` propagates to every element that references it — across all 15 templates. This is the design token pattern used by modern design systems.

**Q2: What is glassmorphism and how did you implement it?**
A: Glassmorphism is a UI design trend that creates a frosted glass effect. We use `backdrop-filter: blur(20px) saturate(180%)` combined with a semi-transparent background (`rgba(17, 24, 39, 0.7)`). The `-webkit-backdrop-filter` prefix is added for Safari compatibility.

**Q3: Why is there a `-webkit-` prefix on `backdrop-filter`?**
A: Safari requires the `-webkit-` prefix for `backdrop-filter`. Without it, the blur effect won't render in Safari/iOS browsers.

**Q4: How does the dark theme work with Bootstrap 4?**
A: Bootstrap 4 doesn't have a native dark mode. We override ~40 Bootstrap component defaults in `theme.css` — `.form-control` gets dark backgrounds, `.btn-primary` uses our gradient, `.table` uses dark theme colours, etc.

**Q5: What does `clamp(2.5rem, 6vw, 4.5rem)` do for the hero title?**
A: CSS `clamp()` provides fluid responsive typography. The font-size will never be smaller than 2.5rem (mobile), never larger than 4.5rem (desktop), and scales proportionally at 6vw between those breakpoints.

**Q6: What is the `.skeleton` CSS class used for?**
A: It creates a shimmer loading animation using a moving gradient. This provides visual feedback while content is loading — it's the "skeleton screen" UX pattern used by Facebook, YouTube, etc.

**Q7: How do you prevent layout shift when fonts load?**
A: We use `font-display: swap` (via Google Fonts URL parameter) and specify `system-ui, sans-serif` as fallbacks. The browser immediately renders with system font and swaps to Inter when loaded.

**Q8: Why do pages have inline `<style>` instead of separate CSS files?**
A: Each page has component-scoped inline styles for page-specific elements. The shared design system lives in `theme.css`. This approach avoids unused CSS on each page and keeps templates self-contained — similar to Vue.js single-file components but without a build step.

---

## Category 2: GSAP Animations

**Q9: What is GSAP and why did you use it instead of CSS animations?**
A: GSAP (GreenSock Animation Platform) is a high-performance JavaScript animation library. We use it because: (1) `ScrollTrigger` makes scroll-based animations declarative, (2) it handles cross-browser quirks, (3) `fromTo()` gives precise control over start/end states, and (4) it performs better than CSS animations for complex sequences.

**Q10: Explain the `scrollTrigger` configuration.**
A: `{ trigger: el, start: 'top 85%', toggleActions: 'play none none none' }` means: start the animation when the element's top edge crosses the 85% mark of the viewport. `toggleActions` defines behavior for enter/leave/enter-back/leave-back — we only play on first enter.

**Q11: What's the difference between `gsap.from()` and `gsap.fromTo()`?**
A: `from()` specifies only the starting state and animates to the element's current CSS state. `fromTo()` specifies both start and end states explicitly. We use `from()` for the hero entrance (known end state) and `fromTo()` for scroll reveals (need to control both states).

**Q12: Why do the animated rings use `repeat: -1`?**
A: `repeat: -1` creates an infinite loop. The three concentric rings rotate continuously at different speeds (20s, 25s, 30s) and alternate directions to create a dynamic background visual.

**Q13: What happens if GSAP fails to load from CDN?**
A: We have a fallback that sets `opacity: 1` and `transform: none` on all `.reveal-*` elements, ensuring content is visible even without animations. The CSS class `.reveal-up` only has `will-change: opacity, transform` — it doesn't set `opacity: 0`, so content would be visible anyway.

---

## Category 3: WebSocket & Real-Time Communication

**Q14: Why WebSocket instead of HTTP polling for the camera system?**
A: WebSocket provides full-duplex, persistent communication with <10ms latency. HTTP polling would require a new request every 50ms (20 FPS) which is impractical — each request has TCP/HTTP overhead, and the server can't push data to the client.

**Q15: Why does the admin page have two WebSocket connections?**
A: The Notification socket handles control messages (start/stop/status/alerts) as JSON. The Grid socket handles binary frame data. Separating them prevents binary frame data from blocking or delaying critical control messages.

**Q16: Explain the binary frame protocol.**
A: Each binary message contains: bytes 0-3 = teacher ID as a 32-bit big-endian unsigned integer (`DataView.getUint32(0)`), bytes 4+ = JPEG image data. The teacher ID identifies which camera cell to update. We extract it with `DataView` on an `ArrayBuffer`, then create a `Blob` from `buffer.slice(4)`.

**Q17: What is `DataView` and why is it used here?**
A: `DataView` provides a low-level interface for reading multi-byte numbers from an `ArrayBuffer` with explicit endianness control. We use `getUint32(0)` to read a 4-byte big-endian integer — the teacher ID prepended by the server.

**Q18: Why `URL.createObjectURL()` instead of base64 for frames?**
A: `createObjectURL()` creates a direct reference to binary blob data without encoding overhead. Base64 encoding adds 33% size overhead and requires CPU time for encoding/decoding. For video at 20 FPS, this difference is significant.

**Q19: What happens if you forget `URL.revokeObjectURL()`?**
A: Each `createObjectURL()` holds a reference to blob data in memory. Without revoking, at 20 FPS you'd accumulate ~1,200 unreleased references per minute. Over a 30-minute session, this causes gigabytes of memory leaks and eventual browser crash.

**Q20: How is the _camFrameState object used for memory management?**
A: It's a dictionary mapping `teacherId → lastObjectURL`. Before setting a new frame, we check if there's an existing URL for that teacher and revoke it first. This ensures only one ObjectURL exists per camera stream at any time.

**Q21: Why `setInterval` instead of `requestAnimationFrame` for frame capture?**
A: `requestAnimationFrame` is throttled to 0-1 FPS when the browser tab is in the background. Since we need consistent streaming even if the teacher briefly switches tabs, `setInterval` is used — it continues running at approximately 20 FPS regardless of tab visibility.

**Q22: What JPEG quality setting is used and why 0.65?**
A: `canvas.toBlob(blob, 'image/jpeg', 0.65)` uses 65% quality. This balances image clarity (still readable by ML models) with file size (~30-50KB per frame instead of 200KB+ at 100%). At 20 FPS, this keeps bandwidth under 1 MB/s.

**Q23: What protocol is used to determine ws:// vs wss://?**
A: `window.location.protocol === 'https:' ? 'wss' : 'ws'` — if the page is served over HTTPS, we use the secure WebSocket protocol (wss://) which tunnels through TLS. Otherwise, plain ws:// is used for development.

**Q24: Explain the sleep/wake reconnection strategy.**
A: When a laptop sleeps and wakes, WebSocket connections are dropped. The `visibilitychange` event fires when the page becomes visible again. We check `document.visibilityState === 'visible'` and verify if each WebSocket's `readyState !== WebSocket.OPEN`. If closed, we reconnect.

**Q25: What's the auto-reconnect strategy on WebSocket close?**
A: `socket.onclose` triggers `setTimeout(reconnect, 3000)` — retry after 3 seconds. On the teacher camera page, there's a guard: `if (webcamStream && activeSessionId)` — we only reconnect if streaming is still intended (not after intentional stop).

---

## Category 4: getUserMedia & Camera

**Q26: What does `facingMode: 'user'` mean?**
A: It requests the front-facing camera (selfie camera), which is what we need for proctoring. On desktops with one camera, it's the default. On mobile devices, it distinguishes from the rear camera (`environment`).

**Q27: Why is audio set to false?**
A: We only need video frames for ML analysis. Capturing audio would require additional permissions, increase bandwidth, and raise privacy concerns without adding value to the proctoring system.

**Q28: How do you handle the case where the user denies camera permission?**
A: `getUserMedia()` rejects with `NotAllowedError`. We catch it and map to `reason: 'permission_denied'`, then send this to the admin via WebSocket. The admin sees an error toast with the teacher's name and the reason.

**Q29: What happens when `NotReadableError` is thrown?**
A: It means the camera hardware exists but is being used by another application (Zoom, Skype, etc.). We map this to `camera_in_use` and notify the admin, who can request again after the teacher closes the other app.

**Q30: Why do you stop individual tracks with `track.stop()` instead of just setting srcObject to null?**
A: `video.srcObject = null` disconnects the video element but doesn't release the camera. The camera LED stays on and the hardware remains locked. `stream.getTracks().forEach(track => track.stop())` actually releases the camera hardware.

---

## Category 5: AJAX & Fetch API

**Q31: Why use Fetch API in some pages and jQuery AJAX in others?**
A: The camera pages use vanilla JS (Fetch API) for minimal dependencies and better control over binary data. The upload page uses jQuery AJAX because it was already handling FormData uploads and jQuery provides cleaner progress callback syntax.

**Q32: What is the CSRF token and why is it needed in AJAX requests?**
A: Django requires CSRF (Cross-Site Request Forgery) tokens for all POST/PUT/DELETE requests to verify the request comes from our own site, not a malicious third-party page. For form submissions, `{% csrf_token %}` adds a hidden input. For AJAX, we either access `{{ csrf_token }}` in headers or extract from the `csrftoken` cookie.

**Q33: What does `processData: false` mean in jQuery AJAX?**
A: By default, jQuery serializes data objects into URL-encoded strings. When sending `FormData` (for file uploads), we must set `processData: false` to prevent jQuery from trying to serialize the binary form data.

**Q34: What does `contentType: false` mean?**
A: It prevents jQuery from setting the `Content-Type` header. `FormData` sets its own multipart boundary in the header (`multipart/form-data; boundary=...`). If jQuery overrides this, the server can't parse the multipart request.

**Q35: How does the `DOMParser` technique work for partial page updates?**
A: `fetch()` retrieves the full HTML page, then `new DOMParser().parseFromString(html, 'text/html')` creates a DOM tree from it. We extract just the `.table-container` element and replace the existing one. This gives us AJAX-like partial updates without a separate API endpoint — reusing the same Django view.

**Q36: Why use `history.pushState()` after AJAX filtering?**
A: `pushState()` updates the browser URL to include filter parameters without triggering a page reload. This means: (1) the URL is shareable/bookmarkable, (2) the browser back button works correctly, (3) page refresh maintains the current filters.

---

## Category 6: Specific UI Features

**Q37: How does the drag-and-drop file upload work?**
A: Three events: `dragover` (prevent default + visual feedback), `dragleave` (remove feedback), `drop` (prevent default + access `e.dataTransfer.files[0]`). The `preventDefault()` on dragover/drop is critical — without it, the browser navigates to the file.

**Q38: How does MJPEG streaming work in the browser?**
A: MJPEG is a stream of JPEG frames sent over HTTP. The browser's `<img>` element natively supports this — just set `img.src` to the stream URL. The browser continuously reads and displays frames. When the server closes the connection, the `<img>` fires an `error` event, which we use to detect stream completion.

**Q39: How is the malpractice row delete animated?**
A: After successful AJAX delete, we apply CSS transition: `opacity 0→1` and `transform: translateX(30px)` (slide right while fading). After 300ms (matching the transition duration), `row.remove()` actually removes the DOM element.

**Q40: Why custom confirmation modals instead of Bootstrap modals for lecture halls?**
A: The lecture hall page needs to dynamically set both the action type (deassign vs delete) AND the form button name (`unmap_teacher` vs `delete_hall`). A custom modal gives full control over button class, text, and form field names without dealing with Bootstrap modal event race conditions.

**Q41: How does the review toggle slider work?**
A: It's a hidden checkbox styled with CSS pseudo-elements to look like a slider. The checkbox state (`checked` or not) maps to `reviewed` vs `not_reviewed`. On change, AJAX fetches the page with the new filter and swaps the table content.

**Q42: Explain the detection alert feed cap of 50 items.**
A: When new detections arrive, they're prepended to the alert list. We cap at 50 items: `while (alertFeed.children.length > 50) alertFeed.lastChild.remove()`. This prevents DOM bloat during long monitoring sessions.

**Q43: What is `performance.getEntriesByType("navigation")` used for?**
A: On the malpractice log, it detects if the page was loaded via browser refresh vs normal navigation. If `entry.type === 'reload'`, the review toggle state is reset to match the URL parameters, ensuring consistency.

---

## Category 7: Template Architecture

**Q44: Why include-based composition instead of Django extends/base template?**
A: The project uses `{% include 'header.html' %}` + `{% block content %}` as a hybrid. Header handles all CDN loading and navbar. Each page defines `{% block content %}`. This is simpler than full template inheritance for a project where every page has a very different structure.

**Q45: What does `{% load static %}` do?**
A: It loads Django's `static` template tag library, enabling `{% static 'css/theme.css' %}` which resolves to the correct URL for static files (e.g., `/static/css/theme.css`). In production with `collectstatic`, these URLs may be different (CDN, hashed filenames).

**Q46: How does role-based rendering work in Django templates?**
A: `{% if request.user.is_superuser %}` checks if the user is an admin. `{% if request.user.is_authenticated %}` checks login status. These determine which navigation links, form fields (admin has more filters), and action buttons appear.

**Q47: What is `{{ forloop.counter }}` in Django templates?**
A: It's a loop variable that gives the 1-based iteration count. Used for serial numbers in tables. `{{ forloop.counter0 }}` gives 0-based. `{{ forloop.last }}` is True on the final iteration.

**Q48: What's the purpose of `{% empty %}` in for loops?**
A: It defines fallback content when the iterable is empty: `{% for teacher in teachers %}...{% empty %}<tr><td>No teachers found.</td></tr>{% endfor %}`. This provides a clean "no data" message instead of a blank table.

---

## Category 8: JavaScript Patterns

**Q49: What is IIFE and why is it used on camera pages?**
A: IIFE (Immediately Invoked Function Expression) — `(function() { ... })()` — creates a private scope for all variables and functions. Since multiple pages are included via `{% include %}` and have inline scripts, IIFE prevents variable name collisions in the global scope.

**Q50: Why use `let` instead of `var` for WebSocket references?**
A: `let` has block scope (within `{}`), while `var` is function-scoped and hoisted. `let` prevents accidental re-declarations and makes the code easier to reason about — especially important in async WebSocket handlers where timing matters.

**Q51: How does the FPS counter avoid expensive frequent DOM updates?**
A: It only updates the display every 30 frames. It counts frames and measures elapsed time with `performance.now()`. When `frameCount >= 30`, it calculates `fps = frameCount / elapsed` and updates the DOM once, then resets counters.

**Q52: What's the `beforeunload` event used for?**
A: It fires when the user is about to leave the page (close tab, navigate away, refresh). On the teacher camera page, it sends `camera_stop_by_teacher` to the admin via WebSocket, ensuring the admin knows the stream ended even if the teacher just closes their browser.

---

## Category 9: Bootstrap Integration

**Q53: Why Bootstrap 4.5.2 and not Bootstrap 5?**
A: Bootstrap 4 was the stable version when the project started. It uses jQuery which was already needed for other interactions. Bootstrap 5 drops jQuery dependency, but since we use jQuery for AJAX and DOM manipulation, keeping Bootstrap 4 avoids redundancy.

**Q54: What Bootstrap components are used throughout the project?**
A: Grid system (container/row/col), Navbar (collapse, dropdown), Modals (malpractice log has 5 modals), Tables (striped, hover), Forms (form-group, form-control, input-group), Alerts, Buttons, Cards, Toasts.

**Q55: How is the Bootstrap grid used for responsive layouts?**
A: `col-md-6` means 50% width from medium screens up, full-width on mobile. The malpractice log filter bar uses `col-md-2`, `col-md-3` etc. for a multi-column filter row that stacks on mobile. Camera feeds use CSS Grid (`auto-fill, minmax(300px, 1fr)`) rather than Bootstrap grid for more dynamic sizing.

---

## Category 10: Security (Frontend)

**Q56: How is XSS prevented in the templates?**
A: Django auto-escapes all template variables by default. `{{ teacher.username }}` is escaped to prevent script injection. For deliberately rendering HTML (rare), you'd use `{{ value|safe }}` — but this project avoids it.

**Q57: How are AJAX requests protected against CSRF?**
A: Three methods used: (1) `{% csrf_token %}` hidden input for form submissions, (2) `{{ csrf_token }}` in `X-CSRFToken` header for Fetch API, (3) Cookie extraction via `getCookie('csrftoken')` for jQuery AJAX. All three provide the same CSRF protection.

**Q58: Is WebSocket communication authenticated?**
A: Yes. The WebSocket handshake uses the same session cookie as HTTP requests. Django Channels middleware (`AuthMiddlewareStack`) extracts the user from the cookie. Unauthenticated users can't establish WebSocket connections.

**Q59: What prevents a teacher from accessing admin pages?**
A: Two layers: (1) Django views check `@login_required` and `is_superuser`, returning 403/redirect, (2) Templates conditionally render admin-only UI elements with `{% if request.user.is_superuser %}`. Even if someone manually navigates to an admin URL, the backend denies access.

---

## Category 11: Architecture & Design Decisions

**Q60: Why inline scripts instead of separate .js files?**
A: Each page has substantial JavaScript tightly coupled to its Django template (using `{{ csrf_token }}`, `{{ teacher.id }}`, URL names). Extracting to separate files would require a data-passing layer (data attributes or global variables). Inline scripts with template variables is the pragmatic Django convention.

**Q61: How would you scale this frontend for 100+ simultaneous camera streams?**
A: Current CSS Grid auto-fill handles layout. For performance: (1) implement virtual scrolling for the camera grid (only render visible cells), (2) reduce frame rate for minimized/off-screen cameras, (3) use `IntersectionObserver` to pause URL.createObjectURL for non-visible feeds, (4) consider WebRTC for peer-to-peer streaming to reduce server load.

**Q62: What's the advantage of MJPEG over HLS/DASH for the upload processing stream?**
A: MJPEG is simpler — just an HTTP response with continuous JPEG frames. No need for video segmentation, manifest files, or client-side video player libraries. For a single processing stream viewed by one user, MJPEG is ideal. HLS/DASH is better for scalable live broadcasting.

**Q63: Why is the detection alert feed limited to 50 items?**
A: DOM nodes consume memory and affect rendering performance. In a long monitoring session, thousands of alerts would slow down the page and increase memory usage. 50 items keeps the recent history visible while maintaining performance.

**Q64: What would you change if rebuilding this frontend?**
A: (1) Use a component framework (React/Vue) for better state management on complex pages like malpractice_log, (2) Use CSS modules or Tailwind instead of global stylesheet, (3) Move to WebRTC for camera streams, (4) Add service worker for offline capability, (5) Use TypeScript for better code quality on 500+ line scripts.

**Q65: How does the system handle slow network connections?**
A: JPEG quality at 0.65 reduces frame size. The FPS counter provides real-time feedback. WebSocket reconnection handles temporary network drops. Stats polling with `maxPolls` cap prevents infinite polling on failed connections. AJAX operations have `.catch()` error handlers that show user-friendly error messages.

---

## Summary Cheat Sheet: Numbers to Remember

| Metric | Value |
|--------|-------|
| CSS custom properties | ~60 |
| Templates (active) | 15 |
| Total frontend lines | ~7,400 |
| WebSocket connections per admin | 2 (notif + grid) |
| Frame capture rate | 20 FPS |
| JPEG quality | 0.65 (65%) |
| Frame protocol header | 4 bytes (uint32 teacher ID) |
| Detection alert cap | 50 items |
| WebSocket reconnect delay | 3 seconds |
| FPS counter update interval | Every 30 frames |
| Bootstrap version | 4.5.2 |
| jQuery version | 3.6.0 |
| GSAP version | 3.12.5 |
| Stats poll max attempts | 10 |
| theme.css total lines | 1,875 |
| malpractice_log.html (most complex) | 1,427 lines |
| Malpractice table columns | 13 |
| Filter bar fields (admin) | 11+ |
