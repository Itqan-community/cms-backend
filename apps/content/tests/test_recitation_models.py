from django.core.files.uploadedfile import SimpleUploadedFile
import pytest

from apps.content.models import (
    SURAH_NAMES_AR,
    SURAH_NAMES_EN,
    Asset,
    RecitationAyahTiming,
    RecitationSurahTrack,
    Resource,
)
from apps.publishers.models import Publisher


@pytest.mark.django_db
def test_recitation_surah_track_save_with_audio_should_set_duration_ms(monkeypatch):
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

    monkeypatch.setattr(content_models, "get_mp3_duration_ms", lambda f: 2500)

    # Act
    track = RecitationSurahTrack.objects.create(
        asset=asset,
        surah_number=2,
        surah_name=SURAH_NAMES_EN[1],
        surah_name_ar=SURAH_NAMES_AR[1],
        audio_file=mp3,
    )

    # Assert
    assert track.duration_ms == 2500
    assert track.size_bytes > 0


@pytest.mark.django_db
def test_recitation_ayah_timing_save_where_end_after_start_should_set_duration_ms():
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
    timing = RecitationAyahTiming.objects.create(
        track=track, ayah_key="1:1", start_ms=100, end_ms=345
    )

    # Assert
    assert timing.duration_ms == 245
