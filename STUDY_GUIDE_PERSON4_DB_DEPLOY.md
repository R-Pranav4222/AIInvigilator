# STUDY GUIDE — PERSON 4: Database / Deployment / Integration / Notifications

## AI Invigilator — B.Tech Final Year Project Evaluation Guide

---

# PART A — WORK ASSIGNMENT & SCOPE

## A.1 What You "Built"

You are responsible for the **data layer, deployment infrastructure, external service integrations, and project wiring** — everything that connects the application end-to-end.

| Area | Files | Lines (approx.) |
|------|-------|-----------------|
| Database Models | `app/models.py` | 110 |
| Database Migrations | `app/migrations/` (20 migration files) | ~620 |
| Admin Panel | `app/admin.py` | 12 |
| Django Forms | `app/forms.py` | 20 |
| Project Settings | `app/settings.py` | 236 |
| URL Routing | `app/urls.py` | 50 |
| ASGI Config | `app/asgi.py` | 25 |
| WSGI Config | `app/wsgi.py` | 10 |
| WebSocket Routing | `app/routing.py` | 14 |
| Server Starter | `start_server.py` | 160 |
| Email Backend | `app/custom_email_backend.py` | 30 |
| Utilities (SMS, SSH, Scripts) | `app/utils.py` | 120 |
| Dockerfile | `Dockerfile` | 28 |
| Requirements Files | `requirements.txt`, `requirements_gpu.txt` | 200 |
| Entry Point | `manage.py` | 22 |
| **TOTAL** | **~25 files** | **~1,630 lines** |

## A.2 Technology Stack (Infrastructure)

| Technology | Version | Role |
|-----------|---------|------|
| **MySQL** | 8.x | Primary relational database |
| **PostgreSQL** | 15+ | Production DB option (Render deployment) |
| **Django ORM** | 6.0.2 | Object-Relational Mapper + migrations |
| **Django Channels** | 4.3.2 | WebSocket support via ASGI |
| **Daphne** | 4.2.1 | ASGI server (HTTP + WebSocket) |
| **Redis** | 7.2 | Channel layer backend (production) |
| **Gunicorn** | 23.0.0 | WSGI server (alternative deployment) |
| **WhiteNoise** | 6.9.0 | Static file serving in production |
| **Twilio** | 9.5.1 | SMS notification API |
| **Gmail SMTP** | — | Email notifications |
| **pyngrok** | 7.5.0 | Public tunnel for remote demos |
| **Docker** | — | Containerised deployment |
| **django-environ** | 0.12.0 | Environment variable management |
| **Paramiko** | 3.5.1 | SSH remote script execution |

---

# PART B — IMPLEMENTATION DEEP-DIVE

## B.1 Database Schema (Entity-Relationship)

### B.1.1 ER Diagram

```
┌──────────────────┐     ┌──────────────────────────┐
│   User (Django)  │     │     LectureHall           │
│──────────────────│     │──────────────────────────│
│ id (PK)          │◄──┐ │ id (PK)                  │
│ username         │   │ │ building (choices)        │
│ password (hashed)│   │ │ hall_name                 │
│ email            │   └─│ assigned_teacher (FK→User)│  OneToOne
│ first_name       │     └──────────┬───────────────┘
│ last_name        │                │
│ is_superuser     │                │
│ is_staff         │                │
│ date_joined      │                │
└──────┬───────────┘                │
       │                            │
       │ OneToOne                   │ OneToOne (optional)
       ▼                            ▼
┌──────────────────────┐  ┌──────────────────────────┐
│   TeacherProfile     │  │                          │
│──────────────────────│  │                          │
│ id (PK)              │  │                          │
│ user (FK→User)       │──┘                          │
│ phone                │                              │
│ profile_picture      │                              │
│ lecture_hall (FK→LH)─┼──────────────────────────────┘
│ is_online            │
│ last_seen            │
└──────────────────────┘

┌───────────────────────────────────┐
│       CameraSession               │
│───────────────────────────────────│
│ id (PK)                           │
│ teacher (FK→User)       CASCADE   │
│ lecture_hall (FK→LH)    CASCADE   │
│ status (choices: requested/       │
│         active/stopped/denied)    │
│ started_at                        │
│ stopped_at                        │
│ created_at (auto)                 │
└───────────────────────────────────┘

┌───────────────────────────────────┐
│     MalpraticeDetection           │
│───────────────────────────────────│
│ id (PK)                           │
│ date                              │
│ time                              │
│ malpractice (type name)           │
│ proof (file path)                 │
│ is_malpractice (nullable bool)    │
│ verified                          │
│ lecture_hall (FK→LH)    SET_NULL  │
│ probability_score (float 0-100)   │
│ source_type (live/recorded)       │
│ uploaded_by (FK→User)   SET_NULL  │
│ teacher_visible (bool)            │
└───────────────────────────────────┘

┌───────────────────────────────────┐
│        ReviewSession              │
│───────────────────────────────────│
│ id (PK)                           │
│ admin_user (FK→User)    CASCADE   │
│ lecture_hall (FK→LH)    CASCADE   │
│ teacher (FK→User)       CASCADE   │
│ review_type (live/recorded)       │
│ session_date                      │
│ session_start_time                │
│ session_end_time                  │
│ logs_reviewed (int)               │
│ logs_flagged (int)                │
│ email_sent (bool)                 │
│ created_at (auto)                 │
└───────────────────────────────────┘
```

### B.1.2 Model Details

#### 1. `LectureHall`

```python
class LectureHall(models.Model):
    BUILDING_CHOICES = [
        ('MAIN', 'Main Block'),
        ('KE', 'Second Block'),
        ('PG', 'Third Block'),
    ]
    building = models.CharField(max_length=50, choices=BUILDING_CHOICES)
    hall_name = models.CharField(max_length=50)
    assigned_teacher = models.OneToOneField(User, on_delete=models.SET_NULL,
                                            null=True, blank=True)
```

**Key points:**
- `OneToOneField` ensures one teacher per hall and vice versa
- `on_delete=SET_NULL` — if the user is deleted, the hall remains but becomes unassigned
- `BUILDING_CHOICES` restricts input to valid building codes via Django validation
- `__str__` returns `"MAIN - LH1"` format for admin readability

#### 2. `TeacherProfile` (Extends Django User)

```python
class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    lecture_hall = models.OneToOneField(LectureHall, on_delete=models.SET_NULL,
                                        null=True, blank=True)
    is_online = models.BooleanField(default=False, db_index=True)
    last_seen = models.DateTimeField(null=True, blank=True)
```

**Key points:**
- Extends Django's built-in `User` model using **OneToOne profile pattern** (not abstract user subclass)
- `CASCADE` on user — deleting a user removes their profile
- `SET_NULL` on lecture_hall — deleting a hall doesn't delete the profile
- `ImageField` requires the `Pillow` library; stores files in `media/profile_pics/`
- `is_online` and `last_seen` are managed by WebSocket consumers (set on connect/disconnect)
- `db_index=True` on `is_online` — frequently filtered to show online/offline teachers in the admin grid

#### 3. `CameraSession`

