# consumers.py — WebSocket consumers for real-time camera management
import json
import base64
import asyncio
import logging
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from channels.generic.websocket import AsyncWebsocketConsumer, AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone

from .models import CameraSession, LectureHall, TeacherProfile, MalpraticeDetection

logger = logging.getLogger(__name__)

# Thread pool for ML processing (max 3 concurrent streams)
ml_executor = ThreadPoolExecutor(max_workers=3)

# Lock for thread-safe access to global state
_state_lock = threading.Lock()

# Global state for active streams
ACTIVE_STREAMS = {}  # {teacher_id: {'channel_name': ..., 'hall_id': ...}}

# Direct admin grid senders — bypass channel layer for high-frequency frame data
# {channel_name: send_func}  where send_func is the consumer's async send method
ADMIN_GRID_SENDERS = {}

# Admin presence tracking for heartbeat system
CONNECTED_ADMINS = set()  # Set of admin channel_names
_admin_disconnect_timer = None  # Timer to stop streams if no admin for 60s
ADMIN_TIMEOUT_SECONDS = 60


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    Handles real-time notifications between admin and teachers:
    - Camera start/stop requests (admin → teacher)
    - Camera permission responses (teacher → admin)
    - Teacher online/offline status
    - Malpractice log notifications
    """

    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous:
            await self.close()
            return

        # Everyone joins a global notification group
        self.notification_group = 'notifications_global'
        await self.channel_layer.group_add(self.notification_group, self.channel_name)

        # User-specific group for targeted messages
        self.user_group = f'user_{self.user.id}'
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        # Admin group
        if self.user.is_superuser:
            self.admin_group = 'admin_notifications'
            await self.channel_layer.group_add(self.admin_group, self.channel_name)
            # Track admin presence
            CONNECTED_ADMINS.add(self.channel_name)
            global _admin_disconnect_timer
            if _admin_disconnect_timer:
                _admin_disconnect_timer.cancel()
                _admin_disconnect_timer = None
                logger.info(f"Admin connected ({len(CONNECTED_ADMINS)} active), cancelled disconnect timer")

        await self.accept()

        # Mark teacher online
        if not self.user.is_superuser:
            await self.set_teacher_online(True)
            await self.broadcast_teacher_status()

        # Send initial state
        await self.send_initial_state()

    async def disconnect(self, close_code):
        if hasattr(self, 'user') and not self.user.is_anonymous:
            # Mark teacher offline
            if not self.user.is_superuser:
                await self.set_teacher_online(False)
                await self.broadcast_teacher_status()

            # Track admin presence
            if self.user.is_superuser:
                CONNECTED_ADMINS.discard(self.channel_name)
                if not CONNECTED_ADMINS and ACTIVE_STREAMS:
                    # Last admin disconnected while streams are active
                    # Start a timer — if no admin reconnects in 60s, warn teachers
                    logger.warning(f"Last admin disconnected. Starting {ADMIN_TIMEOUT_SECONDS}s warning timer.")
                    global _admin_disconnect_timer
                    loop = asyncio.get_running_loop()
                    _admin_disconnect_timer = loop.call_later(
                        ADMIN_TIMEOUT_SECONDS,
                        lambda: asyncio.ensure_future(self._admin_timeout_handler())
                    )

            await self.channel_layer.group_discard(self.notification_group, self.channel_name)
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
            if hasattr(self, 'admin_group'):
                await self.channel_layer.group_discard(self.admin_group, self.channel_name)

    async def _admin_timeout_handler(self):
        """Called when no admin has been connected for ADMIN_TIMEOUT_SECONDS."""
        if CONNECTED_ADMINS:
            return  # An admin reconnected in time

        logger.warning("No admin connected for 60s. Notifying active teacher streams.")
        # Notify all active teachers that admin is disconnected
        for teacher_id in list(ACTIVE_STREAMS.keys()):
            try:
                await self.channel_layer.group_send(
                    f'user_{teacher_id}',
                    {
                        'type': 'admin.disconnected',
                        'message': 'Admin has been disconnected for over 60 seconds. '
                                   'Your camera is still streaming but no one is monitoring.',
                    }
                )
            except Exception as e:
                logger.error(f"Error notifying teacher {teacher_id}: {e}")

    async def receive_json(self, content):
        """Handle incoming WebSocket messages"""
        msg_type = content.get('type')

        if msg_type == 'camera_request':
            # Admin requests a teacher to start camera
            await self.handle_camera_request(content)

        elif msg_type == 'camera_request_all':
            # Admin requests ALL teachers to start cameras
            await self.handle_camera_request_all(content)

        elif msg_type == 'camera_response':
            # Teacher accepts/denies camera request
            await self.handle_camera_response(content)

        elif msg_type == 'camera_stop':
            # Admin stops a teacher's camera
            await self.handle_camera_stop(content)

        elif msg_type == 'camera_stop_all':
            # Admin stops ALL cameras
            await self.handle_camera_stop_all()

        elif msg_type == 'camera_stop_by_teacher':
            # Teacher stops their own camera
            await self.handle_camera_stop_by_teacher(content)

        elif msg_type == 'camera_error':
            # Teacher's camera failed to start (hardware/permission error)
            await self.handle_camera_error(content)

        elif msg_type == 'get_teachers':
            # Admin requests current teacher list
            await self.send_teacher_list()

        elif msg_type == 'get_active_sessions':
            # Get all active camera sessions
            await self.send_active_sessions()

    # ===========================
    # CAMERA REQUEST HANDLERS
    # ===========================

    async def handle_camera_request(self, content):
        """Admin requests a single teacher to start their camera"""
        if not self.user.is_superuser:
            return

        teacher_id = content.get('teacher_id')
        if not teacher_id:
            return

        # Create camera session in DB
        session = await self.create_camera_session(teacher_id)
        if not session:
            await self.send_json({
                'type': 'error',
                'message': 'Teacher not found or no lecture hall assigned'
            })
            return

        # Send request to teacher
        await self.channel_layer.group_send(
            f'user_{teacher_id}',
            {
                'type': 'camera.request',
                'session_id': session['id'],
                'message': 'Admin has requested you to start your camera.',
            }
        )

        # Notify admin group of the pending request
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'session.update',
                'session': session,
            }
        )

    async def handle_camera_request_all(self, content):
        """Admin requests all online teachers to start cameras"""
        if not self.user.is_superuser:
            return

        teachers = await self.get_online_teachers()
        sessions_created = []

        for teacher in teachers:
            session = await self.create_camera_session(teacher['id'])
            if session:
                sessions_created.append(session)
                # Send request to each teacher
                await self.channel_layer.group_send(
                    f'user_{teacher["id"]}',
                    {
                        'type': 'camera.request',
                        'session_id': session['id'],
                        'message': 'Admin has requested you to start your camera.',
                    }
                )

        # Notify admin
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'bulk.session.update',
                'sessions': sessions_created,
                'count': len(sessions_created),
            }
        )

    async def handle_camera_response(self, content):
        """Teacher accepts or denies camera request"""
        if self.user.is_superuser:
            return

        session_id = content.get('session_id')
        accepted = content.get('accepted', False)

        session = await self.update_camera_session(session_id, accepted)
        if not session:
            return

        # Notify admin of the response
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'session.update',
                'session': session,
            }
        )

        # If accepted, tell teacher to start streaming
        if accepted:
            await self.send_json({
                'type': 'camera_approved',
                'session_id': session['id'],
                'message': 'Camera approved. Starting stream...',
            })

    async def handle_camera_stop(self, content):
        """Admin stops a single teacher's camera"""
        if not self.user.is_superuser:
            return

        teacher_id = content.get('teacher_id')
        session_id = content.get('session_id')

        session = await self.stop_camera_session(teacher_id=teacher_id, session_id=session_id)
        if not session:
            return

        # Tell teacher to stop camera
        await self.channel_layer.group_send(
            f'user_{session["teacher_id"]}',
            {
                'type': 'camera.stop',
                'session_id': session['id'],
                'message': 'Admin has stopped your camera.',
            }
        )

        # Notify admin group
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'session.update',
                'session': session,
            }
        )

    async def handle_camera_stop_all(self):
        """Admin stops all active cameras"""
        if not self.user.is_superuser:
            return

        sessions = await self.stop_all_camera_sessions()

        for session in sessions:
            await self.channel_layer.group_send(
                f'user_{session["teacher_id"]}',
                {
                    'type': 'camera.stop',
                    'session_id': session['id'],
                    'message': 'Admin has stopped all cameras.',
                }
            )

        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'bulk.session.update',
                'sessions': sessions,
                'count': len(sessions),
            }
        )

    async def handle_camera_stop_by_teacher(self, content):
        """Teacher stops their own camera"""
        session_id = content.get('session_id')
        if not session_id:
            return

        session = await self.stop_camera_session(session_id=session_id)
        if not session:
            return

        # Notify admin that teacher stopped their camera
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'session.update',
                'session': session,
            }
        )

        # Also send a specific notification so admin knows it was teacher-initiated
        teacher_name = session.get('teacher_name', 'Unknown')
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'camera.stopped.by.teacher',
                'teacher_id': session['teacher_id'],
                'teacher_name': teacher_name,
                'message': f'{teacher_name} stopped their camera.',
            }
        )

    async def handle_camera_error(self, content):
        """Teacher's camera failed to start — notify admin with error details"""
        session_id = content.get('session_id')
        reason = content.get('reason', 'unknown')
        message = content.get('message', 'Camera error')

        # Get teacher info
        teacher_name = f'{self.user.first_name} {self.user.last_name}'.strip() or self.user.username

        # Update session status to 'error' (allows retry)
        if session_id:
            session = await self.stop_camera_session(session_id=session_id)
            if session:
                await self.channel_layer.group_send(
                    'admin_notifications',
                    {
                        'type': 'session.update',
                        'session': session,
                    }
                )

        # Send specific camera error notification to admin
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'camera.error.notification',
                'teacher_id': self.user.id,
                'teacher_name': teacher_name,
                'reason': reason,
                'message': message,
            }
        )

    # ===========================
    # CHANNEL LAYER EVENT HANDLERS
    # (called by group_send)
    # ===========================

    async def camera_request(self, event):
        """Teacher receives camera start request from admin"""
        await self.send_json({
            'type': 'camera_request',
            'session_id': event['session_id'],
            'message': event['message'],
        })

    async def camera_stop(self, event):
        """Teacher receives camera stop command from admin"""
        await self.send_json({
            'type': 'camera_stop',
            'session_id': event['session_id'],
            'message': event['message'],
        })

    async def admin_disconnected(self, event):
        """Teacher is warned that admin has been disconnected"""
        await self.send_json({
            'type': 'admin_disconnected',
            'message': event['message'],
        })

    async def session_update(self, event):
        """Admin receives session status update"""
        await self.send_json({
            'type': 'session_update',
            'session': event['session'],
        })

    async def bulk_session_update(self, event):
        """Admin receives bulk session update"""
        await self.send_json({
            'type': 'bulk_session_update',
            'sessions': event['sessions'],
            'count': event['count'],
        })

    async def teacher_status(self, event):
        """Broadcast teacher online/offline status change"""
        await self.send_json({
            'type': 'teacher_status',
            'teachers': event['teachers'],
        })

    async def malpractice_alert(self, event):
        """Malpractice detection alert"""
        await self.send_json({
            'type': 'malpractice_alert',
            'detection': event['detection'],
        })

    async def review_notification(self, event):
        """Review completion notification (admin → teacher)"""
        await self.send_json({
            'type': 'review_notification',
            'review': event['review'],
        })

    async def camera_stopped_by_teacher(self, event):
        """Admin receives notification that teacher stopped their own camera"""
        await self.send_json({
            'type': 'camera_stopped_by_teacher',
            'teacher_id': event['teacher_id'],
            'teacher_name': event['teacher_name'],
            'message': event['message'],
        })

    async def camera_error_notification(self, event):
        """Admin receives camera error notification from teacher"""
        await self.send_json({
            'type': 'camera_error',
            'teacher_id': event['teacher_id'],
            'teacher_name': event['teacher_name'],
            'reason': event['reason'],
            'message': event['message'],
        })

    # ===========================
    # DATABASE OPERATIONS
    # ===========================

    @database_sync_to_async
    def set_teacher_online(self, online):
        try:
            profile = TeacherProfile.objects.get(user=self.user)
            profile.is_online = online
            profile.last_seen = timezone.now()
            profile.save(update_fields=['is_online', 'last_seen'])
        except TeacherProfile.DoesNotExist:
            pass

    @database_sync_to_async
    def get_online_teachers(self):
        profiles = TeacherProfile.objects.filter(
            is_online=True, user__is_superuser=False
        ).select_related('user', 'lecture_hall')
        return [
            {
                'id': p.user.id,
                'username': p.user.username,
                'first_name': p.user.first_name,
                'last_name': p.user.last_name,
                'lecture_hall': str(p.lecture_hall) if p.lecture_hall else 'Unassigned',
                'lecture_hall_id': p.lecture_hall.id if p.lecture_hall else None,
                'is_online': True,
            }
            for p in profiles
        ]

    @database_sync_to_async
    def get_all_teachers(self):
        profiles = TeacherProfile.objects.filter(user__is_superuser=False).select_related('user', 'lecture_hall')
        return [
            {
                'id': p.user.id,
                'username': p.user.username,
                'first_name': p.user.first_name,
                'last_name': p.user.last_name,
                'lecture_hall': str(p.lecture_hall) if p.lecture_hall else 'Unassigned',
                'lecture_hall_id': p.lecture_hall.id if p.lecture_hall else None,
                'is_online': p.is_online,
            }
            for p in profiles
        ]

    @database_sync_to_async
    def create_camera_session(self, teacher_id):
        try:
            teacher = User.objects.get(id=teacher_id)
            profile = TeacherProfile.objects.get(user=teacher)
            if not profile.lecture_hall:
                return None

            # Close any existing active sessions for this teacher
            CameraSession.objects.filter(
                teacher=teacher, status__in=['requested', 'active']
            ).update(status='stopped', stopped_at=timezone.now())

            session = CameraSession.objects.create(
                teacher=teacher,
                lecture_hall=profile.lecture_hall,
                status='requested',
            )
            return {
                'id': session.id,
                'teacher_id': teacher.id,
                'teacher_name': f'{teacher.first_name} {teacher.last_name}'.strip() or teacher.username,
                'lecture_hall': str(session.lecture_hall),
                'lecture_hall_id': session.lecture_hall.id,
                'status': session.status,
                'created_at': session.created_at.isoformat(),
            }
        except (User.DoesNotExist, TeacherProfile.DoesNotExist):
            return None

    @database_sync_to_async
    def update_camera_session(self, session_id, accepted):
        try:
            session = CameraSession.objects.get(id=session_id)
            if accepted:
                session.status = 'active'
                session.started_at = timezone.now()
            else:
                session.status = 'denied'
            session.save()
            return {
                'id': session.id,
                'teacher_id': session.teacher.id,
                'teacher_name': f'{session.teacher.first_name} {session.teacher.last_name}'.strip() or session.teacher.username,
                'lecture_hall': str(session.lecture_hall),
                'lecture_hall_id': session.lecture_hall.id,
                'status': session.status,
                'started_at': session.started_at.isoformat() if session.started_at else None,
            }
        except CameraSession.DoesNotExist:
            return None

    @database_sync_to_async
    def stop_camera_session(self, teacher_id=None, session_id=None):
        try:
            if session_id:
                session = CameraSession.objects.get(id=session_id)
            elif teacher_id:
                session = CameraSession.objects.filter(
                    teacher_id=teacher_id, status='active'
                ).latest('created_at')
            else:
                return None

            session.status = 'stopped'
            session.stopped_at = timezone.now()
            session.save()
            return {
                'id': session.id,
                'teacher_id': session.teacher.id,
                'teacher_name': f'{session.teacher.first_name} {session.teacher.last_name}'.strip() or session.teacher.username,
                'lecture_hall': str(session.lecture_hall),
                'status': 'stopped',
            }
        except CameraSession.DoesNotExist:
            return None

    @database_sync_to_async
    def stop_all_camera_sessions(self):
        active = CameraSession.objects.filter(status='active').select_related('teacher', 'lecture_hall')
        results = []
        for session in active:
            session.status = 'stopped'
            session.stopped_at = timezone.now()
            session.save()
            results.append({
                'id': session.id,
                'teacher_id': session.teacher.id,
                'teacher_name': f'{session.teacher.first_name} {session.teacher.last_name}'.strip() or session.teacher.username,
                'lecture_hall': str(session.lecture_hall),
                'status': 'stopped',
            })
        return results

    @database_sync_to_async
    def get_active_camera_sessions(self):
        sessions = CameraSession.objects.filter(
            status__in=['requested', 'active']
        ).select_related('teacher', 'lecture_hall')
        return [
            {
                'id': s.id,
                'teacher_id': s.teacher.id,
                'teacher_name': f'{s.teacher.first_name} {s.teacher.last_name}'.strip() or s.teacher.username,
                'lecture_hall': str(s.lecture_hall),
                'lecture_hall_id': s.lecture_hall.id,
                'status': s.status,
                'started_at': s.started_at.isoformat() if s.started_at else None,
            }
            for s in sessions
        ]

    # ===========================
    # HELPER METHODS
    # ===========================

    async def send_initial_state(self):
        """Send current state when client connects"""
        if self.user.is_superuser:
            teachers = await self.get_all_teachers()
            sessions = await self.get_active_camera_sessions()
            await self.send_json({
                'type': 'initial_state',
                'teachers': teachers,
                'active_sessions': sessions,
            })
        else:
            # Teacher gets their own session info
            sessions = await self.get_active_camera_sessions()
            my_sessions = [s for s in sessions if s['teacher_id'] == self.user.id]
            await self.send_json({
                'type': 'initial_state',
                'my_sessions': my_sessions,
            })

    async def send_teacher_list(self):
        teachers = await self.get_all_teachers()
        await self.send_json({
            'type': 'teacher_list',
            'teachers': teachers,
        })

    async def send_active_sessions(self):
        sessions = await self.get_active_camera_sessions()
        await self.send_json({
            'type': 'active_sessions',
            'sessions': sessions,
        })

    async def broadcast_teacher_status(self):
        teachers = await self.get_all_teachers()
        await self.channel_layer.group_send(
            'admin_notifications',
            {
                'type': 'teacher.status',
                'teachers': teachers,
            }
        )


