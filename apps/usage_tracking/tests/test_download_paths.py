from datetime import date

import pytest

from apps.usage_tracking.models import AssetDownloadFileKind, AssetDownloadStatusClass
from apps.usage_tracking.services.download_paths import (
    DownloadFile,
    client_hash_for,
    normalize_country,
    parse_download_path,
    status_class_for,
)


class TestParseDownloadPath:
    def test_parse_download_path_where_surah_mp3_should_return_surah_file(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/13/recitations/091.mp3")

        # Assert
        assert parsed == DownloadFile(13, AssetDownloadFileKind.SURAH, 91, None)

    def test_parse_download_path_where_surah_has_other_extension_should_return_surah_file(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/7/recitations/002.m4a")

        # Assert
        assert parsed == DownloadFile(7, AssetDownloadFileKind.SURAH, 2, None)

    def test_parse_download_path_where_ayah_audio_should_collapse_to_surah(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/5/recitations/12/002/ayah_255.mp3")

        # Assert
        assert parsed == DownloadFile(5, AssetDownloadFileKind.AYAH, 2, None)

    def test_parse_download_path_where_version_file_should_return_version_id(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/9/versions/44/mushaf-hafs.zip")

        # Assert
        assert parsed == DownloadFile(9, AssetDownloadFileKind.VERSION, None, 44)

    def test_parse_download_path_where_tmp_version_folder_should_return_null_version(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/9/versions/tmp-1a2b3c4d/file.json")

        # Assert
        assert parsed == DownloadFile(9, AssetDownloadFileKind.VERSION, None, None)

    def test_parse_download_path_where_thumbnail_or_preview_should_return_none(self):
        # Act / Assert
        assert parse_download_path("/media/uploads/assets/9/cover.png") is None
        assert parse_download_path("/media/uploads/assets/9/preview/shot.png") is None
        assert parse_download_path("/media/uploads/reciters/3/icon.png") is None

    def test_parse_download_path_where_no_media_prefix_should_return_none(self):
        # Act / Assert
        assert parse_download_path("/uploads/assets/13/recitations/091.mp3") is None


class TestStatusClassFor:
    def test_status_class_for_where_known_statuses_should_map_to_classes(self):
        # Act / Assert
        assert status_class_for(200) == AssetDownloadStatusClass.FULL
        assert status_class_for(206) == AssetDownloadStatusClass.PARTIAL
        assert status_class_for(304) == AssetDownloadStatusClass.OTHER
        assert status_class_for(404) == AssetDownloadStatusClass.OTHER


class TestNormalizeCountry:
    def test_normalize_country_where_value_missing_or_odd_should_return_two_upper_chars(self):
        # Act / Assert
        assert normalize_country("SA") == "SA"
        assert normalize_country("sa") == "SA"
        assert normalize_country("") == "XX"
        assert normalize_country(None) == "XX"
        assert normalize_country("T1") == "T1"
        assert normalize_country("XYZ") == "XY"


class TestClientHashFor:
    @pytest.fixture(autouse=True)
    def _secret_key(self, settings):
        settings.SECRET_KEY = "test-secret"

    def test_client_hash_for_where_same_ip_same_day_should_be_stable(self):
        # Act / Assert
        assert client_hash_for("1.2.3.4", date(2026, 10, 13)) == client_hash_for("1.2.3.4", date(2026, 10, 13))

    def test_client_hash_for_where_different_day_should_differ(self):
        # Act / Assert
        assert client_hash_for("1.2.3.4", date(2026, 10, 13)) != client_hash_for("1.2.3.4", date(2026, 10, 14))

    def test_client_hash_for_where_hashed_should_not_contain_ip(self):
        # Act
        digest = client_hash_for("2a02:9b0:4039::1", date(2026, 10, 13))

        # Assert
        assert len(digest) == 64
        assert "2a02" not in digest


class TestParseDownloadPathBounds:
    def test_parse_download_path_where_asset_id_exceeds_db_integer_should_return_none(self):
        # Act / Assert
        assert parse_download_path("/media/uploads/assets/99999999999/recitations/001.mp3") is None
        assert parse_download_path("/media/uploads/assets/2147483648/versions/1/file.zip") is None

    def test_parse_download_path_where_version_id_exceeds_db_integer_should_return_null_version(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/9/versions/99999999999/file.zip")

        # Assert
        assert parsed == DownloadFile(9, AssetDownloadFileKind.VERSION, None, None)

    def test_parse_download_path_where_surah_outside_1_to_114_should_return_none(self):
        # Act / Assert
        assert parse_download_path("/media/uploads/assets/13/recitations/000.mp3") is None
        assert parse_download_path("/media/uploads/assets/13/recitations/999.mp3") is None
        assert parse_download_path("/media/uploads/assets/13/recitations/1/115/ayah_001.mp3") is None
        assert parse_download_path("/media/uploads/assets/13/recitations/114.mp3") is not None
