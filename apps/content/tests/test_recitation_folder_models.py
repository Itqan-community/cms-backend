from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, RecitationFolder, RecitationSurahTrack, StatusChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher


def make_recitation_asset(name: str = "Recitation Set") -> Asset:
    return Asset.objects.create(
        publisher=Publisher.objects.create(name=f"Pub {name}"),
        status=StatusChoice.READY,
        name=name,
        description="desc",
        category=CategoryChoice.RECITATION,
        license="CC0",
        file_size="1 MB",
        format="mp3",
        language="ar",
        reciter=baker.make("content.Reciter", name=f"Reciter {name}"),
        riwayah=baker.make("content.Riwayah", name=f"Riwayah {name}"),
    )


class RecitationFolderModelTest(BaseTestCase):
    def test_folder_save_where_slug_missing_should_derive_slug_from_name(self):
        # Arrange
        asset = make_recitation_asset()

        # Act
        folder = RecitationFolder.objects.create(asset=asset, name="With echo", name_en="With echo")

        # Assert
        self.assertEqual(folder.slug, "with-echo")

    def test_folder_save_where_slug_collides_within_asset_should_append_counter(self):
        # Arrange
        asset = make_recitation_asset()
        RecitationFolder.objects.create(asset=asset, name="Clear", name_en="Clear")

        # Act
        second = RecitationFolder.objects.create(asset=asset, name="Clear", name_en="Clear")

        # Assert
        self.assertEqual(second.slug, "clear-1")

    def test_folder_save_where_same_slug_on_different_assets_should_allow_both(self):
        # Arrange
        first_asset = make_recitation_asset("First")
        second_asset = make_recitation_asset("Second")

        # Act
        first = RecitationFolder.objects.create(asset=first_asset, name="Clear", name_en="Clear")
        second = RecitationFolder.objects.create(asset=second_asset, name="Clear", name_en="Clear")

        # Assert - slug uniqueness is scoped per asset, not global
        self.assertEqual(first.slug, "clear")
        self.assertEqual(second.slug, "clear")

    def test_folder_create_where_duplicate_slug_forced_on_same_asset_should_raise_integrity_error(self):
        # Arrange
        asset = make_recitation_asset()
        RecitationFolder.objects.create(asset=asset, name="Clear", slug="clear")

        # Act / Assert
        with self.assertRaises(IntegrityError):
            RecitationFolder.objects.create(asset=asset, name="Other", slug="clear")

    def test_asset_create_where_category_is_recitation_should_auto_create_default_folder(self):
        # Arrange / Act - the post_save signal owns this invariant
        asset = make_recitation_asset()

        # Assert
        folders = RecitationFolder.objects.filter(asset=asset)
        self.assertEqual(folders.count(), 1)
        self.assertTrue(folders.get().is_default)
        self.assertEqual(folders.get().slug, RecitationFolder.DEFAULT_SLUG)

    def test_folder_create_where_second_default_on_same_asset_should_raise_integrity_error(self):
        # Arrange - the asset already has its signal-created default
        asset = make_recitation_asset()

        # Act / Assert
        with self.assertRaises(IntegrityError):
            RecitationFolder.objects.create(asset=asset, name="Echo", slug="echo", is_default=True)

    def test_folder_create_where_default_on_different_assets_should_allow_both(self):
        # Arrange / Act - each asset gets its own default
        make_recitation_asset("First")
        make_recitation_asset("Second")

        # Assert - the one-default constraint is scoped per asset, not global
        self.assertEqual(RecitationFolder.objects.filter(is_default=True).count(), 2)


class RecitationSurahTrackFolderTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.clear = RecitationFolder.objects.get(asset=self.asset, is_default=True)
        self.echo = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

    def test_track_create_where_same_surah_in_two_folders_should_allow_both(self):
        # Arrange
        audio = SimpleUploadedFile("001.mp3", b"fake-mp3-bytes")

        # Act - the whole point of folders: one asset, same surah, two variants
        first = RecitationSurahTrack.objects.create(
            asset=self.asset, folder=self.clear, surah_number=1, audio_file=audio
        )
        second = RecitationSurahTrack.objects.create(
            asset=self.asset, folder=self.echo, surah_number=1, audio_file=audio
        )

        # Assert
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(RecitationSurahTrack.objects.filter(asset=self.asset, surah_number=1).count(), 2)

    def test_track_create_where_duplicate_surah_in_same_folder_should_raise_integrity_error(self):
        # Arrange
        audio = SimpleUploadedFile("001.mp3", b"fake-mp3-bytes")
        RecitationSurahTrack.objects.create(asset=self.asset, folder=self.clear, surah_number=1, audio_file=audio)

        # Act / Assert
        with self.assertRaises(IntegrityError):
            RecitationSurahTrack.objects.create(asset=self.asset, folder=self.clear, surah_number=1, audio_file=audio)

    def test_track_save_where_folder_belongs_to_another_asset_should_raise_value_error(self):
        # Arrange
        other_asset = make_recitation_asset("Other")
        foreign_folder = RecitationFolder.objects.create(asset=other_asset, name="Clear", name_en="Clear")

        # Act / Assert - denormalized asset FK must agree with folder.asset
        with self.assertRaises(ValueError):
            RecitationSurahTrack.objects.create(
                asset=self.asset,
                folder=foreign_folder,
                surah_number=1,
                audio_file=SimpleUploadedFile("001.mp3", b"x"),
            )

    def test_track_delete_where_folder_deleted_should_cascade(self):
        # Arrange
        RecitationSurahTrack.objects.create(
            asset=self.asset, folder=self.echo, surah_number=5, audio_file=SimpleUploadedFile("005.mp3", b"x")
        )

        # Act
        with transaction.atomic():
            self.echo.delete()

        # Assert
        self.assertEqual(RecitationSurahTrack.objects.filter(folder_id=self.echo.pk).count(), 0)
