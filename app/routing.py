# routing.py - WebSocket URL routing for Django Channels
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Notification channel - real-time alerts, camera requests, status updates
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    # Camera stream - teacher sends webcam frames, receives processed frames
    re_path(r'ws/camera/stream/$', consumers.CameraStreamConsumer.as_asgi()),
    # Admin camera grid - receives raw frames from all active teacher cameras
    re_path(r'ws/camera/admin-grid/$', consumers.AdminGridConsumer.as_asgi()),
]
