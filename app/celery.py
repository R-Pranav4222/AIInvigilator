"""
Celery configuration for AIInvigilator.

Usage:
    # Start worker (in a separate terminal):
    celery -A app worker --pool=solo --loglevel=info

    # On Windows, --pool=solo is required (prefork doesn't work on Windows).
    # On Linux/Docker, use: celery -A app worker --loglevel=info
"""

import os
from celery import Celery

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

app = Celery('app')

# Load config from Django settings (all keys with CELERY_ prefix)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps (looks for tasks.py in each app)
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Test task to verify Celery is working. Run with:
    >>> from app.celery import debug_task
    >>> debug_task.delay()
    """
    print(f'Request: {self.request!r}')
