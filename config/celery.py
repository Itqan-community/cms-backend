"""
Celery configuration for Itqan CMS
"""

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

# Periodic tasks (active entries only - commented-out licensing tasks removed)
app.conf.beat_schedule = {
    "cleanup-stuck-multipart-uploads": {
        "task": "apps.content.tasks.cleanup_stuck_multipart_uploads_task",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    "compute-publisher-stats": {
        "task": "apps.publishers.tasks.compute_publisher_stats_task",
        "schedule": crontab(minute="*/30"),
    },
}


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery connectivity"""
    print(f"Request: {self.request!r}")
