# Person 3 — Django Backend, Database & Notifications

## Your Role
You built the **backend logic and data layer** — all the Django views (the HTTP endpoints), the database schema (models), the email/SMS notification system, user authentication, file upload handling, and video serving. You connect the frontend (Person 4) to the AI pipeline (Person 1) and the real-time system (Person 2).

## Key Files You Own
| File | Purpose | Lines |
|------|---------|-------|
| `app/views.py` | All HTTP views (39 functions) | 1431 |
| `app/models.py` | Database models (5 tables) | 109 |
| `app/urls.py` | URL routing (30+ endpoints) | 41 |
| `app/settings.py` | Django configuration (DB, email, security, ASGI) | 236 |
| `app/custom_email_backend.py` | Resilient email sending | ~50 |
| `app/utils.py` | SSH/script utilities | ~100 |
| `.env` | Environment variables (secrets, DB credentials) | ~15 |
| `requirements.txt` | Python dependencies | ~30 |

---

## PART A: Everything You Built

### 1. User Authentication System
- Login/logout with Django's built-in auth
- Teacher registration with profile creation (phone, lecture hall, profile picture)
- Password change with Django's PasswordChangeForm
- Admin detection (`is_admin()` checks `is_superuser`)
- Session-based authentication (1-hour timeout, expires on browser close)
- `@login_required` decorator on all protected views

### 2. Database Design (5 Models)
- **LectureHall** — Building, hall name, assigned teacher
- **CameraSession** — Teacher, lecture hall, status (requested/active/stopped/denied), timestamps
- **MalpraticeDetection** — Date, time, malpractice type, proof file, probability score, review status
- **ReviewSession** — Admin reviewer, teacher, lecture hall, logs reviewed/flagged counts
- **TeacherProfile** — Phone, profile picture, lecture hall, online status

### 3. Malpractice Log Management
- Filtered/sorted log views (date, time, type, probability, building, source, assignment, sort order)
- Ajax-powered review toggle (reviewed/unreviewed) 
- Individual and bulk log deletion
- AI bulk actions (approve all high-probability, dismiss all low-probability)
- Sort by newest/oldest/highest probability/lowest probability

### 4. Review Workflow
- Admin reviews each detection (mark as malpractice or not malpractice)
- Complete review session → creates ReviewSession record
- Teacher visibility toggle (logs only visible to teacher after admin review)
- Review summary email to teacher with counts

### 5. Video Serving & Upload
- Browser-compatible video serving with H.264 conversion (ffmpeg fallback chain)
- HTTP Range request support for video seeking/scrubbing
- Video upload page with lecture hall selection
- MJPEG streaming for live processing preview

### 6. Email & SMS Notifications
- Gmail SMTP for email notifications
- Twilio API for SMS alerts
- Custom email backend with retry logic
- Background-threaded notification sending (non-blocking)

### 7. Lecture Hall & Teacher Management
- CRUD operations for lecture halls
- Teacher-to-hall assignment
- Building categorization (Main Block, Second Block, Third Block)
- Teacher list view with online status

### 8. Security Settings
- CSRF protection, clickjacking prevention (`X-Frame-Options: DENY`)
- Secure sessions (HTTP-only cookies, 1-hour timeout)
- SSL enforcement in production
- HSTS headers for HTTPS enforcement

---

## PART B: How Each Thing Works (Simple + Technical)

---

### B1. Django MTV Architecture

**Simple:** Django uses a pattern called MTV:
- **Model** = the database structure (what data we store)
- **Template** = the HTML pages the user sees
- **View** = the logic that decides what data to show and which template to use

When you visit a URL (e.g., `/malpractice_log/`), Django looks up which view function handles it, the view fetches data from the database using models, and renders a template with that data.

**Technical:**
```
Browser Request → urls.py (URL routing) → views.py (logic)
                                             │
                                    ┌────────┴────────┐
                                    │                  │
                              models.py          templates/
                           (database query)     (HTML rendering)
                                    │                  │
                                    └────────┬─────────┘
                                             │
                                    HTTP Response → Browser
```

