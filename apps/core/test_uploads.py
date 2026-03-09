from types import SimpleNamespace
from unittest import TestCase

from apps.core.uploads import (
    _safe_id,
    upload_to_asset_files,
    upload_to_asset_preview_images,
    upload_to_asset_thumbnails,
    upload_to_publisher_icons,
    upload_to_recitation_surah_track_files,
    upload_to_reciter_image,
    upload_to_resource_files,
)


class SafeIdTest(TestCase):
    """Tests for the _safe_id helper that prevents None in file paths."""

    def test_safe_id_where_id_is_integer_should_return_string_of_id(self) -> None:
        """Verify that a valid integer ID is returned as its string representation."""
        result = _safe_id(42)
        self.assertEqual(result, "42")

    def test_safe_id_where_id_is_none_should_return_uuid_fallback(self) -> None:
        """Verify that None produces a 12-character hex fallback instead of 'None'."""
        result = _safe_id(None)
        self.assertNotEqual(result, "None")
        self.assertEqual(len(result), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_safe_id_where_id_is_none_should_return_unique_values(self) -> None:
        """Verify that repeated calls with None produce different fallbacks."""
        results = {_safe_id(None) for _ in range(10)}
        self.assertEqual(len(results), 10)

    def test_safe_id_where_id_is_zero_should_return_zero_string(self) -> None:
        """Verify that zero is treated as a valid ID, not as falsy."""
        result = _safe_id(0)
        self.assertEqual(result, "0")


class UploadToAssetFilesTest(TestCase):
    """Tests for upload_to_asset_files path generation."""

    def test_upload_to_asset_files_where_ids_are_set_should_return_correct_path(self) -> None:
        """Verify correct path when both asset_id and instance id are set."""
        instance = SimpleNamespace(asset_id=5, id=10)
        result = upload_to_asset_files(instance, "document.pdf")
        self.assertEqual(result, "uploads/assets/5/versions/10/document.pdf")

    def test_upload_to_asset_files_where_instance_id_is_none_should_not_contain_none(self) -> None:
        """Verify that /None/ never appears in the path when instance.id is None."""
        instance = SimpleNamespace(asset_id=5, id=None)
        result = upload_to_asset_files(instance, "document.pdf")
        self.assertNotIn("None", result)
        self.assertTrue(result.startswith("uploads/assets/5/versions/"))
        self.assertTrue(result.endswith("/document.pdf"))

    def test_upload_to_asset_files_where_asset_id_is_none_should_not_contain_none(self) -> None:
        """Verify that /None/ never appears in the path when asset_id is None."""
        instance = SimpleNamespace(asset_id=None, id=10)
        result = upload_to_asset_files(instance, "document.pdf")
        self.assertNotIn("None", result)
        self.assertTrue(result.startswith("uploads/assets/"))
        self.assertIn("/versions/10/document.pdf", result)

    def test_upload_to_asset_files_where_both_ids_none_should_not_contain_none(self) -> None:
        """Verify that /None/ never appears when both IDs are None."""
        instance = SimpleNamespace(asset_id=None, id=None)
        result = upload_to_asset_files(instance, "document.pdf")
        self.assertNotIn("None", result)
        self.assertTrue(result.startswith("uploads/assets/"))
        self.assertTrue(result.endswith(".pdf"))


class UploadToResourceFilesTest(TestCase):
    """Tests for upload_to_resource_files path generation."""

    def test_upload_to_resource_files_where_ids_are_set_should_return_correct_path(self) -> None:
        """Verify correct path when both resource_id and instance id are set."""
        instance = SimpleNamespace(resource_id=3, id=7)
        result = upload_to_resource_files(instance, "data.csv")
        self.assertEqual(result, "uploads/resources/3/versions/7/data.csv")

    def test_upload_to_resource_files_where_instance_id_is_none_should_not_contain_none(self) -> None:
        """Verify that /None/ never appears when instance.id is None."""
        instance = SimpleNamespace(resource_id=3, id=None)
        result = upload_to_resource_files(instance, "data.csv")
        self.assertNotIn("None", result)
        self.assertTrue(result.startswith("uploads/resources/3/versions/"))


class UploadToPublisherIconsTest(TestCase):
    """Tests for upload_to_publisher_icons path generation."""

    def test_upload_to_publisher_icons_where_id_is_set_should_return_correct_path(self) -> None:
        """Verify correct path when publisher id is set."""
        instance = SimpleNamespace(id=1)
        result = upload_to_publisher_icons(instance, "logo.png")
        self.assertEqual(result, "uploads/publishers/1/icon.png")

    def test_upload_to_publisher_icons_where_id_is_none_should_not_contain_none(self) -> None:
        """Verify that /None/ never appears when publisher id is None."""
        instance = SimpleNamespace(id=None)
        result = upload_to_publisher_icons(instance, "logo.png")
        self.assertNotIn("None", result)
        self.assertTrue(result.startswith("uploads/publishers/"))
        self.assertTrue(result.endswith("/icon.png"))


class UploadToAssetThumbnailsTest(TestCase):
    """Tests for upload_to_asset_thumbnails path generation."""

    def test_upload_to_asset_thumbnails_where_id_is_set_should_return_correct_path(self) -> None:
        """Verify correct path when asset id is set."""
        instance = SimpleNamespace(id=8)
        result = upload_to_asset_thumbnails(instance, "cover.jpg")
        self.assertEqual(result, "uploads/assets/8/thumbnail.jpg")

    def test_upload_to_asset_thumbnails_where_id_is_none_should_not_contain_none(self) -> None:
        """Verify that /None/ never appears when asset id is None."""
        instance = SimpleNamespace(id=None)
        result = upload_to_asset_thumbnails(instance, "cover.jpg")
        self.assertNotIn("None", result)


class UploadToAssetPreviewImagesTest(TestCase):
    """Tests for upload_to_asset_preview_images path generation."""

    def test_upload_to_asset_preview_images_where_asset_id_is_set_should_return_correct_path(self) -> None:
        """Verify correct path when asset_id is set."""
        instance = SimpleNamespace(asset_id=4)
        result = upload_to_asset_preview_images(instance, "preview shot.png")
        self.assertEqual(result, "uploads/assets/4/preview/preview-shot.png")

    def test_upload_to_asset_preview_images_where_asset_id_is_none_should_not_contain_none(self) -> None:
        """Verify that /None/ never appears when asset_id is None."""
        instance = SimpleNamespace(asset_id=None)
        result = upload_to_asset_preview_images(instance, "shot.png")
        self.assertNotIn("None", result)


class UploadToReciterImageTest(TestCase):
    """Tests for upload_to_reciter_image path generation."""

    def test_upload_to_reciter_image_where_id_is_set_should_return_correct_path(self) -> None:
        """Verify correct path when reciter id is set."""
        instance = SimpleNamespace(id=12)
        result = upload_to_reciter_image(instance, "photo.jpg")
        self.assertEqual(result, "uploads/reciters/12/icon.jpg")

    def test_upload_to_reciter_image_where_id_is_none_should_not_contain_none(self) -> None:
        """Verify that /None/ never appears when reciter id is None."""
        instance = SimpleNamespace(id=None)
        result = upload_to_reciter_image(instance, "photo.jpg")
        self.assertNotIn("None", result)


class UploadToRecitationSurahTrackFilesTest(TestCase):
    """Tests for upload_to_recitation_surah_track_files path generation."""

    def test_upload_to_recitation_surah_track_files_where_ids_set_should_return_correct_path(self) -> None:
        """Verify correct path with valid asset_id and surah_number."""
        instance = SimpleNamespace(asset_id=6, surah_number=2)
        result = upload_to_recitation_surah_track_files(instance, "track.mp3")
        self.assertEqual(result, "uploads/assets/6/recitations/002.mp3")

    def test_upload_to_recitation_surah_track_files_where_asset_id_is_none_should_not_contain_none(self) -> None:
        """Verify that /None/ never appears when asset_id is None."""
        instance = SimpleNamespace(asset_id=None, surah_number=114)
        result = upload_to_recitation_surah_track_files(instance, "track.mp3")
        self.assertNotIn("None", result)
        self.assertTrue(result.endswith("/recitations/114.mp3"))
