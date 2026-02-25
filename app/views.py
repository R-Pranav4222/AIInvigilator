# views.py
from django.shortcuts import render
from django.shortcuts import redirect
from .models import *
from threading import Event, Thread
from django.http import JsonResponse, FileResponse, HttpResponse, StreamingHttpResponse
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from .models import TeacherProfile
import json
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from .utils import send_sms_notification
from .forms import EditProfileForm, TeacherProfileForm
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.admin.views.decorators import staff_member_required
from .utils import ssh_run_script, local_run_script
import threading
import os
import subprocess
import tempfile
from .utils import RUNNING_SCRIPTS 
import time
import cv2

# Global stop event
stop_event = Event()


def calculate_retroactive_probability(log):
    """Calculate probability score for existing logs that don't have one.
    
    Uses available data (video file duration + malpractice type) since
    detection metadata wasn't tracked for older logs.
    """
    # Type-based prior probabilities
    type_priors = {
        'Mobile Phone Detected': 0.80,
        'Turning Back': 0.70,
        'Leaning': 0.60,
        'Passing Paper': 0.55,
        'Hand Raised': 0.45,
    }
    type_score = type_priors.get(log.malpractice, 0.50)
    
    # Try to get clip duration from video file
    clip_duration = 0.0
    if log.proof:
        video_path = os.path.join(settings.MEDIA_ROOT, log.proof)
        if os.path.exists(video_path):
            try:
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30
                    clip_duration = total_frames / fps if fps > 0 else 0
                    cap.release()
            except:
                pass
    
    # Duration scoring
    if clip_duration >= 10:
        duration_score = 1.0
    elif clip_duration >= 6:
        duration_score = 0.90
    elif clip_duration >= 4:
        duration_score = 0.75
    elif clip_duration >= 2:
        duration_score = 0.55
    elif clip_duration >= 1:
        duration_score = 0.30
    else:
        duration_score = 0.20
    
    # For retroactive calculation, use simplified 2-factor model:
    # 60% clip duration + 40% type prior
    probability = (duration_score * 0.60 + type_score * 0.40) * 100
    probability = max(0.0, min(100.0, round(probability, 1)))
    
    return probability


def ensure_probability_scores(logs_queryset):
    """Fill in probability scores for any logs that don't have one yet."""
    logs_without_score = logs_queryset.filter(probability_score__isnull=True)
    for log in logs_without_score:
        log.probability_score = calculate_retroactive_probability(log)
        log.save(update_fields=['probability_score'])

def is_admin(user):
    return user.is_superuser


def home(request):
    return render(request,'index.html')


def index(request):
    return render(request,'index.html')


def teacher_register(request):
    if request.method == "POST":
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        username = request.POST.get('username')
        password = request.POST.get('password')
        phone = request.POST.get('phone')
        profile_picture = request.FILES['profile_picture']

        # Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Save profile
        profile = TeacherProfile(user=user, phone=phone, profile_picture=profile_picture)
        profile.save()

        return redirect('login')  # Or any success page
    return render(request, 'teacher_register.html')



def addlogin(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            return redirect('index')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})



def login(request):
    return render(request,'login.html')



@login_required
def logout(request):
    auth_logout(request)
    return redirect('index')


@login_required
def profile(request):
    return render(request, 'profile.html')  # assuming your template is in templates/profile.html


@login_required
def profile_view(request):
    """Render the user's profile page (the one you already have)."""
    return render(request, 'profile.html')  # Your existing page


