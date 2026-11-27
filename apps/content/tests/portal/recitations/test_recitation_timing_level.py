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
from apps.content.timing_level import timing_level
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationTimingLevelAPITest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.staff_user = User.objects.create_user(email="timing-level@example.com", name="Staff", is_staff=True)
        self.publisher = baker.make(Publisher, name="Timing Level Publisher")
        self.reciter = baker.make(Reciter, name="Timing Level Reciter")
        self.qiraah = baker.make(Qiraah, name="Timing Level Qiraah")
        self.riwayah = baker.make(Riwayah, name="Timing Level Riwayah", qiraah=self.qiraah)

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

    def _track(self, asset: Asset, *, timed: bool, quality: RecitationQuality | None = None) -> None:
        track = baker.make(
            RecitationSurahTrack,
            asset=asset,
            quality=quality or asset.recitation_qualities.get(is_default=True),
            surah_number=108,
            duration_ms=60_000,
        )
        if timed:
            baker.make(RecitationAyahTiming, track=track, ayah_key="108:1", start_ms=0, end_ms=900)

    def _authenticate(self) -> None:
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_READ_RECITATION)

    def test_timing_level_where_ayah_timings_present_or_absent_should_return_ayah_or_none(self):
        # Arrange / Act / Assert
        self.assertEqual("ayah", timing_level(True))
        self.assertIsNone(timing_level(False))
        self.assertIsNone(timing_level(None))

    def test_list_recitations_where_some_timed_should_return_timing_level_per_recitation(self):
        # Arrange
        self._authenticate()
        timed = self._recitation("A timed")
        self._track(timed, timed=True)
        untimed = self._recitation("B untimed")
        self._track(untimed, timed=False)
        no_tracks = self._recitation("C no tracks")

        # Act
        response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        levels = {row["id"]: row["timing_level"] for row in response.json()["results"]}
        self.assertEqual({timed.id: "ayah", untimed.id: None, no_tracks.id: None}, levels)

    def test_list_recitations_where_many_timed_should_not_add_queries_per_row(self):
        # Arrange
        self._authenticate()
        first = self._recitation("Timed 1")
        self._track(first, timed=True)
        with CaptureQueriesContext(connection) as single:
            self.client.get("/portal/recitations/")
        for index in range(2, 5):
            self._track(self._recitation(f"Timed {index}"), timed=True)

        # Act
        with CaptureQueriesContext(connection) as many:
            response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(4, len(response.json()["results"]))
        self.assertEqual(len(single.captured_queries), len(many.captured_queries))

    def test_retrieve_recitation_where_only_hidden_quality_timed_should_return_ayah_timing_level(self):
        # Arrange
        self._authenticate()
        asset = self._recitation("Hidden timed")
        hidden = baker.make(RecitationQuality, asset=asset, name="Hidden", slug="hidden", is_visible=False)
        self._track(asset, timed=True, quality=hidden)

        # Act
        response = self.client.get(f"/portal/recitations/{asset.slug}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("ayah", response.json()["timing_level"])

    def test_retrieve_recitation_where_untimed_should_return_null_timing_level(self):
        # Arrange
        self._authenticate()
        asset = self._recitation("Untimed")
        self._track(asset, timed=False)

        # Act
        response = self.client.get(f"/portal/recitations/{asset.slug}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNone(response.json()["timing_level"])
