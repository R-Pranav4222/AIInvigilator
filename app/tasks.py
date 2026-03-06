"""
Celery tasks for AIInvigilator.

Replaces ad-hoc Thread() spawning with reliable, retryable background tasks.
Tasks are automatically discovered by Celery via autodiscover_tasks().

Usage:
    from app.tasks import send_malpractice_notification, send_review_session_email
    send_malpractice_notification.delay(log_id)
    send_review_session_email.delay(session_id)
"""

import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_malpractice_notification(self, log_id):
    """Send email + SMS notification for a confirmed malpractice detection.
    
    Retries up to 3 times with 30-second delay on failure.
    Previously: Thread(target=send_notifications_background, args=(log_id,))
    """
    from .models import MalpraticeDetection, TeacherProfile
    from .utils import send_sms_notification

    try:
        log = MalpraticeDetection.objects.select_related(
            'lecture_hall', 'lecture_hall__assigned_teacher'
        ).get(id=log_id)

        teacher_user = log.lecture_hall.assigned_teacher
        if not teacher_user:
            logger.warning(f"No teacher assigned for log {log_id}")
            return

        try:
            teacher_profile = teacher_user.teacherprofile
        except TeacherProfile.DoesNotExist:
            logger.warning(f"No profile for user: {teacher_user.username}")
            teacher_profile = None

        # Send Email
        subject = 'Malpractice Alert: New Case Reviewed'
        message_body = (
            f"Dear {teacher_user.get_full_name() or teacher_user.username},\n\n"
            f"A malpractice has been detected in your classroom and has been "
            f"approved by the examination cell.\n\n"
            f"Details:\n"
            f"- Date: {log.date}\n"
            f"- Time: {log.time}\n"
            f"- Type: {log.malpractice}\n"
            f"- Lecture Hall: {log.lecture_hall.building} - "
            f"{log.lecture_hall.hall_name}\n\n"
            f"You can view the recorded video proof from your AIInvigilator portal.\n\n"
            f"Best regards,\nAIInvigilator Team"
        )

        try:
            send_mail(
                subject, message_body,
                settings.EMAIL_HOST_USER,
                [teacher_user.email],
                fail_silently=False
            )
            logger.info(f"Email sent to {teacher_user.email} for log {log_id}")
        except Exception as e:
            logger.error(f"Email failed for log {log_id}: {e}")
            raise self.retry(exc=e)

        # Send SMS if phone available
        if teacher_profile and teacher_profile.phone:
            sms_body = (
                f"Malpractice Alert\n"
                f"{log.date} | {log.time}\n"
                f"{log.malpractice} detected in "
                f"{log.lecture_hall.building}-{log.lecture_hall.hall_name}.\n"
                f"Check AIInvigilator for video proof."
            )
            try:
                send_sms_notification(
                    f"+91{teacher_profile.phone.strip()}", sms_body
                )
                logger.info(f"SMS sent to {teacher_profile.phone} for log {log_id}")
            except Exception as e:
                logger.error(f"SMS failed for log {log_id}: {e}")

    except MalpraticeDetection.DoesNotExist:
        logger.error(f"Log {log_id} not found")
    except Exception as e:
        logger.error(f"Notification task failed for log {log_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_review_session_email(self, session_id):
    """Send summary email + SMS after a review session is completed.
    
    Retries up to 3 times with 30-second delay on failure.
    Previously: Thread(target=send_review_email, args=(session_id,))
    """
    from .models import ReviewSession, TeacherProfile
    from .utils import send_sms_notification

    try:
        session = ReviewSession.objects.select_related(
            'teacher', 'lecture_hall'
        ).get(id=session_id)

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
            f"You can now view the flagged malpractice logs in your "
            f"Malpractice Log section on the AIInvigilator portal.\n\n"
            f"Please review the evidence and take appropriate action.\n\n"
            f"Best regards,\nAIInvigilator System"
        )

        try:
            send_mail(
                subject, message_body,
                settings.EMAIL_HOST_USER,
                [teacher_user.email],
                fail_silently=False
            )
            session.email_sent = True
            session.save(update_fields=['email_sent'])
            logger.info(f"Review email sent to {teacher_user.email} "
                        f"for session {session_id}")
        except Exception as e:
            logger.error(f"Review email failed for session {session_id}: {e}")
            raise self.retry(exc=e)

        # Send SMS if available
        try:
            teacher_profile = teacher_user.teacherprofile
            if teacher_profile and teacher_profile.phone:
                sms_body = (
                    f"AIInvigilator: Review complete for "
                    f"{hall_obj.building}-{hall_obj.hall_name}. "
                    f"{session.logs_flagged} malpractice case(s) found out of "
                    f"{session.logs_reviewed} reviewed. Check portal for details."
                )
                send_sms_notification(
                    f"+91{teacher_profile.phone.strip()}", sms_body
                )
        except Exception as e:
            logger.error(f"SMS failed for session {session_id}: {e}")

    except ReviewSession.DoesNotExist:
        logger.error(f"ReviewSession {session_id} not found")
    except Exception as e:
        logger.error(f"Review email task failed for session {session_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_bulk_notifications(self, log_ids):
    """Send notifications for multiple malpractice logs (used by ai_bulk_action).
    
    Previously: Thread(target=_send_bulk_notifications, args=(log_ids,))
    """
    for log_id in log_ids:
        try:
            send_malpractice_notification.delay(log_id)
        except Exception as e:
            logger.error(f"Failed to queue notification for log {log_id}: {e}")
