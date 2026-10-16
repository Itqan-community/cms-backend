"""Unit and integration tests for AuditHistoryService (ITQ-35 / Issue #433)."""

import pytest
from simple_history.exceptions import NotHistoricalModelError

from apps.content.models import UsageEvent
from apps.core.ninja_utils.errors import ItqanError
from apps.core.services.audit_history import AuditHistoryService
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class AuditHistoryServiceTest(BaseTestCase):
    def test_restore_object_version_where_object_edited_should_restore_prior_field_values(self):
        """Verifies that reverting an edited object restores previous field values and writes an auditable '~' record."""
        # Arrange: create publisher and update its fields
        service = AuditHistoryService()
        publisher = Publisher.objects.create(name="Original Name", slug="orig-slug")
        v1_record = publisher.history.first()

        publisher.name = "Edited Name"
        publisher.save()
        assert publisher.name == "Edited Name"

        # Act: revert to version 1
        restored, new_record = service.restore_object_version(
            Publisher,
            publisher.id,
            version_id=v1_record.history_id,
        )

        # Assert: fields restored in operational table and audit DB records update
        publisher.refresh_from_db()
        assert publisher.name == "Original Name"
        assert restored.name == "Original Name"
        assert new_record.history_type == "~"
        assert "Reverted to historical version" in new_record.history_change_reason

    def test_restore_object_version_where_object_deleted_should_recreate_row_with_original_pk(self):
        """Verifies that restoring a deleted object recreates the row with its original primary key and writes a '+' record."""
        # Arrange: create publisher then delete it
        service = AuditHistoryService()
        publisher = Publisher.objects.create(name="Deleted Publisher", slug="del-slug")
        pub_id = publisher.id
        v1_record = publisher.history.first()

        publisher.delete()
        assert not Publisher.objects.filter(id=pub_id).exists()

        # Act: restore the deleted row
        restored, new_record = service.restore_object_version(
            Publisher,
            pub_id,
            version_id=v1_record.history_id,
        )

        # Assert: row recreated in default DB with same PK, and audit record written with '+'
        assert Publisher.objects.filter(id=pub_id).exists()
        recreated = Publisher.objects.get(id=pub_id)
        assert recreated.name == "Deleted Publisher"
        assert restored.pk == pub_id
        assert new_record.history_type == "+"
        assert "Restored deleted object" in new_record.history_change_reason

    def test_restore_object_version_where_deleted_without_version_should_restore_latest_snapshot(self):
        """Verifies that restoring a deleted object without specifying version_id defaults to the latest pre-deletion snapshot."""
        # Arrange: create publisher, edit, then delete
        service = AuditHistoryService()
        publisher = Publisher.objects.create(name="Step 1", slug="step-slug")
        pub_id = publisher.id
        publisher.name = "Step 2"
        publisher.save()
        publisher.delete()

        assert not Publisher.objects.filter(id=pub_id).exists()

        # Act: restore without specifying version_id (should auto-pick latest valid snapshot)
        restored, new_record = service.restore_object_version(
            Publisher,
            pub_id,
        )

        # Assert: row resurrected with latest pre-deletion state
        recreated = Publisher.objects.get(id=pub_id)
        assert recreated.name == "Step 2"
        assert new_record.history_type == "+"

    def test_restore_object_version_where_reverted_should_write_auditable_history_record_with_user_attribution(self):
        """Verifies that restorations correctly attribute the acting user and custom change reason in historical tables."""
        # Arrange: create staff user and publisher with two versions
        service = AuditHistoryService()
        user = User.objects.create(email="staff@itqan.dev", name="Operator Staff")
        publisher = Publisher.objects.create(name="Version 1", slug="v1-slug")
        v1_record = publisher.history.first()

        publisher.name = "Version 2"
        publisher.save()

        # Act: revert with user attribution and custom reason
        custom_reason = "Manual rollback due to publisher request"
        restored, new_record = service.restore_object_version(
            Publisher,
            publisher.id,
            version_id=v1_record.history_id,
            user=user,
            change_reason=custom_reason,
        )

        # Assert: audit record captures user ID and change reason
        assert new_record.history_user_id == user.pk
        assert new_record.history_change_reason == custom_reason
        latest_audit = Publisher.history.order_by("-history_date").first()
        assert latest_audit.history_user_id == user.pk
        assert latest_audit.history_change_reason == custom_reason

    def test_restore_object_version_where_as_of_datetime_passed_should_restore_snapshot_at_that_time(self):
        """Verifies point-in-time restoration to the latest snapshot on or before a given timestamp."""
        # Arrange: create publisher, capture v1 date, then update
        service = AuditHistoryService()
        publisher = Publisher.objects.create(name="Time T1", slug="t1-slug")
        v1_record = publisher.history.first()
        t1_date = v1_record.history_date

        publisher.name = "Time T2"
        publisher.save()
        v2_record = publisher.history.first()
        assert v2_record.history_date >= t1_date

        # Act: restore as of exact t1_date
        restored, new_record = service.restore_object_version(
            Publisher,
            publisher.id,
            as_of=t1_date,
        )

        # Assert: field values match T1
        publisher.refresh_from_db()
        assert publisher.name == "Time T1"

    def test_restore_object_version_where_untracked_model_should_raise_not_historical_model_error(self):
        """Verifies that attempting to restore an untracked model raises NotHistoricalModelError."""
        # Arrange: UsageEvent is explicitly excluded from simple-history
        service = AuditHistoryService()

        # Act & Assert: raises NotHistoricalModelError
        with pytest.raises(NotHistoricalModelError, match="does not have history tracking enabled"):
            service.restore_object_version(UsageEvent, 1, version_id=1)

    def test_restore_object_version_where_invalid_version_id_should_raise_itqan_error(self):
        """Verifies that passing a non-existent version_id raises a 404 ItqanError."""
        # Arrange: publisher exists with history
        service = AuditHistoryService()
        publisher = Publisher.objects.create(name="Valid Pub", slug="val-pub")

        # Act & Assert: raises ItqanError with 404
        with pytest.raises(ItqanError) as exc_info:
            service.restore_object_version(Publisher, publisher.id, version_id=999999)
        assert exc_info.value.status_code == 404
        assert exc_info.value.error_name == "historical_record_not_found"

    def test_get_object_history_where_object_has_versions_should_return_ordered_history_list(self):
        """Verifies that get_object_history returns ordered historical records with display metadata."""
        # Arrange: publisher created and updated
        service = AuditHistoryService()
        publisher = Publisher.objects.create(name="Pub Initial", slug="pub-init")
        publisher.name = "Pub Updated"
        publisher.save()

        # Act: fetch history list
        history = service.get_object_history(Publisher, publisher.id)

        # Assert: returns list of dicts with 2 records, newest first
        assert len(history) == 2
        assert history[0]["history_type"] == "~"
        assert history[1]["history_type"] == "+"
        assert history[0]["history_id"] > history[1]["history_id"]

    def test_restore_object_version_where_string_identifier_used_should_resolve_model(self):
        """Verifies that model resolution correctly handles string identifiers in '<app>.<Model>' format."""
        # Arrange: publisher created and updated
        service = AuditHistoryService()
        publisher = Publisher.objects.create(name="Str Name 1", slug="str-slug")
        v1_record = publisher.history.first()
        publisher.name = "Str Name 2"
        publisher.save()

        # Act: pass model as string "publishers.Publisher"
        restored, new_record = service.restore_object_version(
            "publishers.Publisher",
            publisher.id,
            version_id=v1_record.history_id,
        )

        # Assert: successfully restored
        publisher.refresh_from_db()
        assert publisher.name == "Str Name 1"
