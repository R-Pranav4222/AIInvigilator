"""
Shared pytest fixtures for AIInvigilator test suite.
"""

import pytest
from django.contrib.auth.models import User
from app.models import LectureHall, TeacherProfile, CameraSession, MalpraticeDetection, ReviewSession
from datetime import date, time


@pytest.fixture
def admin_user(db):
    """Create and return a superuser (admin)."""
    user = User.objects.create_superuser(
        username='admin_test',
        password='TestPass123!',
        email='admin@test.com',
        first_name='Admin',
        last_name='User'
    )
    return user


@pytest.fixture
def teacher_user(db):
    """Create and return a regular user (teacher)."""
    user = User.objects.create_user(
        username='teacher_test',
        password='TestPass123!',
        email='teacher@test.com',
        first_name='Test',
        last_name='Teacher'
    )
    return user


@pytest.fixture
def lecture_hall(db):
    """Create and return a lecture hall."""
    return LectureHall.objects.create(
        building='MAIN',
        hall_name='LH1'
    )


@pytest.fixture
def lecture_hall_with_teacher(db, teacher_user, lecture_hall):
    """Create a lecture hall with an assigned teacher + profile."""
    lecture_hall.assigned_teacher = teacher_user
    lecture_hall.save()

    TeacherProfile.objects.create(
        user=teacher_user,
        phone='9876543210',
        lecture_hall=lecture_hall,
        is_online=False
    )
    return lecture_hall


@pytest.fixture
def malpractice_log(db, lecture_hall_with_teacher):
    """Create a sample malpractice detection log."""
    return MalpraticeDetection.objects.create(
        date=date(2026, 3, 7),
        time=time(10, 30),
        malpractice='phone_usage',
        proof='uploaded_videos/test_frame.jpg',
        is_malpractice=None,
        verified=False,
        lecture_hall=lecture_hall_with_teacher,
        probability_score=75.0,
        source_type='live',
        teacher_visible=False
    )


@pytest.fixture
def camera_session(db, teacher_user, lecture_hall_with_teacher):
    """Create a sample camera session."""
    return CameraSession.objects.create(
        teacher=teacher_user,
        lecture_hall=lecture_hall_with_teacher,
        status='requested'
    )


@pytest.fixture
def admin_client(client, admin_user):
    """Return a logged-in admin client."""
    client.login(username='admin_test', password='TestPass123!')
    return client


@pytest.fixture
def teacher_client(client, teacher_user):
    """Return a logged-in teacher client."""
    client.login(username='teacher_test', password='TestPass123!')
    return client
