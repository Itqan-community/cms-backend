from datetime import UTC, date, datetime

from django.db import IntegrityError, transaction

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import (
    AssetDownloadDaily,
    AssetDownloadEvent,
    AssetDownloadFileKind,
    AssetDownloadHourly,
    AssetDownloadStatusClass,
)


def _hourly(**overrides) -> AssetDownloadHourly:
    values = {
        "hour": datetime(2026, 10, 13, 10, tzinfo=UTC),
        "asset_id": 1,
        "file_kind": AssetDownloadFileKind.SURAH,
        "surah": 1,
        "asset_version_id": None,
        "country": "SA",
        "status_class": AssetDownloadStatusClass.FULL,
        "requests": 1,
        "bytes": 10,
        "plays": 1,
    }
    values.update(overrides)
    return AssetDownloadHourly(**values)


class TestAssetDownloadHourly(BaseTestCase):
    def test_unique_constraint_where_null_version_rows_duplicate_should_raise(self):
        # Arrange
        _hourly().save()

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            _hourly().save()


class TestAssetDownloadDaily(BaseTestCase):
    def test_unique_constraint_where_null_surah_rows_duplicate_should_raise(self):
        # Arrange
        kwargs = {
            "day": date(2026, 10, 13),
            "asset_id": 1,
            "file_kind": AssetDownloadFileKind.VERSION,
            "surah": None,
            "asset_version_id": None,
            "country": "SA",
            "status_class": AssetDownloadStatusClass.FULL,
        }
        AssetDownloadDaily.objects.create(**kwargs)

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetDownloadDaily.objects.create(**kwargs)


class TestAssetDownloadEvent(BaseTestCase):
    def test_ray_id_where_duplicated_should_raise(self):
        # Arrange
        kwargs = {
            "ray_id": "a49d7f1abc4ee1e0",
            "occurred_at": datetime(2026, 10, 13, 10, 0, 18, tzinfo=UTC),
            "asset_id": 13,
            "file_kind": AssetDownloadFileKind.SURAH,
            "surah": 91,
            "country": "SA",
            "status_class": AssetDownloadStatusClass.FULL,
            "client_hash": "x" * 64,
        }
        AssetDownloadEvent.objects.create(**kwargs)

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetDownloadEvent.objects.create(**kwargs)