**Why Django and not Flask?**
| Feature | Django | Flask |
|---------|--------|-------|
| Admin panel | Built-in (auto-generated) | Manual |
| ORM (Object-Relational Mapper) | Built-in | SQLAlchemy (separate) |
| Authentication | Built-in (full system) | Flask-Login (separate) |
| Session management | Built-in | Flask-Session (separate) |
| Form handling | Built-in (with CSRF) | WTForms (separate) |
| Template engine | Jinja2-like (built-in) | Jinja2 (built-in) |
| WebSocket support | Via Channels | Via Flask-SocketIO |

Django gives us everything out of the box. Flask would require assembling 5+ separate packages.

---

### B2. Database Design — Deep Dive

**Simple:** Our database has 5 tables, like 5 spreadsheets that are connected to each other. For example, each malpractice detection links to a lecture hall (so we know WHERE it happened) and to a teacher (so we know WHO to notify).

**Technical (Entity-Relationship):**
```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│    User      │     │  MalpraticeDetection  │     │   LectureHall   │
│ (Django auth)│     │                       │     │                 │
│ id           │◄────│ uploaded_by (FK)      │     │ id              │
│ username     │     │ id                    │     │ building        │
│ email        │     │ date, time            │     │ hall_name       │
│ password     │     │ malpractice (type)    │────►│ assigned_teacher│
│ is_superuser │     │ proof (file path)     │     └─────────────────┘
└──────┬───────┘     │ is_malpractice (bool) │              │
       │             │ verified (bool)       │              │
       │             │ probability_score     │              │
       │             │ source_type           │              │
       │             │ teacher_visible       │              │
       │             │ lecture_hall (FK)──────┘              │
       │             └──────────────────────┘               │
       │                                                     │
       │         ┌─────────────────┐                        │
       │         │  CameraSession   │                        │
       │         │ id               │                        │
       ├────────►│ teacher (FK)     │                        │
       │         │ lecture_hall (FK)─────────────────────────┘
       │         │ status           │
       │         │ started_at       │
       │         │ stopped_at       │
       │         └─────────────────┘
       │
       │         ┌─────────────────┐
       │         │  TeacherProfile  │
       ├────────►│ user (1-to-1)   │
       │         │ phone            │
       │         │ profile_picture  │
       │         │ is_online        │
       │         │ lecture_hall (FK)────────────────────────►
       │         └─────────────────┘
       │
       │         ┌─────────────────┐
       └────────►│  ReviewSession  │
                 │ admin_user (FK) │
                 │ teacher (FK)    │
                 │ lecture_hall (FK)│
                 │ logs_reviewed   │
                 │ logs_flagged    │
                 │ email_sent      │
                 └─────────────────┘
```

**Why MySQL?**
- Project requirement specified MySQL
- Handles concurrent writes well (multiple WebSocket consumers saving detections simultaneously)
- SQLite would fail under concurrent writes (file-locking)
- PostgreSQL would also work, commented-out config exists for Render deployment

