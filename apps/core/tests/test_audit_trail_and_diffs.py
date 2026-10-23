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
        assert len(tracked_models) > 0, "Expected tracked models to be discovered"

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

        # Field deltas present with old and new values rendered inside diff markup
        assert "Original Publisher" in content
        assert "Updated Publisher" in content
        assert "&rarr;" in content
        assert "text-decoration: line-through" in content
        assert "Diff unavailable" not in content
        assert "Initial version created" in content

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
        """Verifies that passing --days < 1 raises CommandError for nonzero exit status."""
        # Arrange & Act & Assert
        with pytest.raises(CommandError, match="--days must be a positive integer."):
            call_command("prune_audit_history", days=0)

    def test_prune_audit_history_invalid_model_selector_raises_command_error(self):
        """Verifies that passing invalid/unknown model selectors raises CommandError."""
        # Arrange & Act & Assert
        with pytest.raises(CommandError, match="do not match any tracked model: invalidmodelname"):
            call_command("prune_audit_history", models="InvalidModelName")

    def test_audited_api_key_admin_save_model_assigns_key_on_create(self):
        """Verifies that creating a new APIKey via AuditedAPIKeyAdmin assigns the raw key and displays warning message."""
        # Arrange
        request = RequestFactory().post("/admin/users/apikey/add/")
        request.user = User.objects.create(email="admin_key_cr@itqan.dev", is_staff=True, is_superuser=True)
        request.session = {}
        request._messages = FallbackStorage(request)

        api_key_admin = admin.site._registry[APIKey]
        api_key = APIKey(name="Test Audited Service Key", user=request.user)

        # Act
        api_key_admin.save_model(request, api_key, form=None, change=False)

        # Assert
        assert api_key.pk is not None
        messages = list(request._messages)
        assert len(messages) == 1
        assert "The API key for Test Audited Service Key is:" in messages[0].message
        assert api_key.history.count() == 1

    def test_audited_api_key_admin_revert_revoked_key_raises_permission_denied(self):
        """Verifies that attempting to revert a revoked APIKey to an active snapshot raises PermissionDenied."""
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
        """Verifies that object_history_list template distinguishes 'Diff unavailable' vs 'No tracked field changes'."""
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

        # Arrange: record with falsy changes (False, 0) and empty changes (None, "")
        rec_falsy = SimpleNamespace(
            history_type="~",
            history_delta_changes=[
                {"field": "is_active", "old": True, "new": False},
                {"field": "score", "old": 10, "new": 0},
                {"field": "description", "old": "Old text", "new": ""},
                {"field": "website", "old": "https://itqan.dev", "new": None},
            ],
            history_date=timezone.now(),
            history_user_id=None,
            history_change_reason="",
            history_id=3,
            history_object="Publisher #1",
            pk=3,
        )
        page_falsy = Paginator([rec_falsy], 10).page(1)
        html_falsy = render_to_string(
            "simple_history/object_history_list.html",
            {
                "page_obj": page_falsy,
                "object": SimpleNamespace(pk=1),
                "opts": SimpleNamespace(app_label="publishers", model_name="publisher"),
            },
        )
        # Assert: False and 0 are preserved and rendered, while None and "" render '(empty)'
        assert "False" in html_falsy
        assert "10" in html_falsy
        assert "score:" in html_falsy
        assert "(empty)" in html_falsy

    def test_prune_audit_history_empty_models_filter_raises_command_error(self):
        """Verifies that passing an empty or whitespace/comma-only --models argument raises CommandError."""
        # Arrange & Act & Assert
        with pytest.raises(CommandError, match="--models was provided but contains no valid model names."):
            call_command("prune_audit_history", models="")

        with pytest.raises(CommandError, match="--models was provided but contains no valid model names."):
            call_command("prune_audit_history", models=" , ,, ")

    def test_prune_audit_history_default_runs_prunes_only_tier_2_models(self):
        """Verifies that running prune_audit_history without --models prunes only documented Tier 2 operational models."""
        # Arrange
        out = StringIO()

        # Act: run without --models
        call_command(
            "prune_audit_history",
            days=365,
            dry_run=True,
            stdout=out,
        )

        output = out.getvalue()
        # Assert: default message is printed and Tier 2 models are scanned
        assert "defaulting to documented Tier 2 operational models" in output
        assert "ContentIssueReport" in output
        assert "AssetAccessRequest" in output
        assert "PublisherMemberInvitation" in output
        assert "MemberLanguage" in output
        # Non-Tier 2 models should NOT be scanned in default run
        assert "EditorialRecommendation:" not in output
        assert "AssetVersionChange:" not in output

    def test_audited_api_key_admin_revert_deleted_revoked_key_raises_permission_denied(self):
        """Verifies that reverting a revoked APIKey that was subsequently deleted from DB raises PermissionDenied."""
        # Arrange: create key, snapshot it, revoke it, then DELETE it from operational DB
        staff_user = User.objects.create(email="staff_deleted_key_sec@itqan.dev", is_staff=True, is_superuser=True)
        self.client.force_login(staff_user)

        api_key, raw_key = APIKey.objects.create_key(name="Deleted Revoked Key", user=staff_user)
        initial_history_id = api_key.history.first().history_id
        key_pk = api_key.pk

        # Revoke the key
        api_key.revoked = True
        api_key.save()

        # Now delete the key from operational DB (operational row is absent)
        api_key.delete()
        assert not APIKey.objects.filter(pk=key_pk).exists()

        # Act & Assert: try to POST to revert view to restore the un-revoked snapshot
        snapshot_url = reverse(
            "admin:users_apikey_simple_history",
            args=[key_pk, initial_history_id],
        )
        response = self.client.post(
            snapshot_url,
            {"name": "Deleted Revoked Key", "user": staff_user.pk, "revoked": False},
        )

        assert response.status_code == 403

    def test_prune_audit_history_preserves_deletion_snapshots(self):
        """Verifies that deletion tombstone snapshots (history_type='-') are permanently preserved even with --force-core."""
        # Arrange: create publisher, delete it to create tombstone snapshot
        publisher = Publisher.objects.create(name_en="Tombstone Publisher", name_ar="ناشر شاهد", slug="tomb-pub")
        pub_pk = publisher.pk
        publisher.delete()

        deletion_record = Publisher.history.filter(id=pub_pk, history_type="-").first()
        assert deletion_record is not None

        # Age the deletion snapshot to 500 days ago
        old_date = timezone.now() - timedelta(days=500)
        Publisher.history.filter(pk=deletion_record.pk).update(history_date=old_date)

        out = StringIO()

        # Act: run prune_audit_history with --force-core
        call_command(
            "prune_audit_history",
            days=365,
            models="Publisher",
            force_core=True,
            stdout=out,
        )

        # Assert: the deletion tombstone record still exists
        assert Publisher.history.filter(pk=deletion_record.pk).exists()

    def test_prune_audit_history_protects_unclosed_workflow_requests(self):
        """Verifies that active/unclosed workflow records (e.g. pending ContentIssueReport) are not pruned."""
        # Arrange: create pending issue report aged 400 days
        user = User.objects.create(email="pending_reporter@itqan.dev", name="Pending Reporter")
        pending_report = ContentIssueReport.objects.create(
            reporter=user,
            description="Active pending report",
            status="pending",
        )
        rec = pending_report.history.first()
        old_date = timezone.now() - timedelta(days=400)
        pending_report.history.filter(pk=rec.pk).update(history_date=old_date)

        out = StringIO()

        # Act: run prune_audit_history on ContentIssueReport
        call_command(
            "prune_audit_history",
            days=365,
            models="ContentIssueReport",
            stdout=out,
        )

        # Assert: pending report historical record was protected and NOT pruned
        assert pending_report.history.filter(pk=rec.pk).exists()

    def test_prune_audit_history_default_runs_real_deletes_tier_2_records(self):
        """Verifies that a real (non-dry-run) default prune deletes closed Tier 2 records while protecting non-Tier 2 models."""
        # Arrange: create resolved issue report (Tier 2 closed) and publisher (non-Tier 2) aged 400 days
        user = User.objects.create(email="real_prune_rep@itqan.dev", name="Real Prune Reporter")
        report = ContentIssueReport.objects.create(
            reporter=user,
            description="Resolved report to prune",
            status="resolved",
        )
        report_hist = report.history.first()
        old_date = timezone.now() - timedelta(days=400)
        ContentIssueReport.history.filter(pk=report_hist.pk).update(history_date=old_date)

        pub = Publisher.objects.create(name_en="Keep Pub", name_ar="ناشر باقي", slug="keep-pub")
        pub_hist = pub.history.first()
        Publisher.history.filter(pk=pub_hist.pk).update(history_date=old_date)

        out = StringIO()

        # Act: run default prune without dry-run
        call_command("prune_audit_history", days=365, stdout=out)

        # Assert: closed Tier 2 record was deleted, non-Tier 2 record was kept
        assert not ContentIssueReport.history.filter(pk=report_hist.pk).exists()
        assert Publisher.history.filter(pk=pub_hist.pk).exists()

    def test_prune_audit_history_cutoff_boundary_364d_kept_366d_deleted(self):
        """Verifies cutoff boundary logic: a 364-day-old record is kept while a 366-day-old record is deleted."""
        # Arrange: create resolved report with two updates at 364 days and 366 days
        user = User.objects.create(email="boundary_rep@itqan.dev", name="Boundary Reporter")
        report = ContentIssueReport.objects.create(
            reporter=user,
            description="Boundary report",
            status="resolved",
        )
        report.description = "Updated boundary report"
        report.save()

        records = list(report.history.order_by("-history_date"))
        rec_364 = records[0]
        rec_366 = records[1]

        now = timezone.now()
        report.history.filter(pk=rec_364.pk).update(history_date=now - timedelta(days=364))
        report.history.filter(pk=rec_366.pk).update(history_date=now - timedelta(days=366))

        out = StringIO()

        # Act: run prune with days=365
        call_command(
            "prune_audit_history",
            days=365,
            models="ContentIssueReport",
            stdout=out,
        )

        # Assert: 364-day record is KEPT, 366-day record is DELETED
        assert ContentIssueReport.history.filter(pk=rec_364.pk).exists()
        assert not ContentIssueReport.history.filter(pk=rec_366.pk).exists()

    def test_history_view_access_without_permission_denied(self):
        """Verifies that accessing history page without view/change permissions returns HTTP 403 Forbidden."""
        # Arrange: create staff user without any publisher permissions
        unauthorized_staff = User.objects.create(
            email="unauth_staff@itqan.dev",
            name="Unauthorized Staff",
            is_staff=True,
            is_superuser=False,
        )
        self.client.force_login(unauthorized_staff)

        pub = Publisher.objects.create(name_en="Perm Pub", name_ar="ناشر صلاحية", slug="perm-pub")
        history_url = reverse("admin:publishers_publisher_history", args=[pub.pk])

        # Act
        response = self.client.get(history_url)

        # Assert: PermissionDenied -> HTTP 403
        assert response.status_code == 403

    def test_pipeline_quran_text_admin_is_read_only(self):
        """Verifies that pipeline-owned Quran text admins are strictly read-only and exclude slow text search."""
        from apps.content.models import AssetVersionChange, AssetVersionChangeReview, AssetVersionEntry

        request = RequestFactory().get("/admin/")
        request.user = User.objects.create(email="staff_quran_chk@itqan.dev", is_staff=True, is_superuser=True)

        for model_cls in [AssetVersionEntry, AssetVersionChange, AssetVersionChangeReview]:
            admin_inst = admin.site._registry[model_cls]
            assert admin_inst.has_add_permission(request) is False
            assert admin_inst.has_change_permission(request) is False
            assert admin_inst.has_delete_permission(request) is False

        entry_admin = admin.site._registry[AssetVersionEntry]
        assert "text" not in entry_admin.search_fields

        change_admin = admin.site._registry[AssetVersionChange]
        assert "old_text" not in change_admin.search_fields
        assert "new_text" not in change_admin.search_fields

    def test_history_view_displays_boolean_false_and_does_not_render_empty(self):
        """Verifies that falsy boolean False is displayed in field diffs without rendering '(empty)'."""
        # Arrange: create staff user and a publisher with is_verified toggled True -> False
        staff_user = User.objects.create(
            email="staff_bool_chk@itqan.dev",
            name="Staff Boolean Checker",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(staff_user)

        publisher = Publisher.objects.create(
            name_en="Bool Test Publisher",
            name_ar="ناشر فحص المنطق",
            slug="bool-test-pub",
            is_verified=True,
        )

        # Act: toggle boolean field is_verified from True to False
        publisher.is_verified = False
        publisher.save()

        history_url = reverse("admin:publishers_publisher_history", args=[publisher.pk])
        response = self.client.get(history_url)

        # Assert: 200 OK, diff displays False and does NOT render (empty) for boolean change
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        assert "Is verified" in content
        assert "True" in content
        assert "False" in content
        assert "(empty)" not in content
