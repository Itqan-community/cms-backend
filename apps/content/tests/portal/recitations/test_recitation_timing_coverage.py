from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import (
    Asset,
    CategoryChoice,
    Qiraah,
    RecitationAyahTiming,
    RecitationQuality,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
    StatusChoice,
)
from apps.content.timing_coverage import timing_status
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User

# Surah 1 has 7 ayahs, surah 108 has 3.
FATIHAH_AYAHS = 7
KAWTHAR_AYAHS = 3


class RecitationTimingCoverageAPITest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.staff_user = User.objects.create_user(email="timing-coverage@example.com", name="Staff", is_staff=True)
        self.publisher = baker.make(Publisher, name="Timing Publisher")
        self.reciter = baker.make(Reciter, name="Timing Reciter")
        self.qiraah = baker.make(Qiraah, name="Timing Qiraah")
        self.riwayah = baker.make(Riwayah, name="Timing Riwayah", qiraah=self.qiraah)

    def _recitation(self, name: str) -> Asset:
        return baker.make(
            Asset,
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name=name,
        )

    def _track(self, asset: Asset, surah_number: int, timed_ayahs: int, quality: RecitationQuality | None = None):
        track = baker.make(
            RecitationSurahTrack,
            asset=asset,
            quality=quality or asset.recitation_qualities.get(is_default=True),
            surah_number=surah_number,
            duration_ms=600_000,
        )
        for ayah in range(1, timed_ayahs + 1):
            baker.make(
                RecitationAyahTiming,
                track=track,
                ayah_key=f"{surah_number}:{ayah}",
                start_ms=ayah * 1000,
                end_ms=ayah * 1000 + 900,
            )
        return track

    def _authenticate(self):
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_READ_RECITATION)

    def test_timing_status_where_counts_vary_should_classify_none_partial_full(self):
        # Arrange / Act / Assert
        self.assertEqual("none", timing_status(0, 0))
        self.assertEqual("none", timing_status(0, 10))
        self.assertEqual("partial", timing_status(4, 10))
        self.assertEqual("full", timing_status(10, 10))

    def test_list_recitations_where_tracks_timed_differently_should_return_status_per_recitation(self):
        # Arrange
        self._authenticate()
        untimed = self._recitation("A untimed")
        self._track(untimed, 1, 0)
        no_tracks = self._recitation("B no tracks")
        partial = self._recitation("C partial")
        self._track(partial, 1, FATIHAH_AYAHS)
        self._track(partial, 108, 1)
        full = self._recitation("D full")
        self._track(full, 1, FATIHAH_AYAHS)
        self._track(full, 108, KAWTHAR_AYAHS)

        # Act
        response = self.client.get("/portal/recitations/?ordering=name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        rows = {row["id"]: row for row in response.json()["results"]}
        self.assertEqual(("none", 0, FATIHAH_AYAHS), self._coverage(rows[untimed.id]))
        self.assertEqual(("none", 0, 0), self._coverage(rows[no_tracks.id]))
        self.assertEqual(
            ("partial", FATIHAH_AYAHS + 1, FATIHAH_AYAHS + KAWTHAR_AYAHS), self._coverage(rows[partial.id])
        )
        self.assertEqual(
            ("full", FATIHAH_AYAHS + KAWTHAR_AYAHS, FATIHAH_AYAHS + KAWTHAR_AYAHS), self._coverage(rows[full.id])
        )

    def test_list_recitations_where_second_quality_untimed_should_return_partial(self):
        # Arrange
        self._authenticate()
        asset = self._recitation("Two qualities")
        self._track(asset, 108, KAWTHAR_AYAHS)
        echo = baker.make(RecitationQuality, asset=asset, name="Echo", slug="echo", is_default=False)
        self._track(asset, 108, 0, quality=echo)

        # Act
        response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        (row,) = response.json()["results"]
        self.assertEqual(("partial", KAWTHAR_AYAHS, 2 * KAWTHAR_AYAHS), self._coverage(row))

    def test_list_recitations_where_timings_exceed_surah_ayahs_should_cap_at_ayahs_count(self):
        # Arrange
        self._authenticate()
        asset = self._recitation("Over-timed")
        track = self._track(asset, 108, KAWTHAR_AYAHS)
        baker.make(RecitationAyahTiming, track=track, ayah_key="108:0", start_ms=0, end_ms=500)

        # Act
        response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        (row,) = response.json()["results"]
        self.assertEqual(("full", KAWTHAR_AYAHS, KAWTHAR_AYAHS), self._coverage(row))

    def test_list_recitations_where_more_recitations_should_not_add_queries(self):
        # Arrange
        self._authenticate()
        first = self._recitation("First")
        self._track(first, 108, 1)
        with CaptureQueriesContext(connection) as baseline:
            self.client.get("/portal/recitations/")
        for index in range(5):
            asset = self._recitation(f"More {index}")
            self._track(asset, 1, 2)
            self._track(asset, 108, KAWTHAR_AYAHS)

        # Act
        with CaptureQueriesContext(connection) as grown:
            response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(len(baseline), len(grown))

    def test_list_qualities_where_one_quality_timed_should_return_status_per_quality(self):
        # Arrange
        self._authenticate()
        asset = self._recitation("Qualities")
        self._track(asset, 1, FATIHAH_AYAHS)
        echo = baker.make(RecitationQuality, asset=asset, name="Echo", slug="echo", is_default=False)
        self._track(echo.asset, 1, 3, quality=echo)
        baker.make(RecitationQuality, asset=asset, name="Empty", slug="empty", is_default=False)

        # Act
        response = self.client.get(f"/portal/recitations/{asset.slug}/qualities/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        by_slug = {row["slug"]: row for row in response.json()}
        default_slug = asset.recitation_qualities.get(is_default=True).slug
        self.assertEqual(("full", FATIHAH_AYAHS, FATIHAH_AYAHS), self._coverage(by_slug[default_slug]))
        self.assertEqual(("partial", 3, FATIHAH_AYAHS), self._coverage(by_slug["echo"]))
        self.assertEqual(("none", 0, 0), self._coverage(by_slug["empty"]))

    def test_list_tracks_where_tracks_timed_differently_should_return_status_per_track(self):
        # Arrange
        self._authenticate()
        asset = self._recitation("Tracks")
        self._track(asset, 1, 0)
        self._track(asset, 2, 10)
        self._track(asset, 108, KAWTHAR_AYAHS)

        # Act
        response = self.client.get(f"/portal/recitations/{asset.slug}/recitation-tracks/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        by_surah = {row["surah_number"]: row for row in response.json()["results"]}
        self.assertEqual(("none", 0, FATIHAH_AYAHS), self._coverage(by_surah[1]))
        self.assertEqual(("partial", 10, 286), self._coverage(by_surah[2]))
        self.assertEqual(("full", KAWTHAR_AYAHS, KAWTHAR_AYAHS), self._coverage(by_surah[108]))

    @staticmethod
    def _coverage(row: dict) -> tuple[str, int, int]:
        return row["timing_status"], row["timed_ayahs_count"], row["ayahs_count"]
