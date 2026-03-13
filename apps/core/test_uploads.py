import re
from types import SimpleNamespace
from unittest import TestCase

from apps.core.uploads import (
    _require_fk,
    _safe_pk,
    upload_to_asset_files,
    upload_to_asset_preview_images,
    upload_to_asset_thumbnails,
    upload_to_publisher_icons,
    upload_to_recitation_surah_track_files,
    upload_to_reciter_image,
    upload_to_resource_files,
)

UUID_HEX_8 = re.compile(r"[0-9a-f]{8}")


class RequireFkHelperTest(TestCase):
    """Tests for the _require_fk validation helper"""

    def test_raises_when_field_is_missing_from_instance(self):
        instance = SimpleNamespace()
        with self.assertRaisesRegex(ValueError, "TestModel.id is None"):
            _require_fk(instance, "id", "TestModel", "Save first.")

    def test_raises_when_field_is_none(self):
        instance = SimpleNamespace(asset_id=None)
        with self.assertRaisesRegex(ValueError, "TestModel.asset_id is None"):
            _require_fk(instance, "asset_id", "TestModel", "Link first.")

    def test_raises_when_field_is_empty_string(self):
        instance = SimpleNamespace(asset_id="")
        with self.assertRaisesRegex(ValueError, "TestModel.asset_id is None"):
            _require_fk(instance, "asset_id", "TestModel", "Link first.")

    def test_passes_when_field_has_valid_value(self):
        instance = SimpleNamespace(id=42)
        _require_fk(instance, "id", "TestModel", "Should not raise.")


class SafePkHelperTest(TestCase):
    """Tests for the _safe_pk UUID fallback helper"""

    def test_returns_pk_as_string_when_set(self):
        instance = SimpleNamespace(id=42)
        self.assertEqual(_safe_pk(instance), "42")

    def test_returns_uuid_hex_when_pk_is_none(self):
        instance = SimpleNamespace(id=None)
        result = _safe_pk(instance)
        self.assertTrue(UUID_HEX_8.fullmatch(result), f"Expected 8-char hex, got: {result}")

    def test_returns_uuid_hex_when_id_attr_missing(self):
        instance = SimpleNamespace()
        result = _safe_pk(instance)
        self.assertTrue(UUID_HEX_8.fullmatch(result), f"Expected 8-char hex, got: {result}")


class UploadToPublisherIconsTest(TestCase):
    """Tests for upload_to_publisher_icons (Publisher.icon_url)"""

    def test_generates_correct_path(self):
        instance = SimpleNamespace(id=5)
        result = upload_to_publisher_icons(instance, "logo.PNG")
        self.assertEqual(result, "uploads/publishers/5/icon.png")

    def test_uses_uuid_fallback_when_pk_is_none(self):
        instance = SimpleNamespace(id=None)
        result = upload_to_publisher_icons(instance, "logo.png")
        self.assertRegex(result, r"uploads/publishers/[0-9a-f]{8}/icon\.png")
        self.assertNotIn("None", result)


class UploadToAssetThumbnailsTest(TestCase):
    """Tests for upload_to_asset_thumbnails (Asset.thumbnail_url)"""

    def test_generates_correct_path(self):
        instance = SimpleNamespace(id=12)
        result = upload_to_asset_thumbnails(instance, "cover.JPEG")
        self.assertEqual(result, "uploads/assets/12/thumbnail.jpeg")

    def test_uses_uuid_fallback_when_pk_is_none(self):
        instance = SimpleNamespace(id=None)
        result = upload_to_asset_thumbnails(instance, "cover.jpg")
        self.assertRegex(result, r"uploads/assets/[0-9a-f]{8}/thumbnail\.jpg")
        self.assertNotIn("None", result)


class UploadToAssetPreviewImagesTest(TestCase):
    """Tests for upload_to_asset_preview_images (AssetPreview.image_url)"""

    def test_generates_correct_path(self):
        instance = SimpleNamespace(asset_id=10)
        result = upload_to_asset_preview_images(instance, "preview shot.PNG")
        self.assertEqual(result, "uploads/assets/10/preview/preview-shot.png")

    def test_raises_when_asset_id_is_none(self):
        instance = SimpleNamespace(asset_id=None)
        with self.assertRaisesRegex(ValueError, "AssetPreview.asset_id is None"):
            upload_to_asset_preview_images(instance, "image.jpg")

    def test_raises_when_asset_id_is_empty_string(self):
        instance = SimpleNamespace(asset_id="")
        with self.assertRaisesRegex(ValueError, "AssetPreview.asset_id is None"):
            upload_to_asset_preview_images(instance, "image.jpg")