```python
class CameraSession(models.Model):
    STATUS_CHOICES = [
        ('requested', 'Requested by Admin'),
        ('active', 'Camera Active'),
        ('stopped', 'Camera Stopped'),
        ('denied', 'Denied by Teacher'),
    ]
    teacher = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='camera_sessions')
    lecture_hall = models.ForeignKey(LectureHall, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested', db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
```

**Key points:**
- `ForeignKey` (not OneToOne) — a teacher can have multiple camera sessions over time
- `related_name='camera_sessions'` enables reverse lookup: `user.camera_sessions.all()`
- `auto_now_add=True` sets `created_at` only on first save (never changes)
- `null=True` on `started_at`/`stopped_at` — they're set later when the session state changes
- State machine: `requested → active → stopped` or `requested → denied`
- `ordering = ['-created_at']` — newest sessions first by default
- `db_index=True` on `status` — frequently filtered when checking active/requested sessions

#### 4. `MalpraticeDetection` (Core Data Model)

```python
class MalpraticeDetection(models.Model):
    SOURCE_CHOICES = [('live', 'Live Camera'), ('recorded', 'Recorded Video')]

    date = models.DateField(null=True, db_index=True)
    time = models.TimeField(null=True)
    malpractice = models.CharField(max_length=150)      # Detection type name
    proof = models.CharField(max_length=150)             # File path to proof image/video
    is_malpractice = models.BooleanField(null=True)      # Nullable tri-state
    verified = models.BooleanField(default=False, db_index=True)
    lecture_hall = models.ForeignKey(LectureHall, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    probability_score = models.FloatField(null=True, blank=True, db_index=True)
    source_type = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='live', db_index=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='uploaded_logs')
    teacher_visible = models.BooleanField(default=False, db_index=True)
```

**Key points:**
- `is_malpractice` is `NullBooleanField` in effect — `True` (confirmed), `False` (dismissed), `None` (unreviewed)
- `proof` stores a relative file path (e.g., `uploaded_videos/frame_001.jpg`), not an `ImageField`
- `teacher_visible = False` by default — teachers can only see logs after admin completes a review session
- `SET_NULL` on both ForeignKeys — prevents data loss if a hall or user is deleted
- `probability_score` ranges 0–100 — set by the ML models
- Written to by both live camera stream (consumers.py) and video upload processing (views.py)
- `db_index=True` on `date`, `verified`, `probability_score`, `source_type`, `teacher_visible` — these fields are used in dashboard filters and sorting, so indexing significantly speeds up queries on large datasets

#### 5. `ReviewSession`

```python
class ReviewSession(models.Model):
    REVIEW_TYPE_CHOICES = [('live', 'Live Camera'), ('recorded', 'Recorded Video')]

    admin_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='review_sessions')
    lecture_hall = models.ForeignKey(LectureHall, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='reviewed_sessions')
    review_type = models.CharField(max_length=10, choices=REVIEW_TYPE_CHOICES)
    session_date = models.DateField(default=timezone.now)
    session_start_time = models.TimeField(null=True, blank=True)
    session_end_time = models.TimeField(null=True, blank=True)
    logs_reviewed = models.IntegerField(default=0)
    logs_flagged = models.IntegerField(default=0)
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Key points:**
- Records when admin completes a review — crucial for audit trail
- `CASCADE` on all FKs — if admin, teacher, or hall is deleted, review record is also removed
- `email_sent` tracks whether the notification email was successfully sent
- `default=timezone.now` (without parentheses) — creates a callable default that evaluates at save time

---

## B.2 Django ORM / Migrations System

### B.2.1 How Migrations Work

```
Developer changes models.py
          ↓
  python manage.py makemigrations
          ↓
  Generates migration file (e.g., 0018_malpratice...)
          ↓
  python manage.py migrate
          ↓
  Executes SQL: ALTER TABLE / CREATE TABLE / etc.
```

**Migration file anatomy:**
```python
class Migration(migrations.Migration):
    dependencies = [
        ('app', '0017_auto_20260225_0107'),      # Must run after this
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name='malpraticedetection',
            name='source_type',
            field=models.CharField(choices=[...], default='live', max_length=10),
        ),
        migrations.CreateModel(
            name='CameraSession',
            fields=[...],
        ),
    ]
```

### B.2.2 Migration History (20 Migrations)

| Migration | What It Does |
|-----------|-------------|
| `0001_initial` | Created initial models: `InterviewAnalysis`, `regtable` (legacy models from earlier project phase) |
| `0002` – `0007` | Iterative schema changes during early development |
| `0008` – `0012` | TeacherProfile ↔ LectureHall relationship iterations (added, renamed, restructured) |
| `0013` | Altered `MalpraticeDetection.lecture_hall` FK |
| `0014` | Updated `LectureHall.building` choices |
| `0015` – `0016` | Changed `verified` field behaviour |
| `0017` | Auto-generated changes (Feb 2026) |
| `0018` | **Major expansion:** Added `source_type`, `teacher_visible`, `uploaded_by` to MalpraticeDetection; Created `CameraSession` and `ReviewSession` models; Added `is_online`, `last_seen` to TeacherProfile |
| `0019` | Altered `profile_picture` field on TeacherProfile |
| `0020` | **Performance:** Added `db_index=True` to frequently queried fields — `MalpraticeDetection.date`, `.verified`, `.probability_score`, `.source_type`, `.teacher_visible`; `CameraSession.status`; `TeacherProfile.is_online` |

### B.2.3 Key ORM Operations Used in the Project

```python
# Create a new record
MalpraticeDetection.objects.create(
    date=today, time=now, malpractice='phone_usage',
    proof='uploaded_videos/frame_001.jpg',
    probability_score=87.5, source_type='live',
    lecture_hall=hall
)

# Filter with multiple conditions (AND)
logs = MalpraticeDetection.objects.filter(
    lecture_hall=hall,
    source_type='live',
    teacher_visible=True
)

# Q objects for complex queries (OR)
logs = MalpraticeDetection.objects.filter(
    Q(malpractice__icontains=search) | Q(lecture_hall__hall_name__icontains=search)
)

# Aggregate / Count
from django.db.models import Count
counts = logs.values('malpractice').annotate(count=Count('id'))

# Reverse FK lookup
sessions = user.camera_sessions.filter(status='active')

# Update multiple records
MalpraticeDetection.objects.filter(
    lecture_hall=hall, is_malpractice=True, teacher_visible=False
).update(teacher_visible=True)

# Delete with file cleanup
log = MalpraticeDetection.objects.get(id=log_id)
if log.proof and os.path.exists(media_path):
    os.remove(media_path)
