from django.test import override_settings
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, UsageEvent
from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import TrafficEvent, TrafficHourly, TrafficKind
from apps.usage_tracking.services.django_foldin import fold_in_django_events
from apps.users.models import User


@override_settings(USAGE_IDENTITY_KEY="identity")
class TestFoldIn(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="viewer@example.com", name="Viewer")
        self.asset = baker.make(Asset, category=CategoryChoice.MUSHAF)

    def _event(self, kind: str, delivery: str | None = None) -> UsageEvent:
        metadata = {"delivery": delivery} if delivery else {}
        return UsageEvent.objects.create(
            developer_user=self.user,
            usage_kind=kind,
            asset_id=self.asset.id,
            metadata=metadata,
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0",
            effective_license=self.asset.license,
        )

    def test_fold_in_where_first_run_should_start_after_existing_events(self):
        # Arrange
        self._event("view")

        # Act
        result = fold_in_django_events()

        # Assert
        assert result.events == 0
        assert not TrafficEvent.objects.exists()

    def test_fold_in_where_new_view_and_presigned_download_should_copy_and_skip_cdn(self):
        # Arrange
        fold_in_django_events()  # sets the cursor
        view, presigned, cdn = (
            self._event("view"),
            self._event("file_download", "presigned"),
            self._event("file_download", "cdn"),
        )

        # Act
        result = fold_in_django_events()
        fold_in_django_events()  # re-run: no duplicates

        # Assert
        kinds = dict(TrafficEvent.objects.values_list("ray_id", "kind"))
        assert kinds == {
            f"django:view:{view.pk}": TrafficKind.VIEW,
            f"django:download:{presigned.pk}": TrafficKind.GALLERY_DOWNLOAD,
        }
        assert f"django:download:{cdn.pk}" not in kinds
        assert result.events == 2
        assert TrafficHourly.objects.exists()

    def test_fold_in_where_backlog_exceeds_batch_should_copy_everything(self):
        # Arrange
        from unittest.mock import patch

        from apps.usage_tracking.services import django_foldin

        fold_in_django_events()
        for _ in range(5):
            self._event("view")

        # Act
        with patch.object(django_foldin, "_BATCH", 2):
            result = fold_in_django_events()

        # Assert
        assert result.events == 5
        assert TrafficEvent.objects.count() == 5