class UploadToAssetFilesTest(TestCase):
    """Tests for upload_to_asset_files (AssetVersion.file_url)"""

    def test_generates_correct_path(self):
        instance = SimpleNamespace(asset_id=42, id=7)
        result = upload_to_asset_files(instance, "my document.PDF")
        self.assertEqual(result, "uploads/assets/42/versions/7/my-document.pdf")

    def test_raises_when_asset_id_is_none(self):
        instance = SimpleNamespace(asset_id=None, id=7)
        with self.assertRaisesRegex(ValueError, "AssetVersion.asset_id is None"):
            upload_to_asset_files(instance, "file.pdf")

    def test_raises_when_asset_id_is_empty_string(self):
        instance = SimpleNamespace(asset_id="", id=7)
        with self.assertRaisesRegex(ValueError, "AssetVersion.asset_id is None"):
            upload_to_asset_files(instance, "file.pdf")

    def test_uses_uuid_fallback_when_pk_is_none(self):
        instance = SimpleNamespace(asset_id=42, id=None)
        result = upload_to_asset_files(instance, "file.pdf")
        self.assertRegex(result, r"uploads/assets/42/versions/[0-9a-f]{8}/file\.pdf")
        self.assertNotIn("None", result)


class UploadToResourceFilesTest(TestCase):
    """Tests for upload_to_resource_files (ResourceVersion.storage_url)"""

    def test_generates_correct_path(self):
        instance = SimpleNamespace(resource_id=3, id=15)
        result = upload_to_resource_files(instance, "data file.json")
        self.assertEqual(result, "uploads/resources/3/versions/15/data-file.json")

    def test_raises_when_resource_id_is_none(self):
        instance = SimpleNamespace(resource_id=None, id=15)
        with self.assertRaisesRegex(ValueError, "ResourceVersion.resource_id is None"):
            upload_to_resource_files(instance, "file.zip")

    def test_raises_when_resource_id_is_empty_string(self):
        instance = SimpleNamespace(resource_id="", id=15)
        with self.assertRaisesRegex(ValueError, "ResourceVersion.resource_id is None"):
            upload_to_resource_files(instance, "file.zip")

    def test_uses_uuid_fallback_when_pk_is_none(self):
        instance = SimpleNamespace(resource_id=3, id=None)
        result = upload_to_resource_files(instance, "file.zip")
        self.assertRegex(result, r"uploads/resources/3/versions/[0-9a-f]{8}/file\.zip")
        self.assertNotIn("None", result)


class UploadToRecitationSurahTrackFilesTest(TestCase):
    """Tests for upload_to_recitation_surah_track_files (RecitationSurahTrack.audio_file)"""

    def test_generates_correct_path(self):
        instance = SimpleNamespace(asset_id=5, surah_number=114)
        result = upload_to_recitation_surah_track_files(instance, "audio.mp3")
        self.assertEqual(result, "uploads/assets/5/recitations/114.mp3")

    def test_pads_surah_number_to_three_digits(self):
        instance = SimpleNamespace(asset_id=5, surah_number=1)
        result = upload_to_recitation_surah_track_files(instance, "track.mp3")
        self.assertEqual(result, "uploads/assets/5/recitations/001.mp3")

    def test_raises_when_asset_id_is_none(self):
        instance = SimpleNamespace(asset_id=None, surah_number=1)
        with self.assertRaisesRegex(ValueError, "RecitationSurahTrack.asset_id is None"):
            upload_to_recitation_surah_track_files(instance, "track.mp3")

    def test_raises_when_surah_number_is_none(self):
        instance = SimpleNamespace(asset_id=5, surah_number=None)
        with self.assertRaisesRegex(ValueError, "surah_number is None"):
            upload_to_recitation_surah_track_files(instance, "track.mp3")


class UploadToReciterImageTest(TestCase):
    """Tests for upload_to_reciter_image (Reciter.image_url)"""

    def test_generates_correct_path(self):
        instance = SimpleNamespace(id=8)
        result = upload_to_reciter_image(instance, "photo.JPEG")
        self.assertEqual(result, "uploads/reciters/8/icon.jpeg")

    def test_uses_uuid_fallback_when_pk_is_none(self):
        instance = SimpleNamespace(id=None)
        result = upload_to_reciter_image(instance, "photo.jpg")
        self.assertRegex(result, r"uploads/reciters/[0-9a-f]{8}/icon\.jpg")
        self.assertNotIn("None", result)
