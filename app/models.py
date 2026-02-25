# models.py
from django.db import models
from django.contrib.auth.models import User
from django.contrib import admin
from django.utils import timezone


# Lecture Hall Model
class LectureHall(models.Model):
    BUILDING_CHOICES = [
        ('MAIN', 'Main Block'),
        ('KE', 'Second Block'),
        ('PG', 'Third Block'),
        # Add more if needed
    ]
    building = models.CharField(max_length=50, choices=BUILDING_CHOICES)
    hall_name = models.CharField(max_length=50)  # e.g. "LH1", "LH2", etc.
    assigned_teacher = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self):
        return f"{self.building} - {self.hall_name}"


# Camera Session Model - tracks an active webcam session
class CameraSession(models.Model):
    STATUS_CHOICES = [
        ('requested', 'Requested by Admin'),
        ('active', 'Camera Active'),
        ('stopped', 'Camera Stopped'),
        ('denied', 'Denied by Teacher'),
    ]
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='camera_sessions')
    lecture_hall = models.ForeignKey(LectureHall, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Camera: {self.teacher.username} in {self.lecture_hall} [{self.status}]"


#Malpractice Logs Model
class MalpraticeDetection(models.Model):
    SOURCE_CHOICES = [
        ('live', 'Live Camera'),
        ('recorded', 'Recorded Video'),
    ]
    date = models.DateField(null=True)
    time = models.TimeField(null=True)
    malpractice = models.CharField(max_length=150)
    proof = models.CharField(max_length=150)
    is_malpractice = models.BooleanField(null=True)
    verified = models.BooleanField(default=False)
    lecture_hall = models.ForeignKey(LectureHall, on_delete=models.SET_NULL, null=True, blank=True)
    probability_score = models.FloatField(null=True, blank=True, help_text="AI-computed probability of malpractice (0-100)")
    source_type = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='live')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_logs')
    teacher_visible = models.BooleanField(default=False, help_text="Visible to teacher only after admin review")

    def __str__(self):
        return f"{self.malpractice} - {self.date} {self.time}"


# Review Session Model - tracks admin review completion for email notification
class ReviewSession(models.Model):
    REVIEW_TYPE_CHOICES = [
        ('live', 'Live Camera'),
        ('recorded', 'Recorded Video'),
    ]
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='review_sessions')
    lecture_hall = models.ForeignKey(LectureHall, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviewed_sessions')
    review_type = models.CharField(max_length=10, choices=REVIEW_TYPE_CHOICES, default='live')
    session_date = models.DateField(default=timezone.now)
    session_start_time = models.TimeField(null=True, blank=True)
    session_end_time = models.TimeField(null=True, blank=True)
    logs_reviewed = models.IntegerField(default=0)
    logs_flagged = models.IntegerField(default=0)
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Review: {self.lecture_hall} by {self.admin_user.username} on {self.session_date}"


# Teacher Profile Model
class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    profile_picture = models.ImageField(upload_to='profile_pics/')
    lecture_hall = models.OneToOneField(LectureHall, on_delete=models.SET_NULL, null=True, blank=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return self.user.username
    
@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'profile_picture', 'is_online']
    search_fields = ['user__username', 'phone'] 


