from datetime import UTC, date, datetime, timedelta

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import (
    AssetDownloadDaily,
    AssetDownloadEvent,
    AssetDownloadFileKind,
    AssetDownloadHourly,
    AssetDownloadStatusClass,
    UsageSyncState,
)
from apps.usage_tracking.repositories.asset_downloads import (
    AssetDownloadRepository,
    DownloadEventRow,
    DownloadTotalRow,
)
from apps.usage_tracking.services.download_paths import DownloadFile

H10 = datetime(2026, 10, 13, 10, tzinfo=UTC)
H11 = datetime(2026, 10, 13, 11, tzinfo=UTC)
WINDOW = timedelta(minutes=5)
SURAH_91 = DownloadFile(13, AssetDownloadFileKind.SURAH, 91, None)
FULL = AssetDownloadStatusClass.FULL
PARTIAL = AssetDownloadStatusClass.PARTIAL


def _event(
    ray: str, at: datetime, client: str = "c1", status: str = FULL, file: DownloadFile = SURAH_91
) -> DownloadEventRow:
    return DownloadEventRow(ray, at, file, "SA", status, client * 32)


def _total(requests: int, bytes_: int, status: str = FULL, file: DownloadFile = SURAH_91) -> DownloadTotalRow:
    return DownloadTotalRow(file, "SA", status, requests, bytes_)


class TestReplaceHour(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = AssetDownloadRepository()

    def test_replace_hour_where_200_and_206_pair_should_count_one_play(self):
        # Arrange
        events = [_event("r1", H10 + timedelta(seconds=1)), _event("r2", H10 + timedelta(seconds=2), status=PARTIAL)]
        totals = [_total(1, 100), _total(1, 50, status=PARTIAL)]

        # Act
        self.repo.replace_hour(H10, events, totals, WINDOW)

        # Assert
        rows = {r.status_class: r for r in AssetDownloadHourly.objects.filter(hour=H10)}
        assert (rows[FULL].requests, rows[FULL].bytes, rows[FULL].plays) == (1, 100, 1)
        assert (rows[PARTIAL].requests, rows[PARTIAL].plays) == (1, 0)
        assert AssetDownloadEvent.objects.count() == 2

    def test_replace_hour_where_gap_over_window_should_count_two_plays(self):
        # Arrange
        events = [_event("r1", H10 + timedelta(minutes=1)), _event("r2", H10 + timedelta(minutes=7))]

        # Act
        self.repo.replace_hour(H10, events, [_total(2, 200)], WINDOW)

        # Assert
        assert AssetDownloadHourly.objects.get(hour=H10).plays == 2

    def test_replace_hour_where_different_clients_should_count_separate_plays(self):
        # Arrange
        events = [_event("r1", H10, client="a"), _event("r2", H10 + timedelta(seconds=5), client="b")]

        # Act
        self.repo.replace_hour(H10, events, [_total(2, 200)], WINDOW)

        # Assert
        assert AssetDownloadHourly.objects.get(hour=H10).plays == 2

    def test_replace_hour_where_play_continues_from_previous_hour_should_not_recount(self):
        # Arrange
        self.repo.replace_hour(H10, [_event("r1", H11 - timedelta(minutes=2))], [_total(1, 100)], WINDOW)

        # Act
        self.repo.replace_hour(H11, [_event("r2", H11 + timedelta(minutes=1))], [_total(1, 100)], WINDOW)

        # Assert
        assert AssetDownloadHourly.objects.get(hour=H10).plays == 1
        assert AssetDownloadHourly.objects.get(hour=H11).plays == 0

    def test_replace_hour_where_run_twice_with_changed_data_should_replace_not_add(self):
        # Arrange
        self.repo.replace_hour(H10, [_event("r1", H10)], [_total(1, 100)], WINDOW)
        events = [_event("r1", H10), _event("r9", H10 + timedelta(minutes=30))]

        # Act
        self.repo.replace_hour(H10, events, [_total(2, 300)], WINDOW)

        # Assert
        row = AssetDownloadHourly.objects.get(hour=H10)
        assert (row.requests, row.bytes, row.plays) == (2, 300, 2)
        assert AssetDownloadEvent.objects.count() == 2

    def test_replace_hour_where_hours_written_should_rebuild_daily_as_sum(self):
        # Arrange
        self.repo.replace_hour(H10, [_event("r1", H10)], [_total(1, 100)], WINDOW)

        # Act
        self.repo.replace_hour(H11, [_event("r2", H11 + timedelta(minutes=30))], [_total(3, 300)], WINDOW)
        self.repo.replace_hour(H11, [_event("r2", H11 + timedelta(minutes=30))], [_total(4, 400)], WINDOW)

        # Assert
        daily = AssetDownloadDaily.objects.get(day=date(2026, 10, 13))
        assert (daily.requests, daily.bytes, daily.plays) == (5, 500, 2)

    def test_replace_hour_where_request_failed_should_not_start_a_play(self):
        # Arrange
        other = AssetDownloadStatusClass.OTHER
        events = [_event("r1", H10, status=other), _event("r2", H10 + timedelta(minutes=30), client="b", status=other)]

        # Act
        self.repo.replace_hour(H10, events, [_total(2, 0, status=other)], WINDOW)

        # Assert
        row = AssetDownloadHourly.objects.get(hour=H10)
        assert (row.requests, row.plays) == (2, 0)

    def test_replace_hour_where_same_ray_twice_in_batch_should_store_one_event(self):
        # Act
        self.repo.replace_hour(H10, [_event("dup", H10), _event("dup", H10)], [_total(1, 100)], WINDOW)

        # Assert
        assert AssetDownloadEvent.objects.filter(ray_id="dup").count() == 1
        assert AssetDownloadHourly.objects.get(hour=H10).plays == 1

    def test_replace_hour_where_written_should_advance_watermark_never_backwards(self):
        # Arrange
        self.repo.replace_hour(H11, [], [], WINDOW)

        # Act
        self.repo.replace_hour(H10, [], [], WINDOW)

        # Assert
        assert self.repo.get_watermark() == H11 + timedelta(hours=1)


class TestStateAndMaintenance(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = AssetDownloadRepository()

    def test_try_lock_where_free_should_acquire_and_release(self):
        # Act
        first = self.repo.try_lock()
        self.repo.unlock()

        # Assert
        assert first is True

    def test_record_run_where_error_should_store_it(self):
        # Act
        self.repo.record_run(H11, "boom")

        # Assert
        state = UsageSyncState.objects.get(key="cf_asset_downloads")
        assert (state.last_run_at, state.last_error) == (H11, "boom")

    def test_purge_events_before_where_old_events_should_delete_only_those(self):
        # Arrange
        self.repo.replace_hour(H10, [_event("old", H10), _event("new", H11 - timedelta(seconds=1))], [], WINDOW)

        # Act
        deleted = self.repo.purge_events_before(H10 + timedelta(minutes=30))

        # Assert
        assert deleted == 1
        assert list(AssetDownloadEvent.objects.values_list("ray_id", flat=True)) == ["new"]