class CameraStreamConsumer(AsyncWebsocketConsumer):
    """
    Handles teacher webcam streaming:
    - Teacher sends JPEG frames from browser webcam
    - Server processes frames with ML detection
    - Only ML-annotated frames sent back to teacher (teacher shows raw webcam locally)
    - Raw frames forwarded to admin grid
    - Video clips recorded with pre-roll + grace period for proof
    - Uses frame-dropping for ML, but ALL frames are buffered for video recording
    """

    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous or self.user.is_superuser:
            await self.close()
            return

        # Get teacher's active camera session
        self.session = await self.get_active_session()
        if not self.session:
            await self.close()
            return

        self.teacher_id = self.user.id
        self.hall_id = self.session['lecture_hall_id']
        self.stream_group = f'camera_stream_{self.teacher_id}'
        self.admin_grid_group = 'admin_camera_grid'

        # Register in active streams
        ACTIVE_STREAMS[self.teacher_id] = {
            'channel_name': self.channel_name,
            'hall_id': self.hall_id,
            'hall_name': self.session['lecture_hall'],
            'teacher_name': self.session['teacher_name'],
        }

        await self.channel_layer.group_add(self.stream_group, self.channel_name)
        await self.accept()

        # Initialize frame processor (eager init in background thread)
        self.frame_processor = None
        self.frame_count = 0
        self.admin_frame_count = 0
        self.detection_active = True

        # Frame-dropping: latest frame buffer + ML busy flag
        self._latest_frame = None
        self._ml_busy = False

        # Admin send backpressure flag — skip frames if previous send still in progress
        self._admin_send_busy = False

        # Pre-warm models in background (so first ML frame is fast)
        asyncio.ensure_future(self._init_processor_background())

        # Notify admin that stream started
        await self.channel_layer.group_send(
            'admin_camera_grid',
            {
                'type': 'stream.started',
                'teacher_id': self.teacher_id,
                'teacher_name': self.session['teacher_name'],
                'lecture_hall': self.session['lecture_hall'],
                'hall_id': self.hall_id,
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'teacher_id'):
            # Finalize any active recordings before disconnect
            if self.frame_processor:
                try:
                    loop = asyncio.get_running_loop()
                    completed = await loop.run_in_executor(
                        ml_executor, self.frame_processor.finalize_all_recordings
                    )
                    for detection in completed:
                        saved = await self.save_detection(detection)
                        if saved:
                            await self.channel_layer.group_send(
                                'admin_notifications',
                                {
                                    'type': 'malpractice.alert',
                                    'detection': saved,
                                }
                            )
                except Exception as e:
                    logger.error(f"Error finalizing recordings on disconnect: {e}")

            ACTIVE_STREAMS.pop(self.teacher_id, None)

            # Notify admin that stream ended
            await self.channel_layer.group_send(
                'admin_camera_grid',
                {
                    'type': 'stream.ended',
                    'teacher_id': self.teacher_id,
                }
            )

            await self.channel_layer.group_discard(self.stream_group, self.channel_name)

    async def receive(self, bytes_data=None, text_data=None):
        """Receive frame data from teacher's webcam"""
        if bytes_data:
            await self.process_frame(bytes_data)
        elif text_data:
            data = json.loads(text_data)
            if data.get('type') == 'frame':
                frame_bytes = base64.b64decode(data['data'])
                await self.process_frame(frame_bytes)
            elif data.get('type') == 'stop':
                self.detection_active = False

    async def process_frame(self, frame_bytes):
        """Process a webcam frame — buffer ALL frames, ML with frame-dropping.
        Admin frames sent as BINARY WebSocket (no base64/JSON overhead)."""
        self.frame_count += 1

        # Always store the latest frame for ML (overwrites previous)
        self._latest_frame = frame_bytes

        # Buffer EVERY frame for video recording (quick operation)
        if self.frame_processor:
            loop = asyncio.get_running_loop()
            asyncio.ensure_future(
                loop.run_in_executor(ml_executor, self.frame_processor.buffer_frame, frame_bytes)
            )

        # Forward RAW frame to admin as BINARY — every 2nd frame (~10 FPS at 20 FPS input)
        # Binary = no base64 encoding (50% less CPU), no JSON (33% less bandwidth)
        self.admin_frame_count += 1
        if self.admin_frame_count % 2 == 0 and ADMIN_GRID_SENDERS:
            asyncio.ensure_future(self._forward_to_admin_binary(frame_bytes))

        # ML processing: only if not already busy (frame-dropping)
        if self.detection_active and not self._ml_busy and self.frame_processor:
            self._ml_busy = True
            asyncio.ensure_future(self._run_ml_processing())

    async def _forward_to_admin_binary(self, frame_bytes):
        """Send raw frame as binary WebSocket to all admin consumers.
        Protocol: [4 bytes teacher_id big-endian] + [raw JPEG bytes]
        No base64, no JSON — maximum throughput."""
        try:
            header = self.teacher_id.to_bytes(4, 'big')
            binary_data = header + frame_bytes
            dead_channels = []
            for ch_name, send_func in list(ADMIN_GRID_SENDERS.items()):
                try:
                    await send_func(bytes_data=binary_data)
                except Exception:
                    dead_channels.append(ch_name)
            for ch in dead_channels:
                ADMIN_GRID_SENDERS.pop(ch, None)
        except Exception as e:
            logger.error(f"Admin binary frame forward error: {e}")

    async def _run_ml_processing(self):
        """Run ML on the latest frame, handle completed detections with video proof"""
        try:
            if not self.frame_processor:
                self._ml_busy = False
                return

            frame_bytes = self._latest_frame
            if frame_bytes is None:
                self._ml_busy = False
                return

            # Process in thread pool (ML inference + recording management)
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                ml_executor,
                self.frame_processor.process_frame,
                frame_bytes
            )

            if result:
                # Send annotated frame back to teacher (overlay on their local webcam view)
                await self.send(bytes_data=result['annotated_frame'])

                # Handle completed detections (video clip recordings that finished)
                if result.get('detections'):
                    for detection in result['detections']:
                        saved = await self.save_detection(detection)
                        if saved:
                            # Notify teacher with detection info
                            await self.send(text_data=json.dumps({
                                'type': 'detection',
                                'action': detection.get('action', ''),
                                'probability': detection.get('probability', 0),
                                'proof': detection.get('proof', ''),
                            }))
                            # Notify admin in real-time
                            await self.channel_layer.group_send(
                                'admin_notifications',
                                {
                                    'type': 'malpractice.alert',
                                    'detection': saved,
                                }
                            )
        except Exception as e:
            logger.error(f"ML processing error: {e}")
        finally:
            self._ml_busy = False

    async def _init_processor_background(self):
        """Initialize ML frame processor in background thread.
        Pre-warms models on first use to eliminate cold-start delay."""
        try:
            loop = asyncio.get_running_loop()
            self.frame_processor = await loop.run_in_executor(
                ml_executor, self._create_frame_processor
            )
            if self.frame_processor:
                logger.info(f"Frame processor ready for teacher {self.teacher_id}")
        except Exception as e:
            logger.error(f"Failed to init frame processor: {e}")

    def _create_frame_processor(self):
        """Create FrameProcessor instance (runs in thread pool).
        Pre-warms ML models on first invocation."""
        try:
            import sys
            import os
            from django.conf import settings
            ml_path = os.path.join(settings.BASE_DIR, 'ML')
            if ml_path not in sys.path:
                sys.path.insert(0, ml_path)

            from frame_processor import FrameProcessor, prewarm_models
            # Pre-warm models (only runs once, subsequent calls are no-ops)
            prewarm_models()
            hall_name = ACTIVE_STREAMS.get(self.teacher_id, {}).get('hall_name', 'Unknown')
            return FrameProcessor(
                lecture_hall=hall_name,
                teacher_id=self.teacher_id
            )
        except Exception as e:
            logger.error(f"Failed to create frame processor: {e}")
            return None

    @database_sync_to_async
    def get_active_session(self):
        try:
            session = CameraSession.objects.filter(
                teacher=self.user, status='active'
            ).select_related('lecture_hall').latest('created_at')
            return {
                'id': session.id,
                'lecture_hall': str(session.lecture_hall),
                'lecture_hall_id': session.lecture_hall.id,
                'teacher_name': f'{self.user.first_name} {self.user.last_name}'.strip() or self.user.username,
            }
        except CameraSession.DoesNotExist:
            return None

    @database_sync_to_async
    def save_detection(self, detection):
        """Save malpractice detection to database with video proof"""
        try:
            now = timezone.localtime(timezone.now())  # Convert to local timezone (Asia/Kolkata)
            session_info = ACTIVE_STREAMS.get(self.teacher_id, {})
            hall_id = session_info.get('hall_id')
            hall = LectureHall.objects.get(id=hall_id) if hall_id else None

            log = MalpraticeDetection.objects.create(
                date=now.date(),
                time=now.time(),
                malpractice=detection.get('action', 'Unknown'),
                proof=detection.get('proof', ''),
                is_malpractice=None,
                lecture_hall=hall,
                probability_score=detection.get('probability', 0),
                source_type='live',
                uploaded_by=self.user,
                teacher_visible=False,
            )
            return {
                'id': log.id,
                'date': str(log.date),
                'time': str(log.time),
                'malpractice': log.malpractice,
                'proof': log.proof,
                'lecture_hall': str(hall) if hall else 'Unknown',
                'probability_score': log.probability_score,
                'source_type': 'live',
                'teacher_name': session_info.get('teacher_name', ''),
            }
        except Exception as e:
            logger.error(f"Failed to save detection: {e}")
            return None


