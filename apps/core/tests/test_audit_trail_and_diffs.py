"""Tests for Readable Audit Trail, Diffs, and Retention Pruning (ITQ-36 / Issue #434)."""

from datetime import timedelta
from io import StringIO

from django.apps import apps
from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.content.models import ContentIssueReport
from apps.core.admin import AuditedModelAdmin
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import APIKey, User


class AuditTrailAndDiffsTest(BaseTestCase):
    def test_all_tracked_models_are_registered_with_audited_model_admin(self):
        """Verifies that all models tracked by simple-history inherit from AuditedModelAdmin (100% coverage)."""
        # Arrange: discover all models tracked by simple-history
        tracked_models = [m for m in apps.get_models() if hasattr(m, "history")]
        assert len(tracked_models) == 28, f"Expected 28 tracked models, found {len(tracked_models)}"

        # Act & Assert: verify every tracked model is registered as an AuditedModelAdmin
        unregistered = []
        for model in tracked_models:
            admin_instance = admin.site._registry.get(model)
            if not admin_instance or not issubclass(type(admin_instance), AuditedModelAdmin):
                unregistered.append(model.__name__)

        assert unregistered == [], f"The following tracked models are not AuditedModelAdmin: {unregistered}"

    def test_history_view_displays_action_badges_and_field_deltas(self):
        """Verifies that Django Admin history page renders action badges and field diffs (Before/After)."""
        # Arrange: create staff user and publisher with a field update
        staff_user = User.objects.create(
            email="staff_audit@itqan.dev",
            name="Auditor Staff",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff_user)

        publisher = Publisher.objects.create(
            name_en="Original Publisher",
            name_ar="الناشر الأصلي",
            slug="audit-trail-pub",
        )
        publisher.name_en = "Updated Publisher"
        publisher.save()

        history_url = reverse("admin:publishers_publisher_history", args=[publisher.pk])

        # Act: access history page in Django Admin
        response = self.client.get(history_url)

        # Assert: returns 200, contains styled badges and delta change details
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Action badges present
        assert "Created (+)" in content
        assert "Changed (~)" in content

        # Field deltas present with old and new values
        assert "Original Publisher" in content
        assert "Updated Publisher" in content

    def test_history_view_displays_user_attribution_and_fallback_for_missing_user(self):
        """Verifies that history displays the user's name/email, and gracefully falls back to User #ID."""
        # Arrange: create staff user and publisher
        staff_user = User.objects.create(
            email="creator@itqan.dev",
            name="Original Creator",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff_user)

        publisher = Publisher.objects.create(
            name_en="Attributed Publisher",
            name_ar="ناشر منسوب",
            slug="attr-pub",
        )
        # Update a historical record to simulate an orphaned user ID (e.g. user was purged from operational DB)
        v1_record = publisher.history.first()
        v1_record.history_user_id = 8888
        v1_record.save(update_fields=["history_user_id"])

        history_url = reverse("admin:publishers_publisher_history", args=[publisher.pk])

        # Act: access history page in Django Admin
        response = self.client.get(history_url)

        # Assert: returns 200 and renders the User #8888 fallback badge
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "User #8888" in content

    def test_prune_audit_history_dry_run_does_not_delete_records(self):
        """Verifies that running prune_audit_history with --dry-run simulates pruning without deleting."""
        # Arrange: create an operational issue report with old historical timestamp
        user = User.objects.create(email="reporter@itqan.dev", name="Reporter")
        report = ContentIssueReport.objects.create(
            reporter=user,
            description="Sample typo report",
        )
        v1 = report.history.first()
        old_date = timezone.now() - timedelta(days=400)
        report.history.filter(pk=v1.pk).update(history_date=old_date)

        initial_count = ContentIssueReport.history.count()
        out = StringIO()

        # Act: run prune_audit_history with --dry-run
        call_command(
            "prune_audit_history",
            days=365,
            dry_run=True,
            models="ContentIssueReport",
            stdout=out,
        )

        # Assert: report says records would be pruned, but count remains identical in database
        output = out.getvalue()
        assert "would be pruned" in output
        assert ContentIssueReport.history.count() == initial_count

    def test_prune_audit_history_protects_core_sovereign_models(self):
        """Verifies that core sovereign models (e.g. Publisher) are protected by default from pruning."""
        # Arrange: create publisher and set historical date to 500 days ago
        publisher = Publisher.objects.create(
            name_en="Old Publisher",
            name_ar="ناشر قديم",
            slug="old-pub",
        )
        v1 = publisher.history.first()
        old_date = timezone.now() - timedelta(days=500)
        Publisher.history.filter(pk=v1.pk).update(history_date=old_date)

        initial_count = Publisher.history.count()
        out = StringIO()

        # Act: run prune_audit_history without --force-core
        call_command(
            "prune_audit_history",
            days=365,
            models="Publisher",
            stdout=out,
        )

        # Assert: output indicates core entity protection, and record was NOT deleted
        output = out.getvalue()
        assert "Protected core entity" in output
        assert Publisher.history.count() == initial_count

    def test_prune_audit_history_force_core_allows_pruning_core_models(self):
        """Verifies that passing --force-core allows pruning on core sovereign models when explicitly requested."""
        # Arrange: create publisher with historical record 500 days ago
        publisher = Publisher.objects.create(
            name_en="Prunable Publisher",
            name_ar="ناشر قابل للتقليم",
            slug="prunable-pub",
        )
        v1 = publisher.history.first()
        old_date = timezone.now() - timedelta(days=500)
        Publisher.history.filter(pk=v1.pk).update(history_date=old_date)

        out = StringIO()

        # Act: run prune_audit_history with --force-core
        call_command(
            "prune_audit_history",
            days=365,
            force_core=True,
            models="Publisher",
            stdout=out,
        )

        # Assert: record older than 365 days was successfully pruned
        output = out.getvalue()
        assert "Successfully pruned" in output
        assert not Publisher.history.filter(pk=v1.pk).exists()

    def test_prune_audit_history_invalid_days_raises_command_error(self):
        """Verifies that passing --days < 1 raises CommandError for nonzero exit status (CodeRabbit feedback)."""
        # Arrange & Act & Assert
        with pytest.raises(CommandError, match="--days must be a positive integer."):
            call_command("prune_audit_history", days=0)

    def test_prune_audit_history_invalid_model_selector_raises_command_error(self):
        """Verifies that passing invalid/unknown model selectors raises CommandError (CodeRabbit feedback)."""
        # Arrange & Act & Assert
        with pytest.raises(CommandError, match="do not match any tracked model: invalidmodelname"):
            call_command("prune_audit_history", models="InvalidModelName")

    def test_audited_api_key_admin_save_model_assigns_key_on_create(self):
        """Verifies that creating a new APIKey via AuditedAPIKeyAdmin assigns the raw key and displays warning message (CodeRabbit feedback)."""
        # Arrange
        request = RequestFactory().post("/admin/users/apikey/add/")
        request.user = User.objects.create(email="admin_key_cr@itqan.dev", is_staff=True, is_superuser=True)
        request.session = {}
        request._messages = FallbackStorage(request)

        api_key_admin = admin.site._registry[APIKey]
        api_key = APIKey(name="Test CodeRabbit Key", user=request.user)

        # Act
        api_key_admin.save_model(request, api_key, form=None, change=False)

        # Assert
        assert api_key.pk is not None
        messages = list(request._messages)
        assert len(messages) == 1
        assert "The API key for Test CodeRabbit Key is:" in messages[0].message
        assert api_key.history.count() == 1

    def test_audited_api_key_admin_revert_revoked_key_raises_permission_denied(self):
        """Verifies that attempting to revert a revoked APIKey to an active snapshot raises PermissionDenied (CodeRabbit feedback)."""
        # Arrange: create active key, snapshot it, then revoke it
        staff_user = User.objects.create(email="staff_key_sec@itqan.dev", is_staff=True, is_superuser=True)
        self.client.force_login(staff_user)

        api_key, raw_key = APIKey.objects.create_key(name="Secured Service Key", user=staff_user)
        initial_history_id = api_key.history.first().history_id

        # Now revoke the key in DB
        api_key.revoked = True
        api_key.save()

        # Act & Assert: try to POST to revert view to restore the un-revoked snapshot
        snapshot_url = reverse(
            "admin:users_apikey_simple_history",
            args=[api_key.pk, initial_history_id],
        )
        response = self.client.post(
            snapshot_url, {"name": "Secured Service Key", "user": staff_user.pk, "revoked": False}
        )

        assert response.status_code == 403

    def test_object_history_template_fallbacks(self):
        """Verifies that object_history_list template distinguishes 'Diff unavailable' vs 'No tracked field changes' (CodeRabbit feedback)."""
        from types import SimpleNamespace

        from django.core.paginator import Paginator
        from django.template.loader import render_to_string

        # Arrange: record with empty changes list: []
        rec_empty = SimpleNamespace(
            history_type="~",
            history_delta_changes=[],
            history_date=timezone.now(),
            history_user_id=None,
            history_change_reason="",
            history_id=1,
            history_object="Publisher #1",
            pk=1,
        )

        # Arrange: record with None changes: None
        rec_none = SimpleNamespace(
            history_type="~",
            history_delta_changes=None,
            history_date=timezone.now(),
            history_user_id=None,
            history_change_reason="",
            history_id=2,
            history_object="Publisher #1",
            pk=2,
        )

        page_empty = Paginator([rec_empty], 10).page(1)
        page_none = Paginator([rec_none], 10).page(1)

        # Act & Assert
        html_empty = render_to_string(
            "simple_history/object_history_list.html",
            {
                "page_obj": page_empty,
                "object": SimpleNamespace(pk=1),
                "opts": SimpleNamespace(app_label="publishers", model_name="publisher"),
            },
        )
        assert "No tracked field changes" in html_empty or "لا توجد تغييرات في الحقول المتتبعة" in html_empty

        html_none = render_to_string(
            "simple_history/object_history_list.html",
            {
                "page_obj": page_none,
                "object": SimpleNamespace(pk=1),
                "opts": SimpleNamespace(app_label="publishers", model_name="publisher"),
            },
        )
        assert "Diff unavailable" in html_none or "الفروقات غير متوفرة" in html_none
