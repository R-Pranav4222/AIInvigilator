from django.contrib import admin
from .models import LectureHall, TeacherProfile, MalpraticeDetection, CameraSession, ReviewSession

admin.site.register(LectureHall)
admin.site.register(MalpraticeDetection)
admin.site.register(CameraSession)
admin.site.register(ReviewSession)



