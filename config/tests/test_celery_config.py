"""Tests for Celery configuration."""

from django.conf import settings
from django.test import SimpleTestCase


class TestCeleryConfig(SimpleTestCase):
    """Verify Celery is properly configured across environments."""

    def test_django_celery_beat_in_installed_apps(self):
        """django_celery_beat must be in INSTALLED_APPS for DB-backed scheduling."""
        self.assertIn("django_celery_beat", settings.INSTALLED_APPS)

    def test_celery_app_exists(self):
        """Celery app must be importable from config."""
        from config.celery import app

        self.assertEqual(app.main, "itqan_cms")

    def test_task_always_eager_in_dev(self):
        """Development settings should keep tasks eager (synchronous)."""
        self.assertTrue(settings.CELERY_TASK_ALWAYS_EAGER)

    def test_existing_tasks_discoverable(self):
        """Autodiscover should find tasks in content app."""
        from celery import current_app

        current_app.loader.import_default_modules()
        registered = current_app.tasks.keys()
        self.assertTrue(
            any("content" in t for t in registered),
            f"No content tasks found in: {list(registered)}",
        )

    def test_beat_schedule_has_active_tasks(self):
        """Beat schedule should only contain entries with actual task paths."""
        from config.celery import app

        for name, entry in app.conf.beat_schedule.items():
            self.assertIn(
                "task",
                entry,
                f"Beat schedule entry '{name}' is missing 'task' key",
            )
            self.assertIsNotNone(
                entry["task"],
                f"Beat schedule entry '{name}' has None task",
            )

    def test_audit_history_scheduled_tasks(self):
        """Audit history prune and deduplicate tasks must be scheduled for Friday dawn in Asia/Riyadh (01:00 UTC)."""
        from config.celery import app

        schedule = app.conf.beat_schedule
        self.assertIn("prune-audit-history", schedule)
        self.assertIn("clean-duplicate-history", schedule)

        prune_entry = schedule["prune-audit-history"]
        self.assertEqual(prune_entry["task"], "apps.core.tasks.prune_audit_history_task")
        # crontab(minute=0, hour=4, day_of_week=5) -> Friday dawn 04:00 Asia/Riyadh (01:00 UTC)
        self.assertEqual(prune_entry["schedule"].minute, {0})
        self.assertEqual(prune_entry["schedule"].hour, {4})
        self.assertEqual(prune_entry["schedule"].day_of_week, {5})

        clean_entry = schedule["clean-duplicate-history"]
        self.assertEqual(clean_entry["task"], "apps.core.tasks.clean_duplicate_history_task")
        # crontab(minute=30, hour=4, day_of_week=5) -> Friday dawn 04:30 Asia/Riyadh (01:30 UTC)
        self.assertEqual(clean_entry["schedule"].minute, {30})
        self.assertEqual(clean_entry["schedule"].hour, {4})
        self.assertEqual(clean_entry["schedule"].day_of_week, {5})
