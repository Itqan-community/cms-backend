"""
Celery configuration for Itqan CMS
"""

from datetime import timedelta
import os

from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Create Celery app
app = Celery("itqan_cms")

# Configure Celery using Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all Django apps
app.autodiscover_tasks()

from django.conf import settings  # noqa: E402

# Periodic tasks (active entries only - commented-out licensing tasks removed)
app.conf.beat_schedule = {
    "cleanup-stuck-multipart-uploads": {
        "task": "apps.content.tasks.cleanup_stuck_multipart_uploads_task",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    "expire-publisher-member-invitations": {
        "task": "apps.publishers.tasks.expire_publisher_member_invitations",
        "schedule": crontab(minute=0, hour=0),
    },
    "flush-tracking-buffer": {
        "task": "apps.usage_tracking.tasks.flush_tracking_buffer_task",
        "schedule": timedelta(seconds=30),
    },
    "sync-audio-usage": {
        "task": "apps.usage_tracking.tasks.sync_audio_usage_task",
        "schedule": crontab(minute=5, hour=f"*/{settings.AUDIO_USAGE_SYNC_WINDOW_HOURS}"),
        "kwargs": {"window_hours": settings.AUDIO_USAGE_SYNC_WINDOW_HOURS},
    },
}


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery connectivity"""
    print(f"Request: {self.request!r}")
