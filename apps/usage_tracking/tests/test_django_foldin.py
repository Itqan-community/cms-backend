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

    def _event(self, kind: str, delivery: str | None = None, ip: str = "203.0.113.7") -> UsageEvent:
        metadata = {"delivery": delivery} if delivery else {}
        return UsageEvent.objects.create(
            developer_user=self.user,
            usage_kind=kind,
            asset_id=self.asset.id,
            metadata=metadata,
            ip_address=ip,
            user_agent="Mozilla/5.0",
            effective_license=self.asset.license,
        )

    def test_fold_in_where_no_cutover_recorded_should_start_after_existing_events(self):
        # Arrange
        from apps.usage_tracking.models import UsageImportState

        UsageImportState.objects.filter(key="django_foldin").delete()
        self._event("view")

        # Act
        result = fold_in_django_events()

        # Assert
        assert result.events == 0
        assert not TrafficEvent.objects.exists()

    def test_fold_in_where_new_view_and_presigned_download_should_copy_and_skip_cdn(self):
        # Arrange
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

    def test_fold_in_where_rows_arrive_during_rebuild_should_leave_them_for_the_next_run(self):
        # Arrange
        from unittest.mock import patch

        from apps.usage_tracking.models import TrafficSource, UsageImportState
        from apps.usage_tracking.repositories.traffic import TrafficRepository

        fold_in_django_events()
        self._event("view")
        late: list[TrafficEvent] = []
        original = TrafficRepository.rebuild_hour

        def rebuild_and_write(repo, hour, window):
            if not late:
                late.append(
                    baker.make(
                        TrafficEvent, ray_id="django:install:late", source=TrafficSource.DJANGO, occurred_at=hour
                    )
                )
            return original(repo, hour, window)

        # Act
        with patch.object(TrafficRepository, "rebuild_hour", rebuild_and_write):
            fold_in_django_events()

        # Assert
        state = UsageImportState.objects.get(key="django_foldin")
        assert state.traffic_cursor < late[0].id

    def test_fold_in_where_event_is_near_the_end_of_an_hour_should_rebuild_the_next_hour(self):
        # Arrange
        from datetime import UTC, datetime
        from unittest.mock import patch

        from apps.usage_tracking.repositories.traffic import TrafficRepository

        fold_in_django_events()
        event = self._event("file_download", "presigned")
        UsageEvent.objects.filter(pk=event.pk).update(created_at=datetime(2026, 10, 1, 10, 58, tzinfo=UTC))
        rebuilt: list[datetime] = []

        # Act
        with patch.object(TrafficRepository, "rebuild_hour", lambda repo, hour, window: rebuilt.append(hour)):
            fold_in_django_events()

        # Assert
        assert rebuilt == [datetime(2026, 10, 1, 10, tzinfo=UTC), datetime(2026, 10, 1, 11, tzinfo=UTC)]

    def test_fold_in_where_event_has_the_proxy_ip_should_skip_it(self):
        # Arrange: old workers still running during a deploy record Caddy's internal address.
        proxied = self._event("view", ip="172.18.0.5")
        visitor = self._event("view", ip="198.51.100.20")

        # Act
        fold_in_django_events()

        # Assert
        rays = set(TrafficEvent.objects.values_list("ray_id", flat=True))
        assert rays == {f"django:view:{visitor.pk}"}
        assert f"django:view:{proxied.pk}" not in rays


class TestFoldInCutoverMigration(BaseTestCase):
    def test_initialize_cursor_where_no_state_should_start_after_existing_rows(self):
        # Arrange
        import importlib

        from django.apps import apps as global_apps

        from apps.usage_tracking.models import UsageImportState

        migration = importlib.import_module("apps.usage_tracking.migrations.0005_django_foldin_cutover")
        asset = baker.make(Asset, category=CategoryChoice.MUSHAF)
        event = baker.make(UsageEvent, asset_id=asset.id, usage_kind="view")
        traffic = baker.make(TrafficEvent, ray_id="edge-1")
        UsageImportState.objects.filter(key="django_foldin").delete()

        # Act
        migration.initialize_cursor(global_apps, None)
        migration.initialize_cursor(global_apps, None)  # idempotent

        # Assert
        state = UsageImportState.objects.get(key="django_foldin")
        assert (state.cursor, state.traffic_cursor) == (event.id, traffic.id)
