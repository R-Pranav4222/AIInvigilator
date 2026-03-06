"""
Tests for Django views — authentication, permissions, CRUD operations.
"""

import pytest
import json
from django.contrib.auth.models import User
from app.models import (
    LectureHall, MalpraticeDetection, ReviewSession, TeacherProfile
)
from datetime import date, time


@pytest.mark.django_db
class TestAuthViews:
    """Test login, logout, and access control."""

    def test_login_page_loads(self, client):
        response = client.get('/login/')
        assert response.status_code == 200

    def test_index_page_loads(self, client):
        response = client.get('/')
        assert response.status_code == 200

    def test_login_valid_credentials(self, client, admin_user):
        response = client.post('/login/addlogin', {
            'username': 'admin_test',
            'password': 'TestPass123!'
        })
        assert response.status_code == 302  # redirect on success

    def test_login_invalid_credentials(self, client):
        response = client.post('/login/addlogin', {
            'username': 'nonexistent',
            'password': 'wrong'
        })
        assert response.status_code == 200  # stays on login page

    def test_logout_redirects(self, admin_client):
        response = admin_client.get('/logout/')
        assert response.status_code == 302

    def test_protected_page_requires_login(self, client):
        """Unauthenticated user is redirected to login."""
        response = client.get('/malpractice_log/')
        assert response.status_code == 302
        assert '/login' in response.url


@pytest.mark.django_db
class TestMalpracticeLogView:
    """Test the malpractice log listing and filtering."""

    def test_admin_can_access(self, admin_client, malpractice_log):
        response = admin_client.get('/malpractice_log/')
        assert response.status_code == 200

    def test_teacher_can_access(self, teacher_client, malpractice_log):
        response = teacher_client.get('/malpractice_log/')
        assert response.status_code == 200

    def test_filter_by_source_type(self, admin_client, malpractice_log):
        response = admin_client.get('/malpractice_log/?source=live')
        assert response.status_code == 200

    def test_filter_by_probability(self, admin_client, malpractice_log):
        response = admin_client.get('/malpractice_log/?probability=above_50')
        assert response.status_code == 200


@pytest.mark.django_db
class TestReviewMalpractice:
    """Test the review_malpractice endpoint (admin-only POST)."""

    def test_requires_admin(self, teacher_client, malpractice_log):
        """Non-admin users should be rejected."""
        response = teacher_client.post(
            '/review_malpractice/',
            data=json.dumps({
                'proof': malpractice_log.proof,
                'decision': 'yes'
            }),
            content_type='application/json'
        )
        assert response.status_code == 302  # redirect to login (not admin)

    def test_approve_malpractice(self, admin_client, malpractice_log, settings):
        """Admin approves a malpractice log."""
        settings.CELERY_TASK_ALWAYS_EAGER = True
        response = admin_client.post(
            '/review_malpractice/',
            data=json.dumps({
                'proof': malpractice_log.proof,
                'decision': 'yes'
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

        malpractice_log.refresh_from_db()
        assert malpractice_log.verified is True
        assert malpractice_log.is_malpractice is True
        assert malpractice_log.teacher_visible is True

    def test_dismiss_malpractice(self, admin_client, malpractice_log, settings):
        """Admin dismisses a malpractice log."""
        settings.CELERY_TASK_ALWAYS_EAGER = True
        response = admin_client.post(
            '/review_malpractice/',
            data=json.dumps({
                'proof': malpractice_log.proof,
                'decision': 'no'
            }),
            content_type='application/json'
        )
        assert response.status_code == 200

        malpractice_log.refresh_from_db()
        assert malpractice_log.verified is True
        assert malpractice_log.is_malpractice is False

    def test_invalid_json(self, admin_client):
        response = admin_client.post(
            '/review_malpractice/',
            data='not json',
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False


@pytest.mark.django_db
class TestAiBulkAction:
    """Test the ai_bulk_action endpoint."""

    def test_approve_high_probability(self, admin_client, lecture_hall_with_teacher, settings):
        """Approve all logs with probability >= 50%."""
        settings.CELERY_TASK_ALWAYS_EAGER = True
        hall = lecture_hall_with_teacher
        # Create logs with different probabilities
        MalpraticeDetection.objects.create(
            malpractice='phone', proof='p1.jpg',
            probability_score=80.0, lecture_hall=hall, source_type='live'
        )
        MalpraticeDetection.objects.create(
            malpractice='leaning', proof='p2.jpg',
            probability_score=30.0, lecture_hall=hall, source_type='live'
        )

        response = admin_client.post(
            '/ai_bulk_action/',
            data=json.dumps({'action': 'approve_high'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['count'] == 1  # only the 80% log

    def test_dismiss_low_probability(self, admin_client, lecture_hall_with_teacher, settings):
        """Dismiss all logs with probability < 50%."""
        settings.CELERY_TASK_ALWAYS_EAGER = True
        hall = lecture_hall_with_teacher
        MalpraticeDetection.objects.create(
            malpractice='leaning', proof='d1.jpg',
            probability_score=20.0, lecture_hall=hall, source_type='live'
        )

        response = admin_client.post(
            '/ai_bulk_action/',
            data=json.dumps({'action': 'dismiss_low'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'


@pytest.mark.django_db
class TestDeleteMalpractice:
    """Test log deletion endpoints."""

    def test_delete_single_log(self, admin_client, malpractice_log):
        response = admin_client.post(f'/delete_malpractice/{malpractice_log.id}/')
        assert response.status_code == 200
        assert response.json()['success'] is True
        assert MalpraticeDetection.objects.filter(id=malpractice_log.id).count() == 0

    def test_delete_by_teacher_own_hall(self, teacher_client, malpractice_log):
        """Teacher assigned to the hall can delete logs."""
        response = teacher_client.post(f'/delete_malpractice/{malpractice_log.id}/')
        assert response.status_code == 200
        assert response.json()['success'] is True


@pytest.mark.django_db
class TestManageLectureHalls:
    """Test lecture hall management view."""

    def test_admin_can_access(self, admin_client, lecture_hall):
        response = admin_client.get('/manage-lecture-halls/')
        assert response.status_code == 200

    def test_teacher_cannot_access(self, teacher_client):
        response = teacher_client.get('/manage-lecture-halls/')
        assert response.status_code == 302  # redirected


@pytest.mark.django_db
class TestViewTeachers:
    """Test teacher listing view."""

    def test_admin_can_view_teachers(self, admin_client, teacher_user):
        TeacherProfile.objects.create(user=teacher_user, phone='1234567890')
        response = admin_client.get('/view_teachers/')
        assert response.status_code == 200

    def test_search_teachers(self, admin_client, teacher_user):
        TeacherProfile.objects.create(user=teacher_user, phone='1234567890')
        response = admin_client.get('/view_teachers/?q=teacher_test')
        assert response.status_code == 200


@pytest.mark.django_db
class TestProfileViews:
    """Test profile viewing and editing."""

    def test_view_profile(self, teacher_client, teacher_user):
        TeacherProfile.objects.create(user=teacher_user, phone='1234567890')
        response = teacher_client.get('/profile/')
        assert response.status_code == 200

    def test_edit_profile_page(self, teacher_client, teacher_user):
        TeacherProfile.objects.create(user=teacher_user, phone='1234567890')
        response = teacher_client.get('/profile/edit/')
        assert response.status_code == 200
