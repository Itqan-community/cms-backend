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

    def test_beat_scheduler_is_database(self):
        """Beat scheduler should use django-celery-beat DatabaseScheduler."""
        self.assertEqual(
            settings.CELERY_BEAT_SCHEDULER,
            "django_celery_beat.schedulers:DatabaseScheduler",
        )

    def test_task_always_eager_in_dev(self):
        """Development settings should keep tasks eager (synchronous)."""
        self.assertTrue(settings.CELERY_TASK_ALWAYS_EAGER)

    def test_existing_tasks_discoverable(self):
        """Autodiscover should find tasks in content and publishers apps."""
        from celery import current_app

        current_app.loader.import_default_modules()
        registered = current_app.tasks.keys()
        self.assertTrue(
            any("content" in t for t in registered),
            f"No content tasks found in: {list(registered)}",
        )
        self.assertTrue(
            any("publishers" in t for t in registered),
            f"No publisher tasks found in: {list(registered)}",
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