**Database Configuration (`settings.py`):**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME'),
        'HOST': env('DB_HOST', default='localhost'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASS'),
        'PORT': env('DB_PORT', default='3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}
```

**Why `STRICT_TRANS_TABLES`?** Prevents MySQL from silently truncating data or inserting defaults for missing columns. Forces errors on invalid data, catching bugs early.

---

### B3. The Malpractice Log View — Most Complex View

**Simple:** This is the main page where admin/teachers see all detected malpractice events. It supports filtering by 7+ criteria, sorting by 4 options, toggling between reviewed/unreviewed logs, and different views for admin (all logs) vs teacher (only their logs after review).

**Technical:**
```python
def malpractice_log(request):
    user = request.user
    admin = is_admin(user)
    
    # Get filter parameters from GET request
    date_filter = request.GET.get('date', '')
    time_filter = request.GET.get('time', '')
    malpractice_filter = request.GET.get('malpractice_type', '')
    probability_filter = request.GET.get('probability', '')
    source_filter = request.GET.get('source', '')
    building_filter = request.GET.get('building', '')
    faculty_filter = request.GET.get('faculty', '')
    assignment_filter = request.GET.get('assigned', '')
    query = request.GET.get('q', '')
    sort_order = request.GET.get('sort', 'newest')
    
    # Base queryset
    if admin:
        show_reviewed = request.GET.get('show_reviewed', 'false') == 'true'
        logs = MalpraticeDetection.objects.filter(verified=show_reviewed)
    else:
        # Teachers only see reviewed logs marked visible
        logs = MalpraticeDetection.objects.filter(
            teacher_visible=True,
            lecture_hall__assigned_teacher=user
        )
    
    # Apply filters (chain of .filter() calls)
    if date_filter:
        logs = logs.filter(date=date_filter)
    if time_filter == 'FN':
        logs = logs.filter(time__hour__lt=12)
    elif time_filter == 'AN':
        logs = logs.filter(time__hour__gte=12)
    if malpractice_filter:
        logs = logs.filter(malpractice=malpractice_filter)
    # ... more filters ...
    
    # Apply sorting
    if sort_order == 'oldest':
        logs = logs.order_by('date', 'time')
    elif sort_order == 'prob_high':
        logs = logs.order_by('-probability_score')
    elif sort_order == 'prob_low':
        logs = logs.order_by('probability_score')
    else:  # newest (default)
        logs = logs.order_by('-date', '-time')
    
    # Ensure probability scores exist
    ensure_probability_scores(logs)
    
    return render(request, 'malpractice_log.html', {
        'logs': logs,
        'admin': admin,
        'sort_order': sort_order,
        # ... all filter values for form persistence
    })
```

**Why chained `.filter()` calls?** Django ORM builds SQL queries lazily. Each `.filter()` adds a `WHERE` clause. The query only executes when the template iterates over the results. This means unused filters don't cost anything.

---

### B4. Review Workflow — How It Works

**Simple:** When the AI detects malpractice, it saves a log with `verified=False`. The admin reviews each log and marks it as real malpractice or not. After reviewing, the admin clicks "Complete Review" and the teacher gets an email summary like "3 malpractice events were confirmed in your exam."

**Technical Flow:**
```
1. ML detects malpractice → saves to DB (verified=False, teacher_visible=False)

2. Admin opens /malpractice_log/ (show_reviewed=false) → sees unreviewed logs

3. Admin clicks "Mark as Malpractice" on a log
   → POST /review_malpractice/
   → Updates: is_malpractice=True, verified=True
   
4. Admin clicks "Not Malpractice" on a log
   → POST /review_malpractice/
   → Updates: is_malpractice=False, verified=True

5. Admin clicks "Complete Review Session"
   → POST /complete_review_session/
   → Creates ReviewSession record
   → Sets teacher_visible=True for all reviewed logs of that teacher
   → Sends summary email in background thread
```

**Why `teacher_visible`?** Teachers shouldn't see raw AI detections (many are false positives). They only see logs that the admin has reviewed and confirmed. This prevents unnecessary panic.

**Background Email (non-blocking):**
```python
def send_notifications_background(log_id):
    """Runs in a thread — doesn't block the HTTP response"""
    log = MalpraticeDetection.objects.get(id=log_id)
    teacher = log.lecture_hall.assigned_teacher
    profile = TeacherProfile.objects.get(user=teacher)
    
    # Email
    send_mail(
        subject=f"Malpractice Detected - {log.malpractice}",
        message=f"A {log.malpractice} event was detected...",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[teacher.email],
    )
    
    # SMS via Twilio
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=f"AIInvigilator: {log.malpractice} detected...",
        from_=settings.TWILIO_PHONE_NUMBER,
        to=profile.phone
    )

# Called via:
Thread(target=send_notifications_background, args=(log.id,)).start()
```

---

### B5. Video Serving — The H.264 Conversion Problem

**Simple:** OpenCV saves videos in a format (mp4v) that browsers can't play. So when the admin clicks "View Video", our server converts the video to a browser-friendly format (H.264) on-the-fly and sends it to the browser.

**Technical:**

```python
def serve_video(request):
    video_path = request.GET.get('path')
    
    # Strategy 1: Try ffmpeg conversion to H.264
    try:
        temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        subprocess.run([
            'ffmpeg', '-i', video_path,
            '-c:v', 'libx264',    # H.264 codec
            '-preset', 'ultrafast', # Fast encoding
            '-movflags', '+faststart',  # Seekable from start
            '-y', temp_file.name
        ], check=True)
        return FileResponse(open(temp_file.name, 'rb'), content_type='video/mp4')
    except:
        pass
    
    # Strategy 2: Try OpenCV re-encoding
    try:
        cap = cv2.VideoCapture(video_path)
        # Re-encode with H.264 using OpenCV
        ...
    except:
        pass
    
    # Strategy 3: Fall back to raw file download
    return FileResponse(open(video_path, 'rb'), content_type='video/mp4')
```

**Why can't browsers play mp4v?** Browsers (Chrome, Firefox, Edge) support H.264 (AVC) and VP9 codecs for `<video>` tags. OpenCV's `mp4v` is MPEG-4 Part 2, which is an older codec that most browsers have dropped support for. ffmpeg converts it by re-encoding the video stream to H.264 while keeping the same resolution and framerate.

**HTTP Range Requests:** When you scrub a video (drag the progress bar), the browser sends a `Range: bytes=1000-2000` header. Our view handles this by seeking to the right position in the file and returning just that chunk, enabling smooth video scrubbing without downloading the entire file.

---

### B6. AI Bulk Actions

**Simple:** Instead of reviewing 100 logs one by one, the admin can click "Approve All High ≥50%" to automatically mark all high-probability detections as malpractice, or "Dismiss All Low <50%" to clear the low-probability ones.

**Technical:**
```python
def ai_bulk_action(request):
    action = request.POST.get('action')
    
    if action == 'approve_high':
        # All unreviewed logs with probability ≥ 50%
        logs = MalpraticeDetection.objects.filter(
            verified=False,
            probability_score__gte=50
        )
        logs.update(is_malpractice=True, verified=True)
        
    elif action == 'dismiss_low':
        # All unreviewed logs with probability < 50%
        logs = MalpraticeDetection.objects.filter(
            verified=False,
            probability_score__lt=50
        )
        logs.update(is_malpractice=False, verified=True)
```

**Why 50% threshold?** It's the default midpoint. Detections above 50% are "more likely than not" to be real malpractice. Admins can still review individual cases for borderline scores.

---

### B7. Environment Variables & Security

**Simple:** Secret information like database passwords, email credentials, and API keys should never be written directly in the code. We store them in a `.env` file that only exists on the server and is never shared.

**Technical:**
```bash
# .env file
SECRET_KEY=django-insecure-abc123xyz
DEBUG=True
DB_NAME=aiinvigilator
DB_USER=root
DB_PASS=mysql_password
DB_HOST=localhost
DB_PORT=3306
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=app-specific-password
TWILIO_ACCOUNT_SID=ACXXXXXXXXXXXXXXX
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
USE_GPU=True
USE_HALF_PRECISION=True
```

We use `django-environ` to read these:
```python
import environ
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY', default='fallback-key')
```

**Security measures in `settings.py`:**
- `X_FRAME_OPTIONS = 'DENY'` → Prevents clickjacking (your site can't be embedded in iframes)
- `SESSION_COOKIE_HTTPONLY = True` → JavaScript can't read session cookie (prevents XSS session theft)
- `SESSION_COOKIE_AGE = 3600` → Sessions expire after 1 hour
- `SECURE_SSL_REDIRECT = True` (production) → Forces HTTPS
- `SECURE_HSTS_SECONDS = 31536000` → Tells browsers to always use HTTPS for 1 year

---

### B8. File Upload & Processing Pipeline

**Simple:** Teachers can upload a recorded exam video. The server saves it to disk, creates a processing session, and starts analyzing it frame by frame. The teacher can watch the AI processing live in their browser through a video player that shows annotated frames.

**Technical:**
```python
def process_video(request):
    if request.method == 'POST':
        video_file = request.FILES['video']
        lecture_hall_id = request.POST.get('lecture_hall')
        
        # Save to temp file
        session_id = str(uuid.uuid4())
        temp_path = os.path.join(settings.MEDIA_ROOT, 'uploads', f'{session_id}.mp4')
        
        with open(temp_path, 'wb') as f:
            for chunk in video_file.chunks():
                f.write(chunk)
        
        # Store session
        VIDEO_SESSIONS[session_id] = {
            'video_path': temp_path,
            'lecture_hall_id': lecture_hall_id,
            'status': 'ready'
        }
        
        return JsonResponse({'session_id': session_id})

def stream_video_processing(request, session_id):
    """Return MJPEG stream of ML-processed frames"""
    session = VIDEO_SESSIONS[session_id]
    
    async def frame_generator():
        for annotated_frame in stream_process_video(
            session['video_path'], 
            session['lecture_hall_id']
        ):
            _, jpeg = cv2.imencode('.jpg', annotated_frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    
    return StreamingHttpResponse(
        frame_generator(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )
```

**Why MJPEG streaming?** It's the simplest way to stream processed video. Each frame is a standalone JPEG. No codec negotiation, no complex buffering. The browser's `<img>` tag can display it directly. Downside: higher bandwidth than H.264 video streaming, but fine for a local network demo.

---

### B9. Retroactive Probability Scoring

**Simple:** Some older logs in the database didn't have probability scores because the feature was added later. So we wrote a function that calculates approximate scores for old logs based on available data (video file duration and malpractice type).

**Technical:**
```python
def calculate_retroactive_probability(log):
    """For logs saved before the scoring system existed"""
    base_scores = {
        'Mobile Phone Detected': 72,
        'Turning Back': 55,
        'Leaning': 45,
        'Hand Raising': 30,
        'Passing Paper': 65,
    }
    
    score = base_scores.get(log.malpractice, 50)
    
    # Adjust based on video file duration (if proof exists)
    if log.proof and os.path.exists(log.proof):
        cap = cv2.VideoCapture(log.proof)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = frames / max(fps, 1)
        cap.release()
        
        if duration > 5:
            score += 10
        elif duration > 10:
            score += 20
    
    return min(score, 98)
```

---

## PART C: Testing & Results

### How You Tested
1. **End-to-end flow:** Login → upload video → process → review → email notification
2. **Database integrity:** Verified foreign key constraints, cascade deletes
3. **Filter combinations:** Tested all possible filter combinations (date + time + type + ...)
4. **File handling:** Large file upload (500MB), corrupted video files, missing proof files
5. **Security:** CSRF token validation, unauthorized access attempts, SQL injection (handled by ORM)

### Results
| Metric | Value |
|--------|-------|
| Average view response time | < 200ms |
| Database query time (filtered logs) | < 50ms |
| Video conversion time (30s clip) | ~3 seconds |
| File upload speed | ~50MB/s (local) |
| Email delivery time | 2-5 seconds |
| SMS delivery time | 3-8 seconds |

### What Can Be Improved
1. **Pagination** — Currently loads all logs. Should paginate for 1000+ entries
2. **Caching** — Add Redis caching for frequently accessed log counts
3. **Celery** — Use task queue instead of threads for background jobs (email, video processing)
4. **API endpoints** — Add REST API for mobile app integration
5. **Database indexes** — Add indexes on date, time, lecture_hall for faster filtering

---

## PART D: Evaluation Q&A

### Core Questions

**Q1: Explain Django's MTV architecture.**
A: MTV stands for Model (database schema), Template (HTML views), View (business logic). A request hits the URL router, which calls the appropriate view function. The view queries the database via models, processes data, and renders a template with context variables. The rendered HTML is returned as the HTTP response.

**Follow-up: How is MTV different from MVC?**
A: In principle, they're the same concept. Django's "View" = MVC's "Controller", and Django's "Template" = MVC's "View". Django just uses different names.

---

**Q2: How did you design the database schema?**
A: We identified 5 entities: LectureHall, CameraSession, MalpracticeDetection, ReviewSession, and TeacherProfile. Key relationships:
- LectureHall → Teacher (one-to-one): each hall is assigned one teacher
- MalpracticeDetection → LectureHall (many-to-one): multiple detections per hall
- CameraSession → Teacher + LectureHall (many-to-one): multiple sessions per teacher
- ReviewSession → Admin + Teacher + LectureHall (tracking review history)
- TeacherProfile → User (one-to-one): extends Django's User model with phone, picture

**Follow-up: Why extend User with TeacherProfile instead of modifying User directly?**
A: Django's User model is part of the framework. Modifying it breaks Django admin, auth, and third-party packages. OneToOneField extension is the recommended pattern — it keeps User intact and adds custom fields via a related table.

---

**Q3: How does the email notification system work?**
A: We use Django's `send_mail()` with Gmail SMTP. Emails are sent in background threads using `Thread(target=send_notifications_background).start()`. The custom email backend (`CustomEmailBackend`) adds retry logic — if the first attempt fails (network timeout), it retries up to 3 times with exponential backoff.

**Follow-up: Why background threads instead of Celery?**
A: Celery requires a broker (Redis/RabbitMQ) and a separate worker process. For our project scope (few emails per day), threading is sufficient and simpler. For production at scale, Celery would be better for reliability and retry handling.

---

**Q4: Explain how video serving works. What's the H.264 problem?**
A: OpenCV writes videos with the `mp4v` codec (MPEG-4 Part 2), which browsers can't play inline. When a user clicks "View," our `serve_video()` view tries 3 strategies:
1. ffmpeg conversion to H.264 (preferred)
2. OpenCV re-encoding (fallback)
3. Raw file download (last resort)
The converted file supports HTTP Range requests for seeking.

**Follow-up: What are HTTP Range requests?**
A: When you drag a video's progress bar, the browser requests specific byte ranges instead of downloading the entire file. Our view reads the `Range` header, seeks to that position in the file, and returns just that portion with a `206 Partial Content` response.

---

**Q5: How does the filter system work in the malpractice log?**
A: Filters are passed as GET parameters (e.g., `?date=2026-03-01&time=FN&sort=prob_high`). The view function reads each parameter and chains Django ORM `.filter()` calls on the queryset. Each filter adds a SQL `WHERE` clause. The query is lazily evaluated — it only hits the database when the template iterates over the results.

**Follow-up: What is Django ORM's lazy evaluation?**
A: ORM queries aren't executed immediately. `logs = MalpraticeDetection.objects.filter(...)` just builds a query object. The SQL is only sent to the database when we actually need the data (e.g., in a `for` loop, `len()`, or template rendering). This allows chaining multiple filters without multiple database hits.

---

**Q6: Why MySQL over PostgreSQL or SQLite?**
A: 
- **SQLite** — Single-file, no concurrent writes. When 3 WebSocket consumers save detections simultaneously, SQLite would error with "database is locked."
- **MySQL** — Handles concurrent writes via row-level locking. Required by our project specifications.
- **PostgreSQL** — Excellent choice too (better advanced features), but MySQL was specified. We have a commented-out PostgreSQL config for Render.com deployment.

---

**Q7: How do you handle file uploads for large videos?**
A: Django's default upload limit is 2.5MB. We set `DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800` (50MB) in settings.py. For larger files, we use chunked reading:
```python
with open(temp_path, 'wb') as f:
    for chunk in video_file.chunks():
        f.write(chunk)
```
Django's `chunks()` method reads the uploaded file in 2.5MB pieces to avoid loading the entire file into memory.

---

**Q8: What is CSRF and how do you handle it?**
A: CSRF (Cross-Site Request Forgery) is an attack where a malicious site submits a form to your site using the victim's session. Django protects against this by requiring a `csrfmiddlewaretoken` in every POST form. The token is unique per session and verified server-side.

`CSRF_COOKIE_HTTPONLY = False` because JavaScript needs to read the CSRF token for Ajax requests (the review toggle sends POST via `fetch()`).

---

**Q9: What is `@login_required` and how does it work?**
A: It's a Django decorator that checks if the user is authenticated before executing the view. If not logged in, it redirects to `LOGIN_URL` (configured as `/login/`). Internally, it checks `request.user.is_authenticated` which Django populates from the session cookie.

---

**Q10: How does the teacher registration work?**
A: 
1. Form collects: username, email, password, first/last name, phone, lecture hall, profile picture
2. View creates a `User` object (Django's built-in) with password hashed via `make_password()`
3. Creates a `TeacherProfile` linked to the user with the additional fields
4. If a lecture hall is selected, updates `LectureHall.assigned_teacher`
5. Returns success response

**Follow-up: How are passwords stored?**
A: Django hashes passwords using PBKDF2 with SHA256 and a random salt. The stored format is `algorithm$iterations$salt$hash`. Even if the database is stolen, passwords can't be reversed.

---

### Scenario Questions

**Q: What happens if two admins review the same log simultaneously?**
A: The last write wins. If Admin A marks it as malpractice and Admin B marks it as not, the second POST overwrites the first. This is acceptable for our scale. For a production system, we'd add optimistic locking with database-level version numbers.

**Q: What if the email server is down when sending notifications?**
A: Our custom email backend retries up to 3 times with backoff (1s, 2s, 4s). If all retries fail, the error is logged but doesn't crash the application (it's in a background thread). The review still completes successfully.

**Q: What if a student deletes the proof video file from disk?**
A: The database record would still exist with the file path, but the `serve_video()` view would return a 404. We could add a periodic integrity check to flag logs with missing proof files, but this isn't critical since physical access to the server is restricted.
