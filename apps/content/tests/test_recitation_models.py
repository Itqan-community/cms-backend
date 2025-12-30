from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.content.models import Asset, RecitationAyahTiming, RecitationSurahTrack, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher


class RecitationModelsTest(BaseTestCase):
    def test_recitation_surah_track_save_with_audio_should_set_duration_ms(self):
        # Arrange
        pub = Publisher.objects.create(name="Test Pub")
        res = Resource.objects.create(
            publisher=pub,
            name="Recitation Resource",
            description="desc",
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
            license="CC0",
            slug="recitation-resource",
        )
        asset = Asset.objects.create(
            resource=res,
            name="Recitation Set",
            description="desc",
            category=Asset.CategoryChoice.RECITATION,
            license="CC0",
            file_size="1 MB",
            format="mp3",
            version="1.0.0",
            language="ar",
        )
        mp3 = SimpleUploadedFile("t.mp3", b"fake-mp3-bytes")

        # Monkeypatch duration helper to avoid decoding real MP3
        from apps.content import models as content_models

        with patch.object(content_models, "get_mp3_duration_ms", return_value=2500):
            # Act
            track = RecitationSurahTrack.objects.create(
                asset=asset,
                surah_number=2,
                audio_file=mp3,
            )

            # Assert
            self.assertEqual(track.duration_ms, 2500)
            self.assertGreater(track.size_bytes, 0)

    def test_recitation_ayah_timing_save_where_end_after_start_should_set_duration_ms(self):
        # Arrange
        pub = Publisher.objects.create(name="P")
        res = Resource.objects.create(
            publisher=pub,
            name="R",
            description="d",
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
            license="CC0",
            slug="r",
        )
        asset = Asset.objects.create(
            resource=res,
            name="A",
            description="d",
            category=Asset.CategoryChoice.RECITATION,
            license="CC0",
            file_size="1 MB",
            format="mp3",
            version="1.0.0",
            language="ar",
        )
        track = RecitationSurahTrack.objects.create(
            asset=asset, surah_number=1, audio_file=SimpleUploadedFile("t.mp3", b"x")
        )

        # Act
        timing = RecitationAyahTiming.objects.create(track=track, ayah_key="1:1", start_ms=100, end_ms=345)

        # Assert
        self.assertEqual(timing.duration_ms, 245)
