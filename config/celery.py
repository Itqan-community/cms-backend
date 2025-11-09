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

# Optional: Define periodic tasks

app.conf.beat_schedule = {
    # Search-related tasks removed with search app cleanup
    # Check for expiring access requests daily at 9 AM
    "check-expiring-access-requests": {
        # 'task': 'apps.licensing.tasks.check_expiring_access_requests',
        "schedule": crontab(hour=9, minute=0),
    },
    # Mark expired access requests every hour
    "mark-expired-access-requests": {
        # 'task': 'apps.licensing.tasks.mark_expired_access_requests',
        "schedule": crontab(minute=0),  # Every hour
    },
    # Send admin summary report daily at 8 AM
    "send-admin-summary-report": {
        # 'task': 'apps.licensing.tasks.send_admin_summary_report',
        "schedule": crontab(hour=8, minute=0),
    },
    # Resend failed notifications every 30 minutes
    "resend-failed-notifications": {
        # 'task': 'apps.licensing.tasks.resend_failed_notifications',
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
    # Clean up old access requests monthly
    "cleanup-old-access-requests": {
        # 'task': 'apps.licensing.tasks.cleanup_old_access_requests',
        "schedule": crontab(hour=4, minute=0, day_of_month=1),  # First day of month at 4 AM
    },
}

app.conf.timezone = "UTC"


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery connectivity"""
    print(f"Request: {self.request!r}")