class AdminGridConsumer(AsyncWebsocketConsumer):
    """
    Admin receives raw camera frames from all active teacher streams.
    Provides grid view of all active cameras.
    """

    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous or not self.user.is_superuser:
            await self.close()
            return

        self.admin_grid_group = 'admin_camera_grid'
        await self.channel_layer.group_add(self.admin_grid_group, self.channel_name)
        await self.accept()

        # Register for DIRECT frame sends (bypasses channel layer for speed)
        ADMIN_GRID_SENDERS[self.channel_name] = self.send

        # Send list of currently active streams
        await self.send(text_data=json.dumps({
            'type': 'active_streams',
            'streams': [
                {
                    'teacher_id': tid,
                    'teacher_name': info.get('teacher_name', ''),
                    'lecture_hall': info.get('hall_name', ''),
                    'hall_id': info.get('hall_id'),
                }
                for tid, info in ACTIVE_STREAMS.items()
            ]
        }))

    async def disconnect(self, close_code):
        # Unregister from direct frame sends
        ADMIN_GRID_SENDERS.pop(self.channel_name, None)
        if hasattr(self, 'admin_grid_group'):
            await self.channel_layer.group_discard(self.admin_grid_group, self.channel_name)

    async def receive(self, text_data=None, **kwargs):
        """Admin can send commands via grid view"""
        if not text_data:
            return
        data = json.loads(text_data)
        # Future: admin can click on a specific camera from grid

    # ===========================
    # EVENT HANDLERS
    # ===========================

    async def camera_frame(self, event):
        """Receive frame from a teacher's camera and forward to admin"""
        await self.send(text_data=json.dumps({
            'type': 'camera_frame',
            'teacher_id': event['teacher_id'],
            'teacher_name': event['teacher_name'],
            'lecture_hall': event['lecture_hall'],
            'frame': event['frame'],
        }))

    async def stream_started(self, event):
        """A teacher started streaming"""
        await self.send(text_data=json.dumps({
            'type': 'stream_started',
            'teacher_id': event['teacher_id'],
            'teacher_name': event['teacher_name'],
            'lecture_hall': event['lecture_hall'],
            'hall_id': event['hall_id'],
        }))

    async def stream_ended(self, event):
        """A teacher stopped streaming"""
        await self.send(text_data=json.dumps({
            'type': 'stream_ended',
            'teacher_id': event['teacher_id'],
        }))