log.delete()
```

### B.2.4 Relationship Summary

| Relationship | Type | on_delete | Reason |
|-------------|------|-----------|--------|
| LectureHall → User (assigned_teacher) | OneToOne | SET_NULL | Hall persists if teacher deleted |
| TeacherProfile → User | OneToOne | CASCADE | Profile is meaningless without user |
| TeacherProfile → LectureHall | OneToOne | SET_NULL | Profile persists if hall deleted |
| CameraSession → User | ForeignKey | CASCADE | Sessions belong to user lifecycle |
| CameraSession → LectureHall | ForeignKey | CASCADE | Sessions belong to hall lifecycle |
| MalpraticeDetection → LectureHall | ForeignKey | SET_NULL | Preserve detection data even if hall deleted |
| MalpraticeDetection → User (uploaded_by) | ForeignKey | SET_NULL | Preserve data even if uploader deleted |
| ReviewSession → User (admin) | ForeignKey | CASCADE | Review belongs to admin |
| ReviewSession → User (teacher) | ForeignKey | CASCADE | Review belongs to teacher |
| ReviewSession → LectureHall | ForeignKey | CASCADE | Review tied to specific hall |

**Design principle:** `SET_NULL` for data preservation (malpractice evidence), `CASCADE` for lifecycle coupling (sessions, profiles, reviews).

---

## B.3 Django Settings (`settings.py` — 236 lines)

### B.3.1 Environment Variable Management

```python
import environ
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY', default='django-insecure-...')
DEBUG = env('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = env('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')
```

**`.env` file structure (NOT committed to Git):**
```
SECRET_KEY=your-random-50-char-string
DEBUG=True
DB_NAME=aiinvigilator
DB_USER=root
DB_PASS=password
DB_HOST=localhost
DB_PORT=3306
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+1234567890
ALLOWED_WEBSOCKET_ORIGINS=http://localhost:8000
```

**Why `django-environ`?** Separates secrets from code. The `.env` file is in `.gitignore`, so credentials never enter version control. Each deployment environment (dev/staging/production) has its own `.env`.

### B.3.2 Database Configuration

**Local development (MySQL):**
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

**`STRICT_TRANS_TABLES`** — Forces MySQL to reject invalid data (silently truncated strings, invalid dates) instead of silently inserting bad data. Without this, MySQL might truncate a 200-char string to 150 chars without an error.

**Production (PostgreSQL — commented out):**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASS'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT', default='5432'),
    }
}
```

The project supports **two database backends** — MySQL for local development and PostgreSQL for cloud deployment (Render). The Django ORM abstracts the SQL differences.

### B.3.3 ASGI / Channel Layer Configuration

```python
INSTALLED_APPS = [
    'daphne',     # MUST be first — overrides Django's default runserver
    ...
    'channels',
    'app',
]

ASGI_APPLICATION = 'app.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        # Production: Redis
        # 'BACKEND': 'channels_redis.core.RedisChannelLayer',
        # 'CONFIG': { 'hosts': [('127.0.0.1', 6379)] },

        # Development: In-memory
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
        'CONFIG': { 'capacity': 1000, 'expiry': 10 },
    },
}
```

**InMemoryChannelLayer** — Single-process only, suitable for development. Messages expire after 10 seconds; buffer holds 1000 messages.

**RedisChannelLayer** — Required for production / multi-process. Redis acts as the message broker so all Daphne worker processes can share the same channel state.

### B.3.4 Middleware Stack

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',      # Static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

**WhiteNoise** is placed immediately after `SecurityMiddleware` so it intercepts static file requests before they hit Django's view layer — much faster than Django serving static files.

### B.3.5 Security Settings

```python
# Always-on security
X_FRAME_OPTIONS = 'DENY'                   # Prevents iframe embedding (clickjacking)
SECURE_CONTENT_TYPE_NOSNIFF = True          # Prevents MIME-type sniffing
SESSION_COOKIE_AGE = 3600                   # 1 hour session timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE = True      # Session dies when browser closes
SESSION_COOKIE_HTTPONLY = True               # JS can't read session cookie
CSRF_COOKIE_HTTPONLY = False                 # Must be False — JS needs CSRF token for AJAX

# Production-only (when DEBUG=False)
if not DEBUG:
    SECURE_SSL_REDIRECT = True              # Force HTTPS
    SESSION_COOKIE_SECURE = True            # Cookies over HTTPS only
    CSRF_COOKIE_SECURE = True               # CSRF cookie over HTTPS only
    SECURE_HSTS_SECONDS = 31536000          # HSTS for 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True   # HSTS includes subdomains
    SECURE_HSTS_PRELOAD = True              # Submit to browser HSTS preload list
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

**Why `CSRF_COOKIE_HTTPONLY = False`?** The frontend JavaScript needs to read the CSRF token from the cookie (via `getCookie('csrftoken')`) for AJAX POST requests. If `HttpOnly` were `True`, JavaScript couldn't access it.

### B.3.6 Static & Media Files

```python
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')    # collectstatic output
STATICFILES_DIRS = (str(BASE_DIR.joinpath('static')),)  # Source static files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')            # User uploads
```

In development, `django.conf.urls.static` serves media files:
```python
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

In production, WhiteNoise serves static files and media would use cloud storage (S3, etc.).

### B.3.7 File Upload Limits

```python
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800   # 50MB for general uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800   # 50MB for file uploads
```

Video uploads >50MB are handled via streaming in the `process_video` view (chunked read).

---

## B.4 ASGI & WebSocket Infrastructure

### B.4.1 ASGI Application (`asgi.py`)

```python
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from app.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http":      get_asgi_application(),              # Django handles HTTP
    "websocket": AuthMiddlewareStack(                 # Channels handles WebSocket
        URLRouter(websocket_urlpatterns)
    ),
})
```

**`ProtocolTypeRouter`** — Splits traffic by protocol type. HTTP goes to Django, WebSocket goes to Channels.

**`AuthMiddlewareStack`** — Extracts the user from the session cookie during the WebSocket handshake. After this, `self.scope['user']` is available in consumers.

### B.4.2 WebSocket URL Routing (`routing.py`)

```python
websocket_urlpatterns = [
    re_path(r'ws/notifications/$',       NotificationConsumer.as_asgi()),
    re_path(r'ws/camera/stream/$',       CameraStreamConsumer.as_asgi()),
    re_path(r'ws/camera/admin-grid/$',   AdminGridConsumer.as_asgi()),
]
```

Three separate WebSocket endpoints:
| Endpoint | Consumer | Purpose |
|----------|----------|---------|
| `/ws/notifications/` | NotificationConsumer | Control plane — status, requests, alerts |
| `/ws/camera/stream/` | CameraStreamConsumer | Teacher sends frames, receives ML-processed frames |
| `/ws/camera/admin-grid/` | AdminGridConsumer | Admin receives all live camera frames |

### B.4.3 WSGI vs ASGI

| Feature | WSGI (`wsgi.py`) | ASGI (`asgi.py`) |
|---------|-------------------|-------------------|
| Protocol | HTTP only | HTTP + WebSocket |
| Concurrency | Synchronous | Async (asyncio) |
| Server | Gunicorn | Daphne |
| Used when | Legacy HTTP-only deployment | Full application (Docker + dev) |

The Dockerfile uses Daphne (ASGI) which handles both HTTP and WebSocket connections. This provides full functionality including live camera streaming. For development, `start_server.py` also starts Daphne with additional features like auto-migration and ngrok tunneling.

---

## B.5 URL Routing (`urls.py` — 50 lines)

### B.5.1 URL Pattern Organisation

```python
urlpatterns = [
    # Admin panel
    path('admin/', admin.site.urls),

    # Public pages
    path('', views.index),
    path('index', views.index, name='index'),
    path('login/', views.login, name='login'),
    path('login/addlogin', views.addlogin, name='addlogin'),
    path('register/teacher/', views.teacher_register, name='teacher_register'),

    # Authenticated pages
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('logout/', views.logout, name='logout'),

    # Malpractice log CRUD
    path('malpractice_log/', views.malpractice_log, name='malpractice_log'),
    path('review_malpractice/', views.review_malpractice, name='review_malpractice'),
    path('complete_review_session/', views.complete_review_session, ...),
    path('ai_bulk_action/', views.ai_bulk_action, ...),
    path('delete_malpractice/<int:log_id>/', views.delete_malpractice, ...),
    path('delete_all_logs/', views.delete_all_logs, ...),
    path('delete_selected_logs/', views.delete_selected_logs, ...),

    # Admin management
    path('manage-lecture-halls/', views.manage_lecture_halls, ...),
    path('view_teachers/', views.view_teachers, ...),

    # Camera system
    path('run_cameras/', views.run_cameras_page, ...),
    path('teacher_cameras/', views.teacher_cameras_page, ...),
    path('trigger_camera_scripts/', views.trigger_camera_scripts, ...),
    path('stop_camera_scripts/', views.stop_camera_scripts, ...),

    # Video processing
    path('upload_video/', views.upload_video, ...),
    path('process_video/', views.process_video, ...),
    path('stream_video_processing/<str:session_id>/', views.stream_video_processing, ...),
    path('get_processing_stats/<str:session_id>/', views.get_processing_stats, ...),
    path('serve_video/', views.serve_video, ...),
]
```

**URL naming convention:** `name='malpractice_log'` enables reverse resolution in templates: `{% url 'malpractice_log' %}` and in Python: `reverse('malpractice_log')`.

**Path converters:** `<int:log_id>` captures an integer from the URL (e.g., `/delete_malpractice/42/`) and passes it as `log_id` parameter to the view function.

**Media URL routing:**
```python
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```
Only active in development — serves files from `media/` directory. In production, a CDN or cloud storage serves media.

---

## B.6 Django Admin Panel (`admin.py`)

```python
from django.contrib import admin
from .models import LectureHall, TeacherProfile, MalpraticeDetection, CameraSession, ReviewSession

admin.site.register(LectureHall)
admin.site.register(MalpraticeDetection)
admin.site.register(CameraSession)
admin.site.register(ReviewSession)
```

Additionally, `TeacherProfile` has a custom admin class (defined in `models.py`):

```python
@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'profile_picture', 'is_online']
    search_fields = ['user__username', 'phone']
```

**`list_display`** controls which columns appear in the admin list view.
**`search_fields`** adds a search bar that searches user__username (double-underscore = related field lookup) and phone.

Accessing the admin panel: `http://localhost:8000/admin/` (requires `is_superuser=True` or `is_staff=True`).

---

## B.7 Forms (`forms.py`)

```python
class EditProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class TeacherProfileForm(forms.ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ['phone', 'profile_picture']
```

**`ModelForm`** auto-generates form fields from model definitions. Provides:
- Field validation (email format, max_length)
- CSRF protection when rendered
- `form.save()` directly creates/updates the model instance
- Template rendering: `{{ form.as_p }}` generates `<p>` tags for each field

---

## B.8 External Service Integrations

### B.8.1 Email Notification (Gmail SMTP)

**Settings:**
```python
EMAIL_BACKEND = 'app.custom_email_backend.CustomEmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
```

**Custom Email Backend** (`custom_email_backend.py`):

```python
class CustomEmailBackend(DjangoEmailBackend):
    def open(self):
        connection = self.connection_class(self.host, self.port, timeout=self.timeout)
        connection.ehlo()
        if self.use_tls:
            connection.starttls()   # Without keyfile/certfile params
            connection.ehlo()
        if self.username and self.password:
            connection.login(self.username, self.password)
        self.connection = connection
        return True
```

**Why custom backend?** Django's default SMTP backend passes `keyfile` and `certfile` as keyword arguments to `starttls()`. Some Python versions (and Gmail's SMTP server) don't accept these params, causing `TypeError`. The custom backend calls `starttls()` without arguments, fixing the compatibility issue.