@login_required
def edit_profile(request):
    """Allow user to edit basic info (User) + teacher-specific info (TeacherProfile)."""
    user = request.user
    # Attempt to fetch or create the TeacherProfile:
    teacher_profile, _ = TeacherProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = EditProfileForm(request.POST, instance=user)
        profile_form = TeacherProfileForm(request.POST, request.FILES, instance=teacher_profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = EditProfileForm(instance=user)
        profile_form = TeacherProfileForm(instance=teacher_profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    return render(request, 'edit_profile.html', context)


@login_required
def change_password(request):
    """Allow user to change their password using Django's built-in PasswordChangeForm."""
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            # Important! Keep user logged in after password change
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was changed successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please fix the error below.')
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'change_password.html', {'form': form})



@login_required
def serve_video(request):
    """Serve proof videos in browser-compatible H.264 format with Range request support.
    
    The ML scripts write videos using OpenCV's mp4v codec (MPEG-4 Part 2),
    which browsers cannot play inline. This view converts them to H.264
    using multiple fallback strategies.
    
    Supports HTTP Range requests for video seeking/scrubbing in the browser player.
    """
    filename = request.GET.get('file', '')
    if not filename:
        return HttpResponse('No file specified', status=400)
    
    # Sanitize filename to prevent directory traversal
    filename = os.path.basename(filename)
    video_path = os.path.join(settings.MEDIA_ROOT, filename)
    
    if not os.path.exists(video_path):
        print(f'[serve_video] Video not found: {video_path}')
        return HttpResponse('Video not found', status=404)
    
    print(f'[serve_video] Serving video: {filename}')
    
    # Check if a cached H.264 version already exists
    cache_dir = os.path.join(settings.MEDIA_ROOT, '_h264_cache')
    os.makedirs(cache_dir, exist_ok=True)
    cached_path = os.path.join(cache_dir, filename)
    
    # Determine which file to serve (cached H.264 or convert first)
    serve_path = None
    
    if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
        print(f'[serve_video] Serving from cache: {cached_path}')
        serve_path = cached_path
    else:
        # --- Strategy 1: System ffmpeg ---
        try:
            print('[serve_video] Trying system ffmpeg...')
            cmd = [
                'ffmpeg', '-y', '-i', video_path,
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-an',  # No audio track
                cached_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
                print('[serve_video] ✅ System ffmpeg conversion successful')
                serve_path = cached_path
            else:
                print(f'[serve_video] System ffmpeg failed: {result.stderr[:200] if result.stderr else "unknown error"}')
        except FileNotFoundError:
            print('[serve_video] System ffmpeg not found')
        except subprocess.TimeoutExpired:
            print('[serve_video] System ffmpeg timed out')
        except Exception as e:
            print(f'[serve_video] System ffmpeg error: {e}')
    
    if not serve_path:
        # --- Strategy 2: imageio-ffmpeg bundled binary ---
        try:
            print('[serve_video] Trying imageio-ffmpeg...')
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            print(f'[serve_video] Found imageio-ffmpeg at: {ffmpeg_exe}')
            cmd = [
                ffmpeg_exe, '-y', '-i', video_path,
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-an',
                cached_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
                print('[serve_video] ✅ imageio-ffmpeg conversion successful')
                serve_path = cached_path
            else:
                print(f'[serve_video] imageio-ffmpeg failed: {result.stderr[:200] if result.stderr else "unknown error"}')
        except ImportError:
            print('[serve_video] imageio-ffmpeg not installed')
        except Exception as e:
            print(f'[serve_video] imageio-ffmpeg error: {e}')

    if not serve_path:
        # --- Strategy 3: OpenCV re-encode with H.264 codec ---
        try:
            print('[serve_video] Trying OpenCV H.264 re-encode...')
            import cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print('[serve_video] OpenCV cannot open source video')
            else:
                fps = cap.get(cv2.CAP_PROP_FPS) or 30
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                print(f'[serve_video] Source: {width}x{height} @ {fps}fps, {total_frames} frames')
                
                codec_options = ['avc1', 'H264', 'X264', 'h264']
                writer = None
                used_codec = None
                
                for codec in codec_options:
                    try:
                        fourcc = cv2.VideoWriter_fourcc(*codec)
                        writer = cv2.VideoWriter(cached_path, fourcc, fps, (width, height))
                        if writer.isOpened():
                            used_codec = codec
                            print(f'[serve_video] OpenCV codec "{codec}" is available')
                            break
                        writer.release()
                        writer = None
                    except Exception as e:
                        writer = None
                
                if writer and writer.isOpened():
                    frame_count = 0
                    while True:
                        ret, frame = cap.read()
                        if not ret:
                            break
                        writer.write(frame)
                        frame_count += 1
                    writer.release()
                    cap.release()
                    
                    if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
                        print(f'[serve_video] ✅ OpenCV re-encode successful')
                        serve_path = cached_path
                else:
                    print('[serve_video] No H.264 codec available in OpenCV')
                
                if cap.isOpened():
                    cap.release()
        except ImportError:
            print('[serve_video] OpenCV not available')
        except Exception as e:
            print(f'[serve_video] OpenCV error: {e}')
    
    if not serve_path:
        # --- Strategy 4 (Last resort): Serve original file ---
        print(f'[serve_video] ⚠️ All conversion failed! Serving original mp4v file')
        serve_path = video_path
    
    # ===== Serve with HTTP Range support (enables video seeking) =====
    file_size = os.path.getsize(serve_path)
    range_header = request.META.get('HTTP_RANGE', '')
    
    if range_header:
        # Parse Range: bytes=start-end
        try:
            range_match = range_header.replace('bytes=', '').split('-')
            range_start = int(range_match[0]) if range_match[0] else 0
            range_end = int(range_match[1]) if range_match[1] else file_size - 1
        except (ValueError, IndexError):
            range_start = 0
            range_end = file_size - 1
        
        # Clamp to valid range
        range_start = max(0, range_start)
        range_end = min(range_end, file_size - 1)
        content_length = range_end - range_start + 1
        
        # Stream the requested range
        f = open(serve_path, 'rb')
        f.seek(range_start)
        data = f.read(content_length)
        f.close()
        
        response = HttpResponse(data, content_type='video/mp4', status=206)
        response['Content-Range'] = f'bytes {range_start}-{range_end}/{file_size}'
        response['Content-Length'] = content_length
        response['Accept-Ranges'] = 'bytes'
        return response
    else:
        # Full file response
        response = FileResponse(open(serve_path, 'rb'), content_type='video/mp4')
        response['Content-Length'] = file_size
        response['Accept-Ranges'] = 'bytes'
        return response


@login_required
def malpractice_log(request):
    # Retrieve filter parameters from the GET request
    date_filter = request.GET.get('date', '').strip()
    time_filter = request.GET.get('time', '').strip()
    malpractice_filter = request.GET.get('malpractice_type', '').strip()
    building_filter = request.GET.get('building', '').strip()
    query = request.GET.get('q', '').strip()
    faculty_filter = request.GET.get('faculty', '').strip()
    assignment_filter = request.GET.get('assigned', '').strip()
    review_filter = request.GET.get('review', '').strip() or 'not_reviewed'
    probability_filter = request.GET.get('probability', '').strip()
    source_filter = request.GET.get('source', '').strip()


    # Base Queryset based on user role
    if request.user.is_superuser:
        logs = MalpraticeDetection.objects.all()
        # Apply review filter for admin
        if review_filter.lower() == 'reviewed':
            logs = logs.filter(verified=True)
        elif review_filter.lower() == 'not_reviewed':
            logs = logs.filter(verified=False)
    else:
        # Teachers only see logs that admin has made visible after review
        assigned_halls = LectureHall.objects.filter(assigned_teacher=request.user)
        logs = MalpraticeDetection.objects.filter(
            lecture_hall__in=assigned_halls,
            verified=True,
            is_malpractice=True,
            teacher_visible=True
        )

    # Ensure all logs have probability scores (retroactive calculation)
    ensure_probability_scores(logs)

    # Apply Filtering
    if date_filter:
        logs = logs.filter(date=date_filter)
    if time_filter:
        if time_filter.upper() == "FN":
            logs = logs.filter(time__lt="12:00:00")
        elif time_filter.upper() == "AN":
            logs = logs.filter(time__gte="12:00:00")
    if malpractice_filter:
        logs = logs.filter(malpractice=malpractice_filter)
    if building_filter:
        logs = logs.filter(lecture_hall__building=building_filter)
    if query:
        logs = logs.filter(lecture_hall__hall_name__icontains=query)
    if faculty_filter:
        logs = logs.filter(lecture_hall__assigned_teacher__id=faculty_filter)
    if assignment_filter:
        if assignment_filter.lower() == "assigned":
            logs = logs.filter(lecture_hall__assigned_teacher__isnull=False)
        elif assignment_filter.lower() == "unassigned":
            logs = logs.filter(lecture_hall__assigned_teacher__isnull=True)
    
    # Apply probability filter
    if probability_filter:
        if probability_filter == 'above_50':
            logs = logs.filter(probability_score__gte=50)
        elif probability_filter == 'below_50':
            logs = logs.filter(probability_score__lt=50)

    # Apply source type filter (live camera vs recorded upload)
    if source_filter:
        if source_filter in ('live', 'recorded'):
            logs = logs.filter(source_type=source_filter)

    logs = logs.order_by('-date', '-time')

    # Update session record count to trigger alert if new logs appear
    record_count = logs.count()
    alert = False
    if "record_count" in request.session:
        if request.session["record_count"] < record_count:
            alert = True
            request.session["record_count"] = record_count
    else:
        request.session["record_count"] = record_count

    context = {
        'result': logs,
        'alert': alert,
        'is_admin': request.user.is_superuser,
        'date_filter': date_filter,
        'time_filter': time_filter,
        'malpractice_filter': malpractice_filter,
        'building_filter': building_filter,
        'query': query,
        'faculty_filter': faculty_filter,
        'assignment_filter': assignment_filter,
        'review_filter': review_filter,
        'probability_filter': probability_filter,
        'source_filter': source_filter,
        'faculty_list': User.objects.filter(teacherprofile__isnull=False, is_superuser=False),
        'buildings': LectureHall.objects.values_list('building', flat=True).distinct(),
    }

    return render(request, 'malpractice_log.html', context)



def send_notifications_background(log_id):
    """Send email and SMS notifications in background thread"""
    try:
        log = MalpraticeDetection.objects.get(id=log_id)
        teacher_user = log.lecture_hall.assigned_teacher
        
        try:
            teacher_profile = teacher_user.teacherprofile
        except TeacherProfile.DoesNotExist:
            print(f"[WARN] No profile found for user: {teacher_user.username}")
            teacher_profile = None

        # Send Email Notification
        subject = 'Malpractice Alert: New Case Reviewed'
        message_body = (
            f"Dear {teacher_user.get_full_name() or teacher_user.username},\n\n"
            f"A malpractice has been detected in your classroom and has been approved by the examination cell.\n\n"
            f"Details:\n"
            f"- 📅 Date: {log.date}\n"
            f"- ⏰ Time: {log.time}\n"
            f"- 🎯 Type: {log.malpractice}\n"
            f"- 🏫 Lecture Hall: {log.lecture_hall.building} - {log.lecture_hall.hall_name}\n\n"
            f"You can view the recorded video proof from your AIInvigilator portal.\n\n"
            f"Best regards,\nAIInvigilator Team"
        )

        try:
            send_mail(subject, message_body, settings.EMAIL_HOST_USER, [teacher_user.email], fail_silently=False)
        except Exception as e:
            print(f"\n[ERROR] Email sending failed: {e}\n")

        # Send SMS Notification if phone is available
        if teacher_profile and teacher_profile.phone:
            sms_message_body = (
                f'''
                \nDear {teacher_user.get_full_name() or teacher_user.username},\n\n'''
                f"🔔 Malpractice Alert\n"
                f"{log.date} | {log.time}\n"
                f"{log.malpractice} detected in {log.lecture_hall.building}-{log.lecture_hall.hall_name}.\n"
                f"\nCheck AIInvigilator for video proof."
            )

            try:
                send_sms_notification(f"+91{teacher_profile.phone.strip()}", sms_message_body)
            except Exception as e:
                print(f"\n[ERROR] SMS sending failed: {e}\n")
    except Exception as e:
        print(f"[ERROR] Background notification failed: {e}")


def review_malpractice(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        data = json.loads(request.body)
        proof_filename = data.get('proof')
        decision = data.get('decision')

        if not proof_filename or decision not in ['yes', 'no']:
            return JsonResponse({'success': False, 'error': 'Invalid data received'})

        # Find the malpractice log
        try:
            log = MalpraticeDetection.objects.get(proof=proof_filename)
        except MalpraticeDetection.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Malpractice log not found'})

        # Update the log
        log.verified = True
        log.is_malpractice = (decision == 'yes')
        # Make visible to teacher after admin review (malpractice decisions only)
        if log.is_malpractice:
            log.teacher_visible = True
        log.save()

        # If approved as malpractice, send notifications in background thread
        if log.is_malpractice and log.lecture_hall and log.lecture_hall.assigned_teacher:
            notification_thread = Thread(target=send_notifications_background, args=(log.id,))
            notification_thread.daemon = True
            notification_thread.start()

        return JsonResponse({'success': True})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON format'})

    except Exception as e:
        print(f"[EXCEPTION] Unexpected error in review_malpractice: {e}")
        return JsonResponse({'success': False, 'error': 'Internal server error'})


@csrf_exempt
@login_required
@user_passes_test(is_admin)
def complete_review_session(request):
    """Complete a review session: create ReviewSession record, set teacher_visible=True
    for all reviewed malpractice logs of a given teacher/hall, and send summary email."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        data = json.loads(request.body)
        teacher_id = data.get('teacher_id')
        hall_id = data.get('hall_id')
        review_date = data.get('date')  # optional: filter by specific date

        if not teacher_id or not hall_id:
            return JsonResponse({'success': False, 'error': 'teacher_id and hall_id required'})

        teacher = User.objects.get(id=teacher_id)
        hall = LectureHall.objects.get(id=hall_id)

        # Get all reviewed malpractice logs for this teacher's hall
        reviewed_logs = MalpraticeDetection.objects.filter(
            lecture_hall=hall,
            verified=True
        )
        if review_date:
            reviewed_logs = reviewed_logs.filter(date=review_date)

        total_reviewed = reviewed_logs.count()
        flagged_count = reviewed_logs.filter(is_malpractice=True).count()

        # Make all malpractice logs visible to teacher
        reviewed_logs.filter(is_malpractice=True).update(teacher_visible=True)

        # Create ReviewSession record
        review_session = ReviewSession.objects.create(
            admin_user=request.user,
            lecture_hall=hall,
            teacher=teacher,
            review_type='live',
            logs_reviewed=total_reviewed,
            logs_flagged=flagged_count,
            email_sent=False
        )

        # Send summary email in background
        def send_review_email(session_id):
            try:
                session = ReviewSession.objects.get(id=session_id)
                teacher_user = session.teacher
                hall_obj = session.lecture_hall

                subject = 'Malpractice Review Session Complete - AIInvigilator'
                message_body = (
                    f"Dear {teacher_user.get_full_name() or teacher_user.username},\n\n"
                    f"The examination cell has completed a malpractice review session.\n\n"
                    f"Review Summary:\n"
                    f"- Lecture Hall: {hall_obj.building} - {hall_obj.hall_name}\n"
                    f"- Date: {session.session_date}\n"
                    f"- Total Logs Reviewed: {session.logs_reviewed}\n"
                    f"- Logs Flagged as Malpractice: {session.logs_flagged}\n\n"
                    f"You can now view the flagged malpractice logs in your Malpractice Log section "
                    f"on the AIInvigilator portal.\n\n"
                    f"Please review the evidence and take appropriate action.\n\n"
                    f"Best regards,\nAIInvigilator System"
                )

                try:
                    send_mail(subject, message_body, settings.EMAIL_HOST_USER,
                              [teacher_user.email], fail_silently=False)
                    session.email_sent = True
                    session.save()
                    print(f"[INFO] Review session email sent to {teacher_user.email}")
                except Exception as e:
                    print(f"[ERROR] Failed to send review email: {e}")

                # Send SMS if available
                try:
                    teacher_profile = teacher_user.teacherprofile
                    if teacher_profile and teacher_profile.phone:
                        sms_body = (
                            f"AIInvigilator: Review complete for {hall_obj.building}-{hall_obj.hall_name}. "
                            f"{session.logs_flagged} malpractice case(s) found out of {session.logs_reviewed} reviewed. "
                            f"Check portal for details."
                        )
                        send_sms_notification(f"+91{teacher_profile.phone.strip()}", sms_body)
                except Exception as e:
                    print(f"[ERROR] SMS notification failed: {e}")

            except Exception as e:
                print(f"[ERROR] Review email background task failed: {e}")

        email_thread = Thread(target=send_review_email, args=(review_session.id,))
        email_thread.daemon = True
        email_thread.start()

        return JsonResponse({
            'success': True,
            'session_id': review_session.id,
            'logs_reviewed': total_reviewed,
            'logs_flagged': flagged_count,
            'message': f'Review complete. {flagged_count} malpractice log(s) shared with teacher. Email notification sent.'
        })

    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Teacher not found'})
    except LectureHall.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Lecture hall not found'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        print(f"[EXCEPTION] complete_review_session error: {e}")
        return JsonResponse({'success': False, 'error': 'Internal server error'})


@csrf_exempt
@login_required
@user_passes_test(is_admin)
def ai_bulk_action(request):
    """Bulk action based on AI probability scores.
    
    Two actions:
    - 'approve_high': Send all logs with probability >= 50% to Reviewed as Malpractice
    - 'dismiss_low': Flag all logs with probability < 50% as Not Malpractice (reviewed)
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})
    
    try:
        data = json.loads(request.body)
        action = data.get('action')
        
        if action not in ['approve_high', 'dismiss_low']:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'})
        
        # Only act on non-reviewed logs
        unreviewed_logs = MalpraticeDetection.objects.filter(verified=False)
        
        # Ensure all have probability scores
        ensure_probability_scores(unreviewed_logs)
        
        if action == 'approve_high':
            # Approve all logs with probability >= 50% as malpractice
            high_prob_logs = unreviewed_logs.filter(probability_score__gte=50)
            count = high_prob_logs.count()
            
            # Send notifications for each approved log that has an assigned teacher
            for log in high_prob_logs:
                log.verified = True
                log.is_malpractice = True
                log.teacher_visible = True
                log.save()
                
                if log.lecture_hall and log.lecture_hall.assigned_teacher:
                    notification_thread = Thread(
                        target=send_notifications_background, args=(log.id,)
                    )
                    notification_thread.daemon = True
                    notification_thread.start()
            
            return JsonResponse({
                'status': 'success', 
                'action': 'approve_high',
                'count': count,
                'message': f'{count} log(s) with ≥50% probability approved as malpractice'
            })
        
        elif action == 'dismiss_low':
            # Dismiss all logs with probability < 50% as not malpractice
            low_prob_logs = unreviewed_logs.filter(probability_score__lt=50)
            count = low_prob_logs.count()
            low_prob_logs.update(verified=True, is_malpractice=False)
            
            return JsonResponse({
                'status': 'success',
                'action': 'dismiss_low', 
                'count': count,
                'message': f'{count} log(s) with <50% probability dismissed as non-malpractice'
            })
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'})
    except Exception as e:
        print(f"[ERROR] AI bulk action failed: {e}")
        return JsonResponse({'status': 'error', 'message': 'Internal server error'})


@csrf_exempt
@login_required
def delete_malpractice(request, log_id):
    """Delete a malpractice log - accessible to both admin and teachers"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

    try:
        # Get the malpractice log
        log = MalpraticeDetection.objects.get(id=log_id)
        
        # Check permissions: admin can delete anything, teachers can only delete logs from their assigned halls
        user = request.user
        if not user.is_superuser:
            # Check if teacher is assigned to this hall
            if not log.lecture_hall or log.lecture_hall.assigned_teacher != user:
                return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        # Delete the video file from media folder
        if log.proof:
            video_path = os.path.join(settings.MEDIA_ROOT, log.proof)
            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except Exception as e:
                    print(f"[WARN] Could not delete video file: {e}")
        
        # Delete the log from database
        log.delete()
        
        return JsonResponse({'success': True})
        
    except MalpraticeDetection.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Log not found'}, status=404)
    except Exception as e:
        print(f"[EXCEPTION] Error deleting malpractice log: {e}")
        return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)


@login_required
@user_passes_test(is_admin)
def delete_all_logs(request):
    """
    Delete all malpractice logs (Admin only)
    Can be filtered by review status
    """
    if request.method == 'POST':
        try:
            review_status = request.POST.get('review_status')
            
            # Base queryset
            logs_to_delete = MalpraticeDetection.objects.all()
            
            # Filter based on review status if provided
            if review_status == 'reviewed':
                logs_to_delete = logs_to_delete.filter(verified=True)
                log_type_msg = "reviewed"
            elif review_status == 'not_reviewed':
                logs_to_delete = logs_to_delete.filter(verified=False)
                log_type_msg = "not reviewed"
            else:
                log_type_msg = ""
                
            count = logs_to_delete.count()
            
            if count == 0:
                messages.warning(request, f'No {log_type_msg} logs found to delete.')
                return redirect('malpractice_log')

            # Delete video files
            for log in logs_to_delete:
                if log.proof:
                    video_path = os.path.join(settings.MEDIA_ROOT, log.proof)
                    if os.path.exists(video_path):
                        try:
                            os.remove(video_path)
                        except Exception as e:
                            print(f"[WARN] Could not delete video file {log.proof}: {e}")
            
            # Delete logs from database
            logs_to_delete.delete()
            
            messages.success(request, f'Successfully deleted {count} {log_type_msg} malpractice log(s).')
            return redirect('malpractice_log')
            
        except Exception as e:
            print(f"[EXCEPTION] Error deleting logs: {e}")
            messages.error(request, 'An error occurred while deleting logs.')
            return redirect('malpractice_log')
    
    return redirect('malpractice_log')


@login_required
@user_passes_test(is_admin)
def delete_selected_logs(request):
    """
    Delete selected malpractice logs (Admin only)
    """
    if request.method == 'POST':
        try:
            # Get the comma-separated list of log IDs
            log_ids_str = request.POST.get('log_ids', '')
            
            if not log_ids_str:
                messages.warning(request, 'No logs selected for deletion.')
                return redirect('malpractice_log')
            
            # Convert to list of integers
            log_ids = [int(id_str.strip()) for id_str in log_ids_str.split(',') if id_str.strip()]
            
            if not log_ids:
                messages.warning(request, 'No valid logs selected for deletion.')
                return redirect('malpractice_log')
            
            # Get the selected logs
            selected_logs = MalpraticeDetection.objects.filter(id__in=log_ids)
            count = selected_logs.count()
            
            # Delete video files for selected logs
            for log in selected_logs:
                if log.proof:
                    video_path = os.path.join(settings.MEDIA_ROOT, log.proof)
                    if os.path.exists(video_path):
                        try:
                            os.remove(video_path)
                        except Exception as e:
                            print(f"[WARN] Could not delete video file {log.proof}: {e}")
            
            # Delete selected logs from database
            selected_logs.delete()
            
            messages.success(request, f'Successfully deleted {count} selected malpractice log(s).')
            return redirect('malpractice_log')
            
        except ValueError as e:
            print(f"[ERROR] Invalid log IDs: {e}")
            messages.error(request, 'Invalid log IDs provided.')
            return redirect('malpractice_log')
        except Exception as e:
            print(f"[EXCEPTION] Error deleting selected logs: {e}")
            messages.error(request, 'An error occurred while deleting selected logs.')
            return redirect('malpractice_log')
    
    return redirect('malpractice_log')



@login_required
@user_passes_test(is_admin)
def manage_lecture_halls(request):
    teachers = User.objects.filter(is_superuser=False)
    error_message = None
    query = request.GET.get('q', '')
    building_filter = request.GET.get('building', '')
    assignment_filter = request.GET.get('assigned', '')

    buildings = LectureHall.objects.values_list('building', flat=True).distinct()
    lecture_halls = LectureHall.objects.all()

    if query:
        lecture_halls = lecture_halls.filter(hall_name__icontains=query)
    if building_filter:
        lecture_halls = lecture_halls.filter(building=building_filter)
    if assignment_filter == "assigned":
        lecture_halls = lecture_halls.exclude(assigned_teacher=None)
    elif assignment_filter == "unassigned":
        lecture_halls = lecture_halls.filter(assigned_teacher=None)

    if request.method == 'POST':
        if 'add_hall' in request.POST:
            hall_name = request.POST.get('hall_name')
            building = request.POST.get('building')
            if hall_name and building:
                if LectureHall.objects.filter(hall_name=hall_name, building=building).exists():
                    error_message = f"Lecture Hall '{hall_name}' already exists in '{building}'."
                else:
                    LectureHall.objects.create(hall_name=hall_name, building=building)
                    return redirect('manage_lecture_halls')

        elif 'map_teacher' in request.POST:
            teacher_id = request.POST.get('teacher_id')
            hall_id = request.POST.get('hall_id')
            try:
                hall = LectureHall.objects.get(id=hall_id)
                teacher = User.objects.get(id=teacher_id)
                LectureHall.objects.filter(assigned_teacher=teacher).update(assigned_teacher=None)
                hall.assigned_teacher = teacher
                hall.save()
                return redirect('manage_lecture_halls')
            except:
                pass

    return render(request, 'manage_lecture_halls.html', {
        'lecture_halls': lecture_halls,
        'teachers': teachers,
        'buildings': buildings,
        'error_message': error_message,
        'query': query,
        'building_filter': building_filter,
        'assignment_filter': assignment_filter
    })



@login_required
@user_passes_test(is_admin)
def view_teachers(request):
    assigned_filter = request.GET.get('assigned', '')
    building_filter = request.GET.get('building', '')

    # Use the reverse relation "lecturehall" (LectureHall.assigned_teacher) 
    teachers = User.objects.filter(is_superuser=False).select_related('lecturehall')
    buildings = LectureHall.objects.values_list('building', flat=True).distinct()

    if assigned_filter == 'assigned':
        teachers = teachers.filter(lecturehall__isnull=False)
    elif assigned_filter == 'unassigned':
        teachers = teachers.filter(lecturehall__isnull=True)

    if building_filter:
        teachers = teachers.filter(lecturehall__building=building_filter)

    context = {
        'teachers': teachers,
        'buildings': buildings,
        'assigned_filter': assigned_filter,
        'building_filter': building_filter,
    }
    return render(request, 'view_teachers.html', context)




@login_required
@user_passes_test(is_admin)
def run_cameras_page(request):
    return render(request, 'run_cameras.html')


@login_required
def teacher_cameras_page(request):
    """Render teacher camera page (non-admin)"""
    return render(request, 'teacher_cameras.html')



@login_required
@user_passes_test(lambda u: u.is_superuser) 
def trigger_camera_scripts(request):
    if request.method == 'POST':
        # List of configurations for each angle
        client_configs = [
            {
                "name": "Top Corner - Host(Allen 2)",
                "script_path": "e:\\witcher\\AIINVIGILATOR\\AIINVIGILATOR\\ML\\front.py",
                "mode": "local"
            },
            # {
            #     "name": "Top Corner Angle - Remote Client(Allen)",
            #     "ip": "192.168.154.9",
            #     "username": "allen",
            #     "password": "5213",
            #     "script_path": "D:\\application\\ML\\top_corner.py",
            #     "mode": "remote",
            #     "use_venv": False  # disable venv activation for this host
            # },
            # {
            #     "name": "Front Angle - Remote Client(Shruti)",
            #     "ip": "192.168.39.145",
            #     "username": "SHRUTI S",
            #     "password": "1234shibu",
            #     "script_path": "C:\\Users\\SHRUTI S\\Documents\\Repos\\AIInvigilator\\application\\application\\ML\\front.py",
            #     "mode": "remote",
            #     "use_venv": False 
            # },
            # {
            #     "name": "Front Angle - Remote Client(Noel)",
            #     "ip": "192.168.1.8",
            #     "username": "noelmathen",
            #     "password": "134652",
            #     "mode": "remote",
            #     "script_path": "C:\\Users\\noelmathen\\Documents\\PROJECTS\\AIInvigilator\\ML\\front.py",
            #     "use_venv": True
            # }
        ]

        # Function to run a given configuration
        def run_on_client(config):
            if config.get("mode") == "remote":
                use_venv = config.get("use_venv", True)
                venv_path = config.get("venv_path", None)
                success, output = ssh_run_script(
                    config["ip"],
                    config["username"],
                    config["password"],
                    config["script_path"],
                    use_venv,
                    venv_path
                )
                print(f"[{config['name']}]: {output if success else 'Error: ' + output}")
            elif config.get("mode") == "local":
                success, output = local_run_script(config["script_path"])
                print(f"[{config['name']}]: {output if success else 'Error: ' + output}")

        # Launch each script in a separate thread
        for config in client_configs:
            threading.Thread(target=run_on_client, args=(config,)).start()

        return JsonResponse({'status': 'started'})
    


@login_required
@user_passes_test(lambda u: u.is_superuser)
def stop_camera_scripts(request):
    if request.method == 'POST':
        # Iterate over a copy of the keys so we can safely remove items
        for key in list(RUNNING_SCRIPTS.keys()):
            handle = RUNNING_SCRIPTS[key]
            if handle.get("mode") == "remote":
                try:
                    channel = handle.get("channel")
                    if channel:
                        # Send Ctrl+C to the remote process
                        channel.send("\x03")
                        # Wait a moment for the remote process to handle the interrupt
                        time.sleep(2)
                        channel.close()
                    ssh = handle.get("ssh")
                    if ssh:
                        ssh.close()
                    print(f"\n[{key}] Remote process terminated successfully.")
                except Exception as e:
                    print(f"\n[{key}] Error terminating remote process: {e}")
            elif handle.get("mode") == "local":
                process = handle.get("process")
                if process:
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                        print(f"\n[{key}] Local process terminated successfully.")
                    except Exception as e:
                        print(f"\n[{key}] Error terminating local process: {e}")
            RUNNING_SCRIPTS.pop(key, None)
        return JsonResponse({"status": "stopped"})
    return JsonResponse({"error": "Invalid request method"}, status=400)


@login_required
def upload_video(request):
    """Render the video upload page with dynamic lecture halls"""
    halls = LectureHall.objects.all().order_by('building', 'hall_name')
    return render(request, 'upload_video.html', {'lecture_halls': halls})


# Store video processing sessions
VIDEO_SESSIONS = {}

@login_required
def process_video(request):
    """Process uploaded video file with ML detection"""
    if request.method == 'POST' and request.FILES.get('video'):
        try:
            video_file = request.FILES['video']
            lecture_hall_id = request.POST.get('lecture_hall', '')
            
            # Save uploaded file to temporary location
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploaded_videos')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Generate unique filename and session ID
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            session_id = f"{timestamp}_{request.user.id}"
            filename = f"{timestamp}_{video_file.name}"
            filepath = os.path.join(upload_dir, filename)
            
            # Save uploaded file
            with open(filepath, 'wb+') as destination:
                for chunk in video_file.chunks():
                    destination.write(chunk)
            
            # Store session info
            VIDEO_SESSIONS[session_id] = {
                'filepath': filepath,
                'lecture_hall_id': lecture_hall_id,
                'status': 'ready',
                'user_id': request.user.id
            }
            
            return JsonResponse({
                'status': 'success',
                'message': 'Video uploaded successfully',
                'session_id': session_id
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required
def stream_video_processing(request, session_id):
    """Stream live video processing frames"""
    import sys
    import cv2
    sys.path.append(os.path.join(settings.BASE_DIR, 'ML'))
    from process_uploaded_video_stream import stream_process_video
    
    # Get session info
    session = VIDEO_SESSIONS.get(session_id)
    if not session:
        return HttpResponse('Session not found', status=404)
    
    # Verify user owns this session
    if session['user_id'] != request.user.id:
        return HttpResponse('Unauthorized', status=403)
    
    def generate():
        try:
            filepath = session['filepath']
            lecture_hall_id = session['lecture_hall_id']
            
            # Process video and yield frames
            for frame_data in stream_process_video(filepath, lecture_hall_id):
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
            
            # Clean up after processing
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print(f"✅ Cleaned up video: {filepath}")
                except:
                    pass
            
            # Remove session
            VIDEO_SESSIONS.pop(session_id, None)
            
        except Exception as e:
            print(f"❌ Stream error: {e}")
            import traceback
            traceback.print_exc()
    
    return StreamingHttpResponse(
        generate(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )


