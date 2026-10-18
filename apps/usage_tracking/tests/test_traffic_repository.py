from datetime import UTC, date, datetime, timedelta

from model_bakery import baker

from apps.content.models import Asset, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.models import (
    LogFileImport,
    R2ObjectReadsHourly,
    TrafficChannel,
    TrafficDaily,
    TrafficEvent,
    TrafficHourly,
    TrafficKind,
    TrafficMonthlyUniques,
    TrafficPlatform,
    TrafficStatusClass,
    UniqueMeasure,
    UniqueScope,
)
from apps.usage_tracking.repositories.traffic import LOGPUSH_JOB, TrafficRepository

H10 = datetime(2026, 10, 18, 10, tzinfo=UTC)
H11 = H10 + timedelta(hours=1)
WINDOW = timedelta(minutes=5)
FULL = TrafficStatusClass.FULL
PARTIAL = TrafficStatusClass.PARTIAL


def _event(ray: str, at: datetime, **overrides) -> TrafficEvent:
    values = {
        "ray_id": ray,
        "occurred_at": at,
        "kind": TrafficKind.AUDIO_SURAH,
        "asset_id": 13,
        "surah": 91,
        "country": "SA",
        "channel": TrafficChannel.APP_UNIDENTIFIED,
        "platform": TrafficPlatform.ANDROID,
        "status_class": FULL,
        "bytes": 100,
        "listener_id": "a" * 64,
        "ua_family": "dalvik",
        "path": "/media/uploads/assets/13/recitations/091.mp3",
    }
    values.update(overrides)
    return TrafficEvent(**values)


class TestStoreAndRebuild(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = TrafficRepository()

    def _store(self, *events: TrafficEvent, key: str = "http/production/20261018/a.log.gz") -> None:
        self.repo.store_file(key, list(events))

    def test_store_file_where_same_ray_stored_twice_should_keep_one_event(self):
        # Arrange
        self._store(_event("r1", H10), key="k1")

        # Act
        self._store(_event("r1", H10), key="k2")

        # Assert
        assert TrafficEvent.objects.count() == 1
        assert self.repo.imported_keys(["k1", "k2", "k3"]) == {"k1", "k2"}

    def test_store_file_where_error_given_should_record_file_without_rows(self):
        # Act
        self.repo.store_file("bad.log.gz", [], error="EOFError")

        # Assert
        assert LogFileImport.objects.get(key="bad.log.gz").error == "EOFError"

    def test_rebuild_hour_where_200_and_206_pair_should_count_one_play(self):
        # Arrange
        self._store(
            _event("r1", H10 + timedelta(seconds=1)), _event("r2", H10 + timedelta(seconds=2), status_class=PARTIAL)
        )

        # Act
        self.repo.rebuild_hour(H10, WINDOW)

        # Assert
        rows = TrafficHourly.objects.filter(hour=H10)
        assert sum(r.requests for r in rows) == 2
        assert sum(r.sessions for r in rows) == 1
        assert sum(r.bytes for r in rows) == 200

    def test_rebuild_hour_where_gap_over_window_should_count_two_plays(self):
        # Arrange
        self._store(_event("r1", H10), _event("r2", H10 + timedelta(minutes=7)))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)

        # Assert
        assert TrafficHourly.objects.get(hour=H10).sessions == 2

    def test_rebuild_hour_where_play_continues_from_previous_hour_should_not_recount(self):
        # Arrange
        self._store(_event("r1", H11 - timedelta(minutes=2)), _event("r2", H11 + timedelta(minutes=1)))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)
        self.repo.rebuild_hour(H11, WINDOW)

        # Assert
        assert TrafficHourly.objects.get(hour=H10).sessions == 1
        assert TrafficHourly.objects.get(hour=H11).sessions == 0

    def test_rebuild_hour_where_bot_or_error_should_not_count(self):
        # Arrange
        self._store(
            _event("bot", H10, is_bot=True),
            _event("404", H10, listener_id="b" * 64, status_class=TrafficStatusClass.CLIENT_ERROR),
        )

        # Act
        self.repo.rebuild_hour(H10, WINDOW)

        # Assert
        assert not TrafficHourly.objects.filter(hour=H10).exists()

    def test_rebuild_hour_where_api_calls_should_count_each_call_as_session(self):
        # Arrange
        api = {
            "kind": TrafficKind.API_CALL,
            "surah": None,
            "path": "/recitations/13/",
            "endpoint": "/recitations/{asset_id}/",
        }
        self._store(_event("a1", H10, **api), _event("a2", H10 + timedelta(seconds=5), **api))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)

        # Assert
        row = TrafficHourly.objects.get(hour=H10)
        assert (row.requests, row.sessions, row.endpoint) == (2, 2, "/recitations/{asset_id}/")

    def test_rebuild_hour_where_install_repeats_same_day_should_count_once(self):
        # Arrange
        cli = {
            "kind": TrafficKind.CLI_INSTALL,
            "surah": None,
            "asset_version_id": 7,
            "install_id": "i" * 64,
            "channel": TrafficChannel.CLI,
            "platform": TrafficPlatform.DESKTOP,
        }
        self._store(_event("c1", H10, **cli), _event("c2", H11, **cli))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)
        self.repo.rebuild_hour(H11, WINDOW)

        # Assert
        assert TrafficHourly.objects.get(hour=H10).sessions == 1
        assert TrafficHourly.objects.get(hour=H11).sessions == 0

    def test_rebuild_hour_where_run_twice_should_replace_not_add(self):
        # Arrange
        self._store(_event("r1", H10))
        self.repo.rebuild_hour(H10, WINDOW)
        self._store(_event("r2", H10 + timedelta(minutes=30)), key="k2")

        # Act
        self.repo.rebuild_hour(H10, WINDOW)

        # Assert
        row = TrafficHourly.objects.get(hour=H10)
        assert (row.requests, row.sessions) == (2, 2)

    def test_rebuild_hour_where_hours_rebuilt_should_keep_daily_as_sum(self):
        # Arrange
        self._store(_event("r1", H10), _event("r2", H11 + timedelta(minutes=30)))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)
        self.repo.rebuild_hour(H11, WINDOW)

        # Assert
        daily = TrafficDaily.objects.get(day=date(2026, 10, 18))
        assert (daily.requests, daily.sessions, daily.bytes) == (2, 2, 200)


class TestMonthlyUniques(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = TrafficRepository()
        self.publisher = baker.make(Publisher, name="Pub")
        self.asset = baker.make(Asset, publisher=self.publisher, name="A", category=CategoryChoice.MUSHAF)

    def test_rebuild_month_uniques_where_listeners_repeat_should_count_distinct_per_scope(self):
        # Arrange
        self.repo.store_file(
            "k",
            [
                _event("r1", H10, asset_id=self.asset.id),
                _event("r2", H10 + timedelta(days=3), asset_id=self.asset.id),
                _event("r3", H10, asset_id=self.asset.id, listener_id="b" * 64),
            ],
        )

        # Act
        self.repo.rebuild_month_uniques(date(2026, 10, 1))

        # Assert
        counts = {
            (row.scope, row.scope_id): row.count
            for row in TrafficMonthlyUniques.objects.filter(measure=UniqueMeasure.LISTENERS)
        }
        assert counts == {
            (UniqueScope.ALL, 0): 2,
            (UniqueScope.ASSET, self.asset.id): 2,
            (UniqueScope.PUBLISHER, self.publisher.id): 2,
        }


class TestMaintenanceHelpers(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = TrafficRepository()

    def test_purge_events_before_where_old_events_should_delete_only_those(self):
        # Arrange
        self.repo.store_file("k", [_event("old", H10), _event("new", H11)])

        # Act
        deleted = self.repo.purge_events_before(H10 + timedelta(minutes=30))

        # Assert
        assert deleted == 1
        assert list(TrafficEvent.objects.values_list("ray_id", flat=True)) == ["new"]

    def test_edge_requests_by_object_where_file_events_should_count_per_path(self):
        # Arrange
        self.repo.store_file("k", [_event("r1", H10), _event("r2", H10, status_class=PARTIAL), _event("r3", H11)])

        # Act
        counts = self.repo.edge_requests_by_object(H10)

        # Assert
        assert counts == {"/media/uploads/assets/13/recitations/091.mp3": 2}

    def test_replace_r2_reads_where_called_twice_should_replace_and_advance_watermark(self):
        # Arrange
        row = {"hour": H10, "object_key": "media/x.mp3", "asset_id": 13, "reads": 5, "edge_requests": 4}
        self.repo.replace_r2_reads(H10, [R2ObjectReadsHourly(**row)])

        # Act
        self.repo.replace_r2_reads(H10, [R2ObjectReadsHourly(**{**row, "reads": 6})])

        # Assert
        assert R2ObjectReadsHourly.objects.get().reads == 6
        assert self.repo.get_watermark("r2_reconciliation") == H11

    def test_record_run_and_lock_where_used_should_store_state_and_release(self):
        # Act
        acquired = self.repo.try_lock(LOGPUSH_JOB)
        self.repo.unlock(LOGPUSH_JOB)
        self.repo.set_watermark(LOGPUSH_JOB, H10)
        self.repo.record_run(LOGPUSH_JOB, H11, "boom")

        # Assert
        assert acquired is True
        assert self.repo.get_watermark(LOGPUSH_JOB) == H10