**Usage in views (complete_review_session):**
```python
send_mail(
    subject='Malpractice Review Completed',
    message=email_body,
    from_email=settings.DEFAULT_FROM_EMAIL,
    recipient_list=[teacher.email],
)
```

### B.8.2 SMS Notification (Twilio)

```python
from twilio.rest import Client

def send_sms_notification(to_phone, message_body):
    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )
    client.messages.create(
        body=message_body,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=to_phone           # E.164 format: +919876543210
    )
```

**Twilio flow:**
1. Admin completes a review session
2. Backend creates `ReviewSession` record
3. `send_mail()` sends email to teacher
4. `send_sms_notification()` sends SMS to teacher's phone number
5. Both are triggered in a background thread to avoid blocking the HTTP response

**Phone format:** Must be E.164 format (`+` followed by country code + number). Example: `+919876543210` for India.

### B.8.3 SSH Remote Script Execution (Paramiko)

```python
def ssh_run_script(ip, username, password, script_path, use_venv=True, venv_path=None):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
    ssh.connect(ip, username=username, password=password)

    script_dir = os.path.dirname(script_path)
    script_name = os.path.basename(script_path)

    command = f'cmd /c "cd /d \"{script_dir}\" && {activation_cmd}python \"{script_name}\""'

    channel = ssh.get_transport().open_session()
    channel.get_pty()
    channel.exec_command(command)

    RUNNING_SCRIPTS[key] = {"mode": "remote", "ssh": ssh, "channel": channel}
```

**Use case:** Running ML detection scripts on remote machines with GPUs. The admin triggers scripts from the web UI, and they execute via SSH on the target machine.

### B.8.4 Local Script Execution

```python
ALLOWED_SCRIPTS = {
    'front.py', 'top_corner.py', 'hand_raise.py', 'leaning.py',
    'passing_paper.py', 'mobile_detection.py', 'hybrid_detector.py',
    'process_uploaded_video.py', 'process_uploaded_video_stream.py',
}

def local_run_script(script_path):
    script_name = os.path.basename(script_path)
    if script_name not in ALLOWED_SCRIPTS:
        return False, f"Script '{script_name}' is not in the allowed scripts list."

    process = subprocess.Popen(
        ['python', script_name],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=script_dir, text=True
    )
    RUNNING_SCRIPTS[key] = {"mode": "local", "process": process}
```

**Security:** Script whitelist prevents command injection — only known ML scripts can be executed. `subprocess.Popen` with list form (not `shell=True`) prevents shell metacharacter attacks.

---

## B.9 Deployment Infrastructure

### B.9.1 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# System dependencies for mysqlclient, cryptography, ffmpeg, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ default-libmysqlclient-dev pkg-config \
    libffi-dev libssl-dev build-essential ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD python manage.py collectstatic --noinput \
    && daphne -b 0.0.0.0 -p 8000 app.asgi:application
