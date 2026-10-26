"""Recitation reports (spec §21): listening time, reciter dimensions, listener growth, search terms, coverage."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import (
    Asset,
    CategoryChoice,
    Qiraah,
    RecitationAyahTiming,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.usage_tracking.models import (
    SearchEvent,
    SearchSurface,
    TrafficChannel,
    TrafficDaily,
    TrafficEvent,
    TrafficHourly,
    TrafficKind,
    TrafficPlatform,
    TrafficStatusClass,
)
from apps.usage_tracking.repositories.search_events import SearchEventRepository
from apps.usage_tracking.repositories.traffic import TrafficRepository
from apps.usage_tracking.services import usage_reports
from apps.usage_tracking.services.search_terms import normalize_term
from apps.usage_tracking.services.traffic_maintenance import rebuild_rollups
from apps.users.models import User

BASE = "/portal/usage"
H10 = datetime(2026, 10, 12, 10, tzinfo=UTC)
WINDOW = timedelta(minutes=5)


def _event(ray: str, at: datetime, **overrides) -> TrafficEvent:
    values = {
        "ray_id": ray,
        "occurred_at": at,
        "kind": TrafficKind.AUDIO_SURAH,
        "surah": 1,
        "country": "SA",
        "channel": TrafficChannel.APP_UNIDENTIFIED,
        "platform": TrafficPlatform.ANDROID,
        "status_class": TrafficStatusClass.FULL,
        "bytes": 100,
        "listener_id": "a" * 64,
        "ua_family": "dalvik",
    }
    values.update(overrides)
    return TrafficEvent.objects.create(**values)


def _daily(day: date, **values) -> TrafficDaily:
    row = {"kind": TrafficKind.AUDIO_SURAH, "country": "SA", "channel": "web", "platform": "android", "sessions": 0}
    row.update(values)
    return TrafficDaily.objects.create(day=day, **row)


def _recitation(publisher: Publisher, name: str, reciter: Reciter, riwayah: Riwayah | None = None) -> Asset:
    return baker.make(
        Asset,
        publisher=publisher,
        name=name,
        category=CategoryChoice.RECITATION,
        reciter=reciter,
        riwayah=riwayah,
        qiraah=riwayah.qiraah if riwayah else baker.make(Qiraah),
    )


def _track(asset: Asset, surah: int, *, size: int = 1000, duration_ms: int = 10_000) -> RecitationSurahTrack:
    return RecitationSurahTrack.objects.create(
        asset=asset,
        surah_number=surah,
        audio_file=f"uploads/assets/{asset.id}/recitations/{surah:03}.mp3",
        size_bytes=size,
        duration_ms=duration_ms,
    )


class _ReportTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = User.objects.create_user(email="member@example.com", name="Member")
        self.publisher = baker.make(Publisher, name="Pub A")
        baker.make(
            PublisherMember, user=self.user, publisher=self.publisher, status=PublisherMember.StatusChoice.ACTIVE
        )
        self.reciter = baker.make(Reciter, name="Mishary Alafasy", name_ar="مشاري العفاسي", name_en="Mishary Alafasy")
        self.other_reciter = baker.make(Reciter, name="Saad Al-Ghamdi", name_ar="سعد الغامدي", name_en="Saad Al-Ghamdi")
        self.riwayah = baker.make(Riwayah, name="Hafs", name_ar="حفص", name_en="Hafs")
        self.asset = _recitation(self.publisher, "Recitation A", self.reciter, self.riwayah)
        self.other_asset = _recitation(self.publisher, "Recitation B", self.other_reciter)

    def _allow(self) -> None:
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_USAGE)

    def _get(self, path: str):
        return self.client.get(f"{BASE}/{path}", headers={"x-tenant": str(self.publisher.id)})


class TestListenedSeconds(_ReportTestCase):
    def test_rebuild_hour_where_audio_path_is_a_stored_track_should_convert_bytes_to_seconds(self):
        # Arrange
        track = _track(self.asset, 1, size=1000, duration_ms=10_000)  # 10 ms per byte
        _event("r1", H10, asset_id=self.asset.id, bytes=500, path=f"/media/{track.audio_file.name}")

        # Act
        TrafficRepository().rebuild_hour(H10, WINDOW)

        # Assert
        assert TrafficHourly.objects.get(hour=H10).listened_seconds == 5
        assert TrafficDaily.objects.get(day=H10.date()).listened_seconds == 5

    def test_rebuild_hour_where_audio_path_is_an_ayah_file_should_use_the_ayah_length(self):
        # Arrange
        track = _track(self.asset, 1)
        ayah = RecitationAyahTiming.objects.create(
            track=track, ayah_key="1:1", start_ms=0, end_ms=4000, audio_file="a/ayah_001.mp3", size_bytes=200
        )
        _event(
            "r1",
            H10,
            asset_id=self.asset.id,
            kind=TrafficKind.AUDIO_AYAH,
            bytes=100,
            path=f"/media/{ayah.audio_file.name}",
        )

        # Act
        TrafficRepository().rebuild_hour(H10, WINDOW)

        # Assert
        assert TrafficHourly.objects.get(hour=H10).listened_seconds == 2

    def test_rebuild_hour_where_audio_path_is_unknown_should_add_no_seconds(self):
        # Arrange
        _track(self.asset, 1)
        _event("r1", H10, asset_id=self.asset.id, bytes=500, path="/media/uploads/assets/1/recitations/old.mp3")

        # Act
        TrafficRepository().rebuild_hour(H10, WINDOW)

        # Assert
        row = TrafficHourly.objects.get(hour=H10)
        assert row.listened_seconds == 0
        assert row.bytes == 500

    def test_rebuild_traffic_rollups_where_events_exist_should_fill_listened_seconds(self):
        # Arrange
        track = _track(self.asset, 1)
        _event("r1", H10, asset_id=self.asset.id, bytes=1000, path=f"/media/{track.audio_file.name}")
        TrafficDaily.objects.create(
            day=H10.date(),
            asset_id=self.asset.id,
            kind=TrafficKind.AUDIO_SURAH,
            country="SA",
            channel="web",
            platform="android",
        )  # a stale row from before the column existed

        # Act
        call_command("rebuild_traffic_rollups", "--since", "2026-10-01")

        # Assert
        assert list(TrafficDaily.objects.values_list("listened_seconds", flat=True)) == [10]

    def test_rebuild_rollups_where_import_holds_the_lock_should_skip(self):
        # Arrange
        _event("r1", H10, asset_id=self.asset.id)

        # Act
        with (
            patch.object(TrafficRepository, TrafficRepository.try_lock.__name__, return_value=False),
            patch.object(TrafficRepository, TrafficRepository.rebuild_hour.__name__) as rebuild_hour,
        ):
            rebuilt = rebuild_rollups(date(2026, 10, 1))

        # Assert
        assert rebuilt is None
        rebuild_hour.assert_not_called()


class TestReciterDimensions(_ReportTestCase):
    def setUp(self):
        super().setUp()
        _daily(date(2026, 10, 12), asset_id=self.asset.id, sessions=7, listened_seconds=120)
        _daily(date(2026, 10, 12), asset_id=self.other_asset.id, sessions=3)
        _daily(date(2026, 10, 5), asset_id=self.other_asset.id, sessions=1)
        _daily(date(2026, 10, 5), asset_id=self.asset.id, sessions=6)

    def test_breakdown_where_by_reciter_should_label_each_reciter(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("breakdown/?start_date=2026-10-10&end_date=2026-10-16&by=reciter")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["items"]
        assert [(item["key"], item["label"], item["value"]) for item in items] == [
            (str(self.reciter.id), "Mishary Alafasy", 7),
            (str(self.other_reciter.id), "Saad Al-Ghamdi", 3),
        ]

    def test_summary_where_filtered_by_reciter_should_count_that_reciters_assets_only(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"summary/?start_date=2026-10-10&end_date=2026-10-16&reciter_id={self.reciter.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        metrics = response.json()["metrics"]
        assert metrics["plays"]["value"] == 7
        assert metrics["listening_seconds"]["value"] == 120

    def test_timeseries_where_split_by_riwayah_should_key_by_riwayah(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("timeseries/?start_date=2026-10-12&end_date=2026-10-12&split_by=riwayah")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        series = {item["key"]: item for item in response.json()["series"]}
        assert series[str(self.riwayah.id)]["label"] == "Hafs"
        assert series[str(self.riwayah.id)]["points"][0]["value"] == 7
        assert series[""]["points"][0]["value"] == 3  # no riwayah

    def test_breakdown_where_order_is_growth_should_rank_by_increase(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("breakdown/?start_date=2026-10-10&end_date=2026-10-16&by=asset&order=growth")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["items"]
        # Previous week: 2026-10-03 .. 2026-10-09. B grew 1 → 3, A grew 6 → 7.
        assert [(item["label"], item["value"], item["previous"]) for item in items] == [
            ("Recitation B", 3, 1),
            ("Recitation A", 7, 6),
        ]

    def test_breakdown_where_order_is_growth_by_hour_of_week_should_reject(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("breakdown/?start_date=2026-10-10&end_date=2026-10-16&by=hour_of_week&order=growth")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        assert response.json()["error_name"] == "invalid_dimension"


class TestListenerGrowth(_ReportTestCase):
    def setUp(self):
        super().setUp()
        day = lambda d: datetime(2026, 10, d, 12, tzinfo=UTC)  # noqa: E731
        # Listener a: weeks of 5 Oct and 12 Oct; b: week of 12 Oct only; c: before the range.
        _event("a1", day(6), asset_id=self.asset.id, listener_id="a" * 64)
        _event("a2", day(13), asset_id=self.asset.id, listener_id="a" * 64)
        _event("b1", day(14), asset_id=self.asset.id, listener_id="b" * 64)
        _event("c1", datetime(2026, 9, 1, tzinfo=UTC), asset_id=self.asset.id, listener_id="c" * 64)
        _event("bot", day(14), asset_id=self.asset.id, listener_id="d" * 64, is_bot=True)

    def test_listeners_where_weekly_should_split_new_and_returning_and_accumulate(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("listeners/?start_date=2026-10-05&end_date=2026-10-18&granularity=week")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        points = response.json()["points"]
        assert [(p["t"], p["new"], p["returning"], p["cumulative"]) for p in points] == [
            ("2026-10-05", 1, 0, 2),
            ("2026-10-12", 1, 1, 3),
        ]
        assert response.json()["clamped_start"] is None

    def test_cohorts_where_listener_returns_next_week_should_report_retention(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("cohorts/?start_date=2026-10-05&end_date=2026-10-18")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        cohorts = response.json()["cohorts"]
        assert cohorts == [
            {"week": "2026-10-05", "size": 1, "retention": [1.0, 1.0]},
            {"week": "2026-10-12", "size": 1, "retention": [1.0]},
        ]

    def test_cohorts_where_range_exceeds_26_weeks_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("cohorts/?start_date=2026-01-01&end_date=2026-10-18")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("range_too_large", response.json()["error_name"])

    def test_listeners_where_range_ends_before_retention_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        with patch.object(usage_reports, usage_reports.retention_cutoff.__name__, return_value=date(2026, 10, 1)):
            response = self._get("listeners/?start_date=2026-08-01&end_date=2026-09-15")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("range_before_retention", response.json()["error_name"])

    def test_listeners_where_range_starts_before_retention_should_clamp_it(self):
        # Arrange
        self._allow()

        # Act
        with patch.object(usage_reports, usage_reports.retention_cutoff.__name__, return_value=date(2026, 10, 1)):
            response = self._get("listeners/?start_date=2026-08-01&end_date=2026-10-18&granularity=month")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        assert body["clamped_start"] == "2026-10-01"
        assert [(p["t"], p["new"]) for p in body["points"]] == [("2026-10-01", 2)]

    def test_first_seen_where_by_country_should_flag_countries_new_in_range(self):
        # Arrange
        self._allow()
        _event("eg", datetime(2026, 10, 15, tzinfo=UTC), asset_id=self.asset.id, country="EG")
        _event("xx", datetime(2026, 10, 15, tzinfo=UTC), asset_id=self.asset.id, country="XX")

        # Act
        response = self._get("first-seen/?start_date=2026-10-10&end_date=2026-10-18&by=country")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["items"]
        assert [(item["key"], item["first_seen"], item["new"]) for item in items] == [
            ("EG", "2026-10-15", True),
            ("SA", "2026-09-01", False),
        ]


class TestSearchTerms(_ReportTestCase):
    def _search(self, term: str, *, ip: str = "1.1.1.1", page: int = 1, user_agent: str = "Mozilla/5.0"):
        return self.client.get(
            "/cms-api/reciters/",
            {"search": term, "page": page},
            headers={"x-forwarded-for": ip, "user-agent": user_agent},
        )

    def test_normalize_term_where_arabic_variants_should_unify(self):
        # Arrange
        raw = "  الْعَفَاسِيّ   مُشارى  أحمد ة "

        # Act
        term = normalize_term(raw)

        # Assert
        assert term == "العفاسي مشاري احمد ه"

    def test_gallery_search_where_first_page_should_record_term_and_result_count(self):
        # Arrange
        # (the reciters list needs no authentication)

        # Act
        response = self._search("العفاسي")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        event = SearchEvent.objects.get()
        assert (event.surface, event.term, event.results) == (SearchSurface.RECITERS, "العفاسي", 0)
        assert len(event.listener_id) == 64

    def test_gallery_search_where_later_page_or_bot_should_not_record(self):
        # Arrange
        # (nothing)

        # Act
        self._search("saad", page=2)
        self._search("saad", user_agent="Googlebot/2.1")

        # Assert
        assert not SearchEvent.objects.exists()

    def test_gallery_search_where_typed_letter_by_letter_should_keep_the_final_term(self):
        # Arrange
        # (nothing)

        # Act
        for term in ("s", "sa", "saa", "saad"):
            self._search(term)
        self._search("saad", ip="2.2.2.2")  # another searcher keeps their own row

        # Assert
        assert sorted(SearchEvent.objects.values_list("term", flat=True)) == ["saad", "saad"]

    def test_gallery_search_where_recorded_should_add_two_queries(self):
        # Arrange
        with CaptureQueriesContext(connection) as plain:
            self.client.get("/cms-api/reciters/")

        # Act
        with CaptureQueriesContext(connection) as searched:
            self._search("saad")

        # Assert
        assert len(searched.captured_queries) == len(plain.captured_queries) + 2  # delete keystrokes, insert

    def test_gallery_search_where_recording_fails_should_still_answer(self):
        # Arrange
        # (nothing)

        # Act
        with patch.object(
            SearchEventRepository, SearchEventRepository.record.__name__, side_effect=RuntimeError("down")
        ):
            response = self._search("saad")

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    def _searches(self, term: str, searchers: int, results: int = 0) -> None:
        for index in range(searchers):
            SearchEvent.objects.create(
                occurred_at=datetime(2026, 10, 12, index, tzinfo=UTC),
                surface=SearchSurface.ASSETS,
                term=term,
                results=results,
                listener_id=str(index) * 64,
            )

    def test_search_terms_where_few_searchers_should_hide_term_and_match_entities(self):
        # Arrange
        self._allow()
        self._searches("العفاسي", 3)
        self._searches("حفص", 4, results=2)
        self._searches("rare private text", 2)

        # Act
        response = self._get("search-terms/?start_date=2026-10-10&end_date=2026-10-16")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["items"]
        assert [(item["term"], item["searchers"], item["match"]) for item in items] == [
            ("حفص", 4, {"type": "riwayah", "id": self.riwayah.id, "label": "Hafs"}),
            ("العفاسي", 3, {"type": "reciter", "id": self.reciter.id, "label": "Mishary Alafasy"}),
        ]

    def test_search_terms_where_zero_results_should_list_terms_whose_latest_search_found_nothing(self):
        # Arrange
        self._allow()
        self._searches("husary", 3)
        self._searches("حفص", 3, results=1)

        # Act
        response = self._get("search-terms/?start_date=2026-10-10&end_date=2026-10-16&zero_results=true")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["items"]
        assert [(item["term"], item["zero_results"], item["latest_results"], item["match"]) for item in items] == [
            ("husary", 3, 0, None)
        ]

    def test_admin_search_terms_where_not_staff_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get("/portal/admin/usage/search-terms/?start_date=2026-10-10&end_date=2026-10-16")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])


class TestRecitationCoverage(_ReportTestCase):
    def test_coverage_where_surahs_missing_should_order_them_by_platform_demand(self):
        # Arrange
        self._allow()
        for surah in range(1, 113):  # 113 and 114 missing
            _track(self.asset, surah)
        timed = RecitationSurahTrack.objects.get(asset=self.asset, surah_number=1)
        RecitationAyahTiming.objects.create(track=timed, ayah_key="1:1", start_ms=0, end_ms=10)
        today = datetime.now(UTC).date()
        _daily(today, asset_id=9999, surah=114, sessions=50)  # another publisher's recitation
        _daily(today, asset_id=9999, surah=113, sessions=5)

        # Act
        response = self._get(f"recitation-coverage/?asset_id={self.asset.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        [item] = response.json()["items"]
        assert item["surahs"] == 112
        assert item["missing"] == [113, 114]
        assert item["missing_by_demand"] == [114, 113]
        assert item["timed_share"] == round(1 / 112, 4)

    def test_coverage_where_incomplete_only_should_skip_complete_recitations(self):
        # Arrange
        self._allow()
        for surah in range(1, 115):
            _track(self.other_asset, surah)

        # Act
        response = self._get("recitation-coverage/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["items"]
        assert [(item["name"], item["surahs"], item["timed_share"]) for item in items] == [("Recitation A", 0, None)]

    def test_coverage_where_asset_belongs_to_another_publisher_should_return_404(self):
        # Arrange
        self._allow()
        foreign = _recitation(baker.make(Publisher), "Foreign", self.reciter)

        # Act
        response = self._get(f"recitation-coverage/?asset_id={foreign.id}")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])
