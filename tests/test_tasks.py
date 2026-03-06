"""
Tests for Celery tasks — notification sending with mocked external services.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.models import MalpraticeDetection, ReviewSession, TeacherProfile
from datetime import date, time


@pytest.mark.django_db
class TestSendMalpracticeNotification:
    """Test the send_malpractice_notification Celery task."""

    @patch('app.utils.send_sms_notification')
    @patch('app.tasks.send_mail')
    def test_sends_email_and_sms(self, mock_mail, mock_sms,
                                  malpractice_log, lecture_hall_with_teacher):
        from app.tasks import send_malpractice_notification

        # Mark as malpractice so notification makes sense
        malpractice_log.is_malpractice = True
        malpractice_log.verified = True
        malpractice_log.save()

        result = send_malpractice_notification(malpractice_log.id)

        assert mock_mail.called
        assert mock_sms.called

    @patch('app.utils.send_sms_notification')
    @patch('app.tasks.send_mail')
    def test_handles_missing_log(self, mock_mail, mock_sms):
        from app.tasks import send_malpractice_notification

        # Should not raise, just log error
        send_malpractice_notification(99999)
        assert not mock_mail.called

    @patch('app.utils.send_sms_notification')
    @patch('app.tasks.send_mail')
    def test_skips_sms_when_no_phone(self, mock_mail, mock_sms,
                                      lecture_hall_with_teacher, teacher_user):
        from app.tasks import send_malpractice_notification

        # Remove phone number
        profile = teacher_user.teacherprofile
        profile.phone = ''
        profile.save()

        log = MalpraticeDetection.objects.create(
            date=date(2026, 3, 7), time=time(10, 0),
            malpractice='test', proof='test.jpg',
            lecture_hall=lecture_hall_with_teacher,
            probability_score=80.0
        )

        send_malpractice_notification(log.id)
        assert mock_mail.called
        assert not mock_sms.called


@pytest.mark.django_db
class TestSendReviewSessionEmail:
    """Test the send_review_session_email Celery task."""

    @patch('app.utils.send_sms_notification')
    @patch('app.tasks.send_mail')
    def test_sends_review_email(self, mock_mail, mock_sms,
                                 admin_user, teacher_user,
                                 lecture_hall_with_teacher):
        from app.tasks import send_review_session_email

        session = ReviewSession.objects.create(
            admin_user=admin_user,
            lecture_hall=lecture_hall_with_teacher,
            teacher=teacher_user,
            logs_reviewed=10,
            logs_flagged=3,
            email_sent=False
        )

        send_review_session_email(session.id)

        assert mock_mail.called
        session.refresh_from_db()
        assert session.email_sent is True

    @patch('app.utils.send_sms_notification')
    @patch('app.tasks.send_mail')
    def test_handles_missing_session(self, mock_mail, mock_sms):
        from app.tasks import send_review_session_email
        send_review_session_email(99999)
        assert not mock_mail.called