```

**Layer explanation:**
1. `python:3.12-slim` — Minimal Python image (~150MB vs 1GB for full); Python 3.12 offers 5–15% speed improvements
2. System packages — `gcc`/`g++` for C extensions, `default-libmysqlclient-dev` for `mysqlclient`, `libffi-dev`/`libssl-dev` for `cryptography`, `ffmpeg` for video conversion (Strategy 1 in `serve_video`)
3. `--no-install-recommends` and `rm -rf /var/lib/apt/lists/*` reduce image size by ~50MB
4. `--no-cache-dir` on pip prevents storing wheel caches inside the image
5. Requirements installed before code copy — leverages Docker layer caching
6. `collectstatic` gathers all static files into `staticfiles/` directory
7. `daphne` serves the app with ASGI — supports both HTTP and WebSocket (full functionality including live camera streaming)

### B.9.2 Start Server Script (`start_server.py` — 160 lines)

A one-click development server launcher that:

```
[1/4] Check MySQL connection
         ↓
[2/4] Run pending migrations (manage.py migrate --run-syncdb)
         ↓
[3/4] Detect LAN IP (socket connection to 8.8.8.8)
         ↓
[4/4] Start ngrok tunnel (optional, --ngrok flag)
         ↓
Start Daphne ASGI server (0.0.0.0:port)
         ↓
Print access banner with local/LAN/public URLs
```

**Key features:**
```python
# LAN IP detection
def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))    # No actual connection—just route lookup
    ip = s.getsockname()[0]
    return ip

# Daphne launch
def start_daphne(host, port):
    cmd = [sys.executable, "-m", "daphne",
           "-b", host, "-p", str(port),
           "app.asgi:application"]
    return subprocess.Popen(cmd, cwd=BASE_DIR)

# ngrok tunnel (for remote demos)
def start_ngrok(port):
    from pyngrok import ngrok, conf
    conf.get_default().region = "in"    # India region
    tunnel = ngrok.connect(port, "http")
    return tunnel.public_url
```

**Usage:**
```bash
python start_server.py                # LAN only
python start_server.py --ngrok        # LAN + public ngrok URL
python start_server.py --port 9000    # Custom port
```

### B.9.3 Requirements Files

**`requirements.txt`** (168 packages) — Complete production dependencies:
- Core: Django 6.0.2, channels 4.3.2, daphne 4.2.1
- Database: mysqlclient 2.2.7, mysql-connector-python 9.2.0, psycopg2-binary 2.9.11
- ML: torch 2.5.1+cu121, ultralytics 8.3.0, mediapipe 0.10.32, opencv-python 4.10.0.84
- Services: twilio 9.5.1, paramiko 3.5.1
- Deployment: gunicorn 23.0.0, whitenoise 6.9.0, pyngrok 7.5.0

**`requirements_gpu.txt`** — Lightweight GPU-specific set:
- Targets CUDA 11.8 (with `--extra-index-url` for PyTorch GPU builds)
- Fewer packages, focused on core + ML

### B.9.4 WhiteNoise (Static Files in Production)

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',    # Serves static files
    ...
]
```

WhiteNoise serves static files directly from the application server, eliminating the need for a separate Nginx/Apache server for static assets. It:
- Compresses files (gzip/brotli)
- Adds caching headers
- Serves from `STATIC_ROOT` (the `staticfiles/` directory after `collectstatic`)

---

## B.10 Notification Flow (End-to-End)

### B.10.1 Complete Review Session Flow

```
Admin clicks "Complete & Notify" on malpractice_log page
          ↓
Frontend sends POST /complete_review_session/
  body: { teacher_id, hall_id, date? }
          ↓
Backend (views.py):
  1. Validate teacher_id, hall_id
  2. Count logs: MalpraticeDetection.objects.filter(
       lecture_hall_id=hall_id, is_malpractice=True
     )
  3. Mark logs visible: .update(teacher_visible=True)
  4. Create ReviewSession record
  5. Spawn background thread:
     a. send_mail() → Gmail SMTP → teacher's email
     b. send_sms_notification() → Twilio API → teacher's phone
     c. Update ReviewSession.email_sent = True
          ↓
HTTP response: { success: true, message: "..." }
```

### B.10.2 Email Content

The review completion email includes:
- Lecture hall name
- Date of review
- Number of logs reviewed vs flagged
- Instruction to log in and check malpractice logs

### B.10.3 SMS Content

Short message: "AI Invigilator: Review completed for [Hall]. [X] malpractice incidents flagged. Check your email for details."

---

## B.11 Channel Layer & Group Messaging

### B.11.1 Channel Groups

| Group Name | Who Joins | Purpose |
|-----------|-----------|---------|
| `notifications_global` | All authenticated users | Broadcast messages |
| `user_{id}` | Specific user | Targeted messages (camera requests) |
| `admin_notifications` | All admins | Admin-specific alerts |
| `camera_stream_{teacher_id}` | Teacher + Admin grid | Frame routing |

### B.11.2 Message Flow Example

```
Admin clicks "Start Camera" for Teacher #5
          ↓
NotificationConsumer.handle_camera_request():
  1. Create CameraSession(teacher_id=5, status='requested')
  2. channel_layer.group_send('user_5', {
       type: 'camera.request',
       session_id: 42
     })
          ↓
Teacher #5's NotificationConsumer receives camera.request
  → Sends JSON to teacher's browser
  → Browser shows confirmation modal
          ↓
Teacher clicks "Accept"
  → Browser sends { type: 'camera_response', response: 'accept' }
          ↓
NotificationConsumer.handle_camera_response():
  1. Update CameraSession(status='active', started_at=now)
  2. channel_layer.group_send('admin_notifications', {
       type: 'session.update', teacher_id: 5, status: 'active'
     })
          ↓
Admin's browser shows teacher tile as "streaming" (cyan pulse)
```

---

# PART C — TESTING & RESULTS

## C.1 Database Testing

| Test | Method | Result |
|------|--------|--------|
| Model creation | Django shell: `LectureHall.objects.create(...)` | All models created successfully |
| Migration apply | `python manage.py migrate` | All 20 migrations applied without errors |
| FK constraints | Delete a user with camera sessions | CASCADE deletes sessions correctly |
| SET_NULL behaviour | Delete a hall with malpractice logs | Logs preserved, `lecture_hall=NULL` |
| OneToOne enforcement | Assign same teacher to 2 halls | `IntegrityError` raised correctly |
| Admin panel | Browse all 5 registered models | All CRUD operations work |

## C.2 Deployment Testing

| Test | Method | Result |
|------|--------|--------|
| Docker build | `docker build -t aiinvigilator .` | Builds successfully (~3 min) |
| MySQL connectivity | `start_server.py` step 1 | Connects and verifies |
| LAN access | `http://<lan-ip>:8000` from another device | Pages load correctly |
| ngrok tunnel | `start_server.py --ngrok` | Public URL works |
| Static file serving | WhiteNoise in production mode | All CSS/JS/images served |
| Migration auto-run | `start_server.py` step 2 | Pending migrations applied |

## C.3 Integration Testing

| Test | Method | Result |
|------|--------|--------|
| Email sending | Complete review → check teacher inbox | Gmail received within 30s |
| SMS delivery | Complete review → check teacher phone | Twilio SMS received within 10s |
| WebSocket auth | Open WS without login | Connection rejected |
| WebSocket reconnect | Close laptop lid and reopen | Auto-reconnects within 3s |
| CSRF protection | POST without token | 403 Forbidden returned |
| .env missing key | Remove DB_NAME from .env | Clear error message on startup |

---

# PART D — VIVA QUESTIONS & ANSWERS (65+ Questions)

## Category 1: Database Models

**Q1: Why did you use Django's built-in User model instead of a custom one?**
A: Django's `User` provides authentication (hashing, sessions, login/logout), admin integration, and permission system out of the box. We extended it with `TeacherProfile` using the OneToOne pattern, which adds phone, profile picture, and lecture hall without modifying the auth system.

**Q2: What is the OneToOne profile pattern?**
A: Instead of modifying Django's `User` model (which affects auth, admin, etc.), we create a separate model (`TeacherProfile`) with `OneToOneField(User)`. Each user has exactly one profile and vice versa. Access: `user.teacherprofile.phone`. This is Django's recommended way to extend User.

**Q3: Why `SET_NULL` for `MalpraticeDetection.lecture_hall` but `CASCADE` for `CameraSession.lecture_hall`?**
A: Malpractice evidence must be preserved even if a hall is restructured or deleted — it's permanent forensic data. Camera sessions are transient operational records tied to a specific hall — if the hall is deleted, old session records are meaningless.

**Q4: What is `auto_now_add=True` vs `auto_now=True`?**
A: `auto_now_add=True` sets the field only when the record is first created (INSERT). `auto_now=True` updates the field every time the record is saved (INSERT and UPDATE). We use `auto_now_add` for `created_at` because creation time should never change.

**Q5: Why is `is_malpractice` a `BooleanField(null=True)` instead of a plain Boolean?**
A: It represents a tri-state: `True` = confirmed malpractice, `False` = dismissed (not malpractice), `None` = not yet reviewed. This allows filtering by review status without a separate field.

**Q6: Explain `related_name` in ForeignKey.**
A: `related_name='camera_sessions'` creates a reverse accessor. Instead of Django's default `user.camerasession_set.all()`, we can write `user.camera_sessions.all()`. For ReviewSession, we have `related_name='review_sessions'` and `related_name='reviewed_sessions'` to distinguish the admin and teacher FKs.

**Q7: What does `choices` do on a model field?**
A: It restricts values to a predefined list, e.g., `STATUS_CHOICES = [('requested', 'Requested by Admin'), ...]`. Django validates input against this list in forms and admin. The first element is the stored value, the second is the human-readable label.

**Q8: What happens if you try to create two LectureHalls assigned to the same teacher?**
A: `IntegrityError` — the `OneToOneField` on `assigned_teacher` creates a UNIQUE constraint in the database. The DB rejects the second assignment.

**Q9: Why `ImageField` for profile_picture but `CharField` for proof?**
A: `ImageField` handles file upload, validation (is it an image?), and storage automatically. `proof` stores a file path string because proof files are generated by the ML system (not uploaded through a form), so they bypass Django's file handling.

**Q10: What is `ordering = ['-created_at']` in Meta?**
A: It sets the default query ordering. `-` means descending (newest first). Every `CameraSession.objects.all()` or `ReviewSession.objects.all()` automatically returns newest records first without needing `.order_by()`.

---

## Category 2: Django ORM & Queries

**Q11: What is the Django ORM?**
A: Object-Relational Mapper — it maps Python classes (models) to database tables and Python operations to SQL queries. `MalpraticeDetection.objects.filter(...)` becomes `SELECT * FROM ... WHERE ...`. It abstracts the database engine so the same code works with MySQL, PostgreSQL, SQLite.

**Q12: What is a Q object and when do you need it?**
A: `Q` objects allow complex queries with OR, NOT operators. `filter()` normally uses AND: `filter(a=1, b=2)` → `WHERE a=1 AND b=2`. For OR: `filter(Q(a=1) | Q(b=2))` → `WHERE a=1 OR b=2`. Used in malpractice log search to search across multiple fields.

**Q13: What is `icontains` in a query filter?**
A: Case-insensitive substring match. `malpractice__icontains='phone'` generates `WHERE malpractice LIKE '%phone%'` (with case folding). The double underscore `__` accesses field lookups.

**Q14: How does `select_related` vs `prefetch_related` work?**
A: `select_related` uses SQL JOIN for ForeignKey/OneToOne — one query. `prefetch_related` uses separate queries for ManyToMany/reverse FKs — avoids cartesian product. Example: `MalpraticeDetection.objects.select_related('lecture_hall')` JOINs the hall table to avoid N+1 queries.

**Q15: What is the N+1 query problem?**
A: Querying 100 malpractice logs then accessing `log.lecture_hall` for each generates 101 queries (1 for logs + 100 for halls). `select_related('lecture_hall')` does it in 1 JOIN query. This is a common performance pitfall.

**Q16: What SQL does `objects.create(...)` generate?**
A: `INSERT INTO table_name (col1, col2, ...) VALUES (val1, val2, ...)`. It also returns the created instance with the auto-generated `id` populated.

**Q17: What is `objects.update()` vs `instance.save()`?**
A: `objects.filter(...).update(field=value)` generates a single `UPDATE` SQL statement — efficient for bulk updates. `instance.save()` saves one record at a time and triggers signals/validation. Use `update()` for batch operations, `save()` when you need signals or validation.

---

## Category 3: Migrations

**Q18: What are Django migrations?**
A: Version control for the database schema. Each migration file represents a set of changes (add field, create table, alter column). `makemigrations` detects model changes and generates migration files. `migrate` applies them to the database.

**Q19: Can you reverse a migration?**
A: Yes, `python manage.py migrate app 0017` rolls back to migration 0017, undoing 0018 and 0019. Django generates reverse SQL (DROP COLUMN, DROP TABLE). Some operations like `RunSQL` need explicit `reverse_sql` to be reversible.

**Q20: Why are there 20 migrations instead of just 1?**
A: Migrations capture the evolution of the schema over time. Each change during development (adding a field, renaming a relationship, changing choices, adding database indexes) creates a new migration. This preserves history and allows rollback to any point.

**Q21: What is `dependencies` in a migration file?**
A: It defines which migrations must run before this one. `('app', '0017_auto...')` means migration 0017 must be applied first. `swappable_dependency(settings.AUTH_USER_MODEL)` ensures the User table exists before creating FKs to it.

**Q22: What happens if two developers create conflicting migrations?**
A: Django detects conflicting migrations (same dependency, different operations) and shows an error. Run `python manage.py makemigrations --merge` to create a merge migration that combines both branches.

**Q23: What does `--run-syncdb` do?**
A: It creates tables for apps that don't have migrations (e.g., third-party apps without migration files). Used in `start_server.py` as a safety net.

---

## Category 4: Settings & Configuration

**Q24: Why use `django-environ` instead of `os.environ`?**
A: `django-environ` reads `.env` files automatically, provides type casting (`cast=bool`), default values, and cleaner syntax. `os.environ` only reads system environment variables and everything is a string.

**Q25: Why is `SECRET_KEY` in the `.env` file?**
A: `SECRET_KEY` is used for cryptographic signing (sessions, CSRF tokens, password reset tokens). If leaked, attackers can forge sessions and bypass CSRF protection. Keeping it in `.env` (which is in `.gitignore`) prevents it from being committed to Git.

**Q26: What is `STRICT_TRANS_TABLES` in MySQL?**
A: It enables strict mode where MySQL rejects invalid data instead of silently fixing it. Without it: inserting a 200-char string into a 150-char column silently truncates to 150 chars. With it: MySQL raises an error. This prevents data corruption.

**Q27: Why two database configurations (MySQL and PostgreSQL)?**
A: MySQL for local development (widely available, team already uses it). PostgreSQL for cloud deployment on Render (their managed DB offering). Django ORM handles the SQL dialect differences transparently.

**Q28: What is the InMemoryChannelLayer and why not use it in production?**
A: InMemoryChannelLayer stores messages in process memory. It only works within a single process. In production with multiple worker processes (load balancing), each process has its own memory — messages would be lost between processes. Redis provides a shared message store across all processes.

**Q29: Explain `SESSION_COOKIE_AGE = 3600`.**
A: Sessions expire after 3600 seconds (1 hour) of inactivity. Combined with `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`, sessions also end when the browser is closed. This limits the window of exposure if a user forgets to log out.

**Q30: What is HSTS and why `31536000` seconds?**
A: HTTP Strict Transport Security — tells browsers to always use HTTPS for this domain. `31536000` seconds = 1 year. After the first HTTPS visit, the browser refuses HTTP connections for 1 year. `SECURE_HSTS_PRELOAD` submits the domain to browser preload lists for day-one HTTPS enforcement.

**Q31: Why `CSRF_COOKIE_HTTPONLY = False`?**
A: The frontend JavaScript reads the CSRF token from the cookie using `getCookie('csrftoken')` for AJAX POST requests. If `HttpOnly` were `True`, JavaScript couldn't access the cookie and AJAX POSTs would fail with 403 errors.

---

## Category 5: ASGI & WebSocket

**Q32: What is ASGI?**
A: Asynchronous Server Gateway Interface — the async successor to WSGI. ASGI supports HTTP, WebSocket, and other async protocols. Django Channels uses ASGI to add WebSocket support to Django.

**Q33: What is `ProtocolTypeRouter`?**
A: It's the top-level router that splits incoming connections by protocol type. `"http"` goes to Django's standard ASGI handler. `"websocket"` goes through `AuthMiddlewareStack` → `URLRouter` → our consumers.

**Q34: How does `AuthMiddlewareStack` work with WebSocket?**
A: During the WebSocket handshake (which is an HTTP upgrade request), Django's session middleware reads the session cookie. `AuthMiddlewareStack` extracts the authenticated user from the session and puts it in `self.scope['user']`. All subsequent messages on that WebSocket connection carry this user context.

**Q35: What is the difference between Daphne and Gunicorn?**
A: Daphne is an ASGI server — handles both HTTP and WebSocket connections asynchronously. Gunicorn is a WSGI server — handles HTTP only, synchronously. Our project needs Daphne for live camera streaming via WebSocket. The Dockerfile uses Daphne to provide full ASGI support including WebSocket in production.

**Q36: What is a "channel layer"?**
A: An abstraction for passing messages between different processes (or different WebSocket connections within the same process). `channel_layer.group_send('user_5', {...})` sends a message to all consumers that joined the `user_5` group, even if they're in different processes.

**Q37: What is `group_send` vs direct send?**
A: `group_send` broadcasts to all consumers in a named group. `self.send_json({...})` sends directly to the specific connected client. Groups enable patterns like "notify all admins" (`admin_notifications` group) or "message a specific teacher" (`user_5` group).

---

## Category 6: Deployment

**Q38: Why `python:3.12-slim` in the Dockerfile?**
A: `slim` is a minimal Debian image (~150MB) with just the Python runtime. The full image is ~1GB with development tools we don't need in production. `3.12` provides 5–15% speed improvements over 3.11 thanks to CPython optimisations, and is compatible with all our dependencies.

**Q39: Why install system packages in the Dockerfile?**
A: `mysqlclient` needs `gcc` and `default-libmysqlclient-dev` for C extension compilation. `cryptography` needs `libffi-dev` and `libssl-dev`. These are build-time dependencies for pip packages that have C components.

**Q40: What is Docker layer caching and how does the Dockerfile leverage it?**
A: Docker caches each instruction's output as a layer. By copying `requirements.txt` first and running `pip install` before copying the application code, we ensure that pip install is only re-run when dependencies change — not on every code change. This makes rebuilds much faster.

**Q41: What does `collectstatic` do?**
A: It copies all static files from `STATICFILES_DIRS` (our `static/` folder) and installed app static directories into `STATIC_ROOT` (`staticfiles/`). WhiteNoise then serves these files. In development, Django serves static files directly from source directories.

**Q42: What is WhiteNoise?**
A: A Python middleware that serves static files directly from the Django application server, eliminating the need for Nginx or Apache just for static files. It adds caching headers, compresses files, and is production-ready for small to medium deployments.

**Q43: What is ngrok and why is it in the project?**
A: ngrok creates a secure tunnel from a public URL to your localhost. For demo purposes, `python start_server.py --ngrok` creates a public URL like `https://abc123.ngrok.io` that external evaluators can access without network configuration. The `region="in"` setting uses India servers for lower latency.

**Q44: How does the LAN IP detection work?**
A: `socket.connect(("8.8.8.8", 80))` creates a UDP socket to Google's DNS server. This doesn't actually send data — it triggers the OS to determine which network interface would be used to reach that destination. `getsockname()[0]` returns the local IP address of that interface, which is the LAN IP.

---

## Category 7: Email & SMS

**Q45: Why use a custom email backend instead of Django's default?**
A: Django's default SMTP backend passes `keyfile` and `certfile` parameters to `starttls()`. Some Python versions and Gmail's SMTP server reject these parameters with `TypeError`. Our custom backend calls `starttls()` without arguments, which works universally.

**Q46: What is a Gmail App Password?**
A: Gmail doesn't allow direct password login for SMTP from applications. You must generate an "App Password" from Google Account → Security → 2-Step Verification → App passwords. This 16-character password goes in `EMAIL_HOST_PASSWORD` in `.env`.

**Q47: How does Twilio SMS work?**
A: Twilio provides a REST API for sending SMS. Our code uses the `twilio` Python SDK. We create a `Client` with account SID + auth token, then call `client.messages.create(body, from_, to)`. Twilio routes the message through their carrier network. The `from_` number must be a Twilio-provisioned number.

**Q48: Why send notifications in a background thread?**
A: Email and SMS are network calls that take 2–10 seconds. If done synchronously in the request handler, the HTTP response would be delayed by that amount. A background thread allows the response to return immediately while notifications send asynchronously.

**Q49: What happens if the email fails?**
A: The `ReviewSession.email_sent` field tracks whether the email was successfully sent. If it fails (bad SMTP config, Gmail quota exceeded), `email_sent` remains `False`. The admin can see this in the admin panel and re-trigger if needed.

---

## Category 8: Security (Infrastructure)

**Q50: What is HSTS preloading?**
A: When `SECURE_HSTS_PRELOAD = True`, the domain can be submitted to browser vendors' hardcoded HSTS lists. Browsers like Chrome ship with this list, so even the first visit to the domain uses HTTPS — no initial HTTP request that could be intercepted.

**Q51: What is `SECURE_PROXY_SSL_HEADER`?**
A: When behind a reverse proxy (like Render, Heroku, Nginx), the proxy terminates SSL and forwards HTTP to Django. The proxy sets `X-Forwarded-Proto: https` header. `SECURE_PROXY_SSL_HEADER` tells Django to trust this header and treat the request as HTTPS.

**Q52: How does the script whitelist prevent command injection?**
A: `ALLOWED_SCRIPTS` is a set of known-safe filenames. Before executing any script, `local_run_script()` checks `if script_name not in ALLOWED_SCRIPTS: return False`. Even if an attacker passes `"; rm -rf / #"` as the script name, it won't match any whitelisted name.

**Q53: Why `subprocess.Popen` with list form instead of `shell=True`?**
A: `shell=True` passes the command through the system shell, which interprets metacharacters (`;`, `|`, `$`, etc.). `Popen(['python', script_name])` executes directly without shell interpretation, so special characters in `script_name` are treated as literal characters, not shell commands.

**Q54: What is Paramiko's `WarningPolicy`?**
A: When connecting via SSH, the server presents a host key. `WarningPolicy` logs a warning for unknown hosts but connects anyway. `RejectPolicy` (recommended for production) rejects unknown hosts. `AutoAddPolicy` silently trusts all hosts (dangerous — susceptible to man-in-the-middle attacks).

---

## Category 9: Channel Layer & Real-Time Architecture

**Q55: How does the admin grid receive frames from multiple teachers?**
A: Each teacher's `CameraStreamConsumer` processes frames through ML and sends binary frames to the `camera_stream_{teacher_id}` group. The `AdminGridConsumer` joins all active stream groups. For performance, `ADMIN_GRID_SENDERS` stores direct send functions to bypass the channel layer for high-frequency frame data.

**Q56: What is `database_sync_to_async`?**
A: Django's ORM is synchronous. WebSocket consumers are async. `database_sync_to_async` wraps a synchronous DB call to run in a thread pool, making it compatible with `async/await`:
```python
@database_sync_to_async
def create_camera_session(self, teacher_id):
    session = CameraSession.objects.create(...)
    return session
```

**Q57: What is the admin disconnect timer?**
A: When the last admin disconnects, a 60-second timer starts. If no admin reconnects within 60 seconds, all active teachers are notified: "Admin has been disconnected for over 60 seconds. Your camera is still streaming but no one is monitoring." This prevents teachers from streaming indefinitely with no viewer.

**Q58: What are `channel_name` and `group_name`?**
A: `channel_name` is a unique identifier for a single WebSocket connection (e.g., `specific.abc123!def456`). `group_name` is a named set of channels that receive broadcast messages (e.g., `admin_notifications`). Multiple channels can join one group.

---

## Category 10: Integration & Architecture

**Q59: How do WebSocket consumers write to the database?**
A: Using `@database_sync_to_async` decorator. Example: when a teacher accepts a camera request, the consumer updates the `CameraSession` status from `requested` to `active` and sets `started_at = timezone.now()`. This is done in a wrapped sync method called from the async consumer.

**Q60: How does the video processing pipeline work end-to-end?**
A: Upload via AJAX → Django view saves file to `media/uploaded_videos/` → spawns ML processing in a thread → ML writes frames to temp directory → `StreamingHttpResponse` serves MJPEG stream → ML writes detections to `MalpraticeDetection` table → completion stats returned via polling endpoint.

**Q61: What is `StreamingHttpResponse` and why use it for video?**
A: It sends the HTTP response in chunks — the server sends data as it's generated, not all at once. For MJPEG, each chunk is a JPEG frame with multipart boundary. The browser receives and displays frames progressively. Standard `HttpResponse` would buffer everything in memory.

**Q62: How does the media file system work?**
A: `MEDIA_ROOT = os.path.join(BASE_DIR, 'media')` is the filesystem root for user uploads. `MEDIA_URL = '/media/'` is the URL prefix. Files are stored as: `media/profile_pics/user1.jpg`, `media/uploaded_videos/exam.mp4`. In development, Django serves these directly. In production, a CDN or cloud storage would be used.

**Q63: What is the role of `manage.py`?**
A: It's Django's command-line entry point. It sets `DJANGO_SETTINGS_MODULE` and delegates to Django's management command framework. Common commands: `runserver`, `migrate`, `makemigrations`, `createsuperuser`, `collectstatic`, `shell`, `test`.

**Q64: How do you create the initial admin user?**
A: `python manage.py createsuperuser` — prompts for username, email, password. This creates a `User` with `is_superuser=True` and `is_staff=True`, granting access to the admin panel and all admin-only features in the application.

**Q65: What is the full request lifecycle for a login?**
A:
1. Browser sends `POST /login/addlogin` with username + password + CSRF token
2. Django middleware: SecurityMiddleware → SessionMiddleware → CsrfViewMiddleware → AuthenticationMiddleware
3. `views.addlogin()`: `authenticate(username, password)` → checks User table's hashed password
4. `auth_login(request, user)` → creates session, sets session cookie
5. `redirect('index')` → returns 302 with `Set-Cookie: sessionid=abc123`
6. Browser follows redirect, sending session cookie
7. On subsequent requests, `AuthenticationMiddleware` reads cookie → loads user from session

---

## Summary Cheat Sheet: Numbers to Remember

| Metric | Value |
|--------|-------|
| Database models | 5 (LectureHall, TeacherProfile, CameraSession, MalpraticeDetection, ReviewSession) |
| Django built-in model used | `User` (from `django.contrib.auth.models`) |
| Total migrations | 20 |
| MySQL STRICT mode | `STRICT_TRANS_TABLES` |
| Default session timeout | 3600 seconds (1 hour) |
| HSTS duration | 31536000 seconds (1 year) |
| File upload limit | 50 MB (52,428,800 bytes) |
| Channel layer capacity | 1000 messages, 10s expiry (InMemory) |
| WebSocket endpoints | 3 (notifications, stream, admin-grid) |
| Channel groups | 4 types (global, user-specific, admin, camera-stream) |
| Admin timeout timer | 60 seconds |
| Total Python packages | 168 |
| Twilio phone format | E.164 (+919876543210) |
| Gmail SMTP port | 587 (TLS) |
| Docker base image | python:3.12-slim |
| Daphne default port | 8000 |
| ngrok region | "in" (India) |
| start_server.py startup steps | 4 (DB check → Migrate → LAN IP → ngrok) |
| Allowed ML scripts | 9 whitelisted |
| on_delete strategies used | SET_NULL (4), CASCADE (6) |
