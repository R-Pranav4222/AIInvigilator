"""
Tests for Django models — FK constraints, validations, cascades, db_index.
"""

import pytest
from django.db import IntegrityError
from django.contrib.auth.models import User
from app.models import (
    LectureHall, TeacherProfile, CameraSession,
    MalpraticeDetection, ReviewSession
)
from datetime import date, time


@pytest.mark.django_db
class TestLectureHall:

    def test_create_lecture_hall(self):
        hall = LectureHall.objects.create(building='MAIN', hall_name='LH1')
        assert str(hall) == 'MAIN - LH1'
        assert hall.assigned_teacher is None

    def test_building_choices(self):
        """Valid building codes are accepted."""
        for code, _ in LectureHall.BUILDING_CHOICES:
            hall = LectureHall.objects.create(building=code, hall_name=f'Test-{code}')
            assert hall.building == code

    def test_one_to_one_teacher_constraint(self, teacher_user, lecture_hall):
        """A teacher can only be assigned to one hall (OneToOne)."""
        lecture_hall.assigned_teacher = teacher_user
        lecture_hall.save()

        hall2 = LectureHall.objects.create(building='KE', hall_name='LH2')
        hall2.assigned_teacher = teacher_user
        with pytest.raises(IntegrityError):
            hall2.save()

    def test_set_null_on_teacher_delete(self, lecture_hall_with_teacher):
        """Deleting a teacher sets lecture_hall.assigned_teacher to NULL."""
        teacher = lecture_hall_with_teacher.assigned_teacher
        teacher.delete()
        lecture_hall_with_teacher.refresh_from_db()
        assert lecture_hall_with_teacher.assigned_teacher is None


@pytest.mark.django_db
class TestTeacherProfile:

    def test_create_profile(self, teacher_user, lecture_hall):
        profile = TeacherProfile.objects.create(
            user=teacher_user, phone='9876543210',
            lecture_hall=lecture_hall, is_online=False
        )
        assert str(profile) == teacher_user.username
        assert profile.is_online is False

    def test_cascade_on_user_delete(self, teacher_user):
        TeacherProfile.objects.create(user=teacher_user, phone='1234567890')
        teacher_user.delete()
        assert TeacherProfile.objects.count() == 0

    def test_is_online_db_index(self):
        """is_online field should have db_index=True."""
        field = TeacherProfile._meta.get_field('is_online')
        assert field.db_index is True


@pytest.mark.django_db
class TestCameraSession:

    def test_create_session(self, camera_session):
        assert camera_session.status == 'requested'
        assert camera_session.started_at is None

    def test_ordering_newest_first(self, teacher_user, lecture_hall_with_teacher):
        import time as _time
        s1 = CameraSession.objects.create(
            teacher=teacher_user, lecture_hall=lecture_hall_with_teacher, status='requested'
        )
        _time.sleep(0.05)  # ensure different created_at timestamp
        s2 = CameraSession.objects.create(
            teacher=teacher_user, lecture_hall=lecture_hall_with_teacher, status='active'
        )
        sessions = list(CameraSession.objects.all())
        assert sessions[0].created_at >= sessions[-1].created_at  # newest first

    def test_cascade_on_teacher_delete(self, camera_session, teacher_user):
        """Deleting user cascades to camera sessions."""
        teacher_user.delete()
        assert CameraSession.objects.count() == 0

    def test_status_db_index(self):
        field = CameraSession._meta.get_field('status')
        assert field.db_index is True


@pytest.mark.django_db
class TestMalpraticeDetection:

    def test_create_log(self, malpractice_log):
        assert malpractice_log.verified is False
        assert malpractice_log.is_malpractice is None
        assert malpractice_log.probability_score == 75.0
        assert malpractice_log.source_type == 'live'

    def test_tri_state_is_malpractice(self, lecture_hall):
        """is_malpractice supports True/False/None (tri-state)."""
        for state in [True, False, None]:
            log = MalpraticeDetection.objects.create(
                malpractice='test', proof='test.jpg',
                is_malpractice=state, lecture_hall=lecture_hall
            )
            assert log.is_malpractice is state

    def test_set_null_on_hall_delete(self, malpractice_log, lecture_hall_with_teacher):
        """Deleting hall sets FK to NULL, preserving evidence."""
        lecture_hall_with_teacher.delete()
        malpractice_log.refresh_from_db()
        assert malpractice_log.lecture_hall is None

    def test_db_indexes(self):
        """Key fields should have db_index=True for query performance."""
        indexed_fields = ['date', 'verified', 'probability_score', 'source_type', 'teacher_visible']
        for field_name in indexed_fields:
            field = MalpraticeDetection._meta.get_field(field_name)
            assert field.db_index is True, f"{field_name} should have db_index=True"


@pytest.mark.django_db
class TestReviewSession:

    def test_create_review(self, admin_user, teacher_user, lecture_hall_with_teacher):
        session = ReviewSession.objects.create(
            admin_user=admin_user,
            lecture_hall=lecture_hall_with_teacher,
            teacher=teacher_user,
            review_type='live',
            logs_reviewed=10,
            logs_flagged=3,
            email_sent=False
        )
        assert session.logs_reviewed == 10
        assert session.email_sent is False
        assert 'Review:' in str(session)
