from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, RecitationFolder, RecitationSurahTrack, StatusChoice
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.content.services.recitation_folder import RecitationFolderService
from apps.content.services.recitation_folder_resolution import find_folder_by_token
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher


def make_recitation_asset(name: str = "Recitation") -> Asset:
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


class RecitationFolderServiceTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.default_folder = RecitationFolder.objects.get(asset=self.asset, is_default=True)
        self.service = RecitationFolderService()

    def test_create_folder_where_names_given_should_create_non_default_folder(self):
        # Arrange / Act
        folder = self.service.create_folder(asset_id=self.asset.id, name_ar="مع صدى", name_en="With echo")

        # Assert - `name` is a modeltranslation descriptor resolving to the active
        # language (en under test), so assert the stored columns instead.
        self.assertEqual(folder.slug, "with-echo")
        self.assertFalse(folder.is_default)
        self.assertEqual(folder.name_ar, "مع صدى")
        self.assertEqual(folder.name_en, "With echo")

    def test_create_folder_where_both_names_blank_should_raise_folder_name_required(self):
        # Arrange / Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.create_folder(asset_id=self.asset.id, name_ar="   ", name_en="")

        self.assertEqual(ctx.exception.error_name, "folder_name_required")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_resolve_folder_where_slug_omitted_should_return_default_folder(self):
        # Arrange
        RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act
        resolved = self.service.resolve_folder(self.asset.id, folder_slug=None)

        # Assert
        self.assertEqual(resolved.id, self.default_folder.id)

    def test_resolve_folder_where_slug_given_should_return_that_folder(self):
        # Arrange
        echo = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act
        resolved = self.service.resolve_folder(self.asset.id, folder_slug="with-echo")

        # Assert
        self.assertEqual(resolved.id, echo.id)

    def test_resolve_folder_where_slug_unknown_should_raise_folder_not_found(self):
        # Arrange / Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_folder(self.asset.id, folder_slug="does-not-exist")

        self.assertEqual(ctx.exception.error_name, "folder_not_found")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_resolve_folder_where_asset_has_no_default_should_raise_folder_not_found(self):
        # Arrange - simulate legacy/corrupt data whose default folder went missing;
        # normal creation can no longer produce this, since the signal guarantees one.
        orphan_asset = make_recitation_asset("Orphan")
        RecitationFolder.objects.filter(asset=orphan_asset).delete()

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_folder(orphan_asset.id, folder_slug=None)

        self.assertEqual(ctx.exception.error_name, "folder_not_found")

    def test_update_folder_where_renamed_should_keep_slug_stable(self):
        # Arrange
        RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act
        updated = self.service.update_folder(
            asset_id=self.asset.id,
            folder_slug="with-echo",
            fields={"name_en": "Echo and delay", "name_ar": "مع صدى وتأخير"},
        )

        # Assert - the slug is the public ?folder= value, so renaming must not move it
        self.assertEqual(updated.slug, "with-echo")
        self.assertEqual(updated.name_en, "Echo and delay")
        self.assertEqual(updated.name_ar, "مع صدى وتأخير")

    def test_update_folder_where_both_names_cleared_should_raise_folder_name_required(self):
        # Arrange
        RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.update_folder(
                asset_id=self.asset.id,
                folder_slug="with-echo",
                fields={"name_en": "", "name_ar": ""},
            )

        self.assertEqual(ctx.exception.error_name, "folder_name_required")

    def test_delete_folder_where_folder_is_default_should_raise_cannot_delete_default_folder(self):
        # Arrange / Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.delete_folder(asset_id=self.asset.id, folder_slug=RecitationFolder.DEFAULT_SLUG)

        self.assertEqual(ctx.exception.error_name, "cannot_delete_default_folder")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertTrue(RecitationFolder.objects.filter(id=self.default_folder.id).exists())

    def test_delete_folder_where_folder_is_variant_should_delete_it_and_its_tracks(self):
        # Arrange
        echo = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        RecitationSurahTrack.objects.create(
            asset=self.asset, folder=echo, surah_number=1, audio_file=SimpleUploadedFile("001.mp3", b"x")
        )

        # Act
        self.service.delete_folder(asset_id=self.asset.id, folder_slug="with-echo")

        # Assert
        self.assertFalse(RecitationFolder.objects.filter(id=echo.id).exists())
        self.assertEqual(RecitationSurahTrack.objects.filter(folder_id=echo.id).count(), 0)

    def test_list_folders_should_return_default_first(self):
        # Arrange
        RecitationFolder.objects.create(asset=self.asset, name="A variant", name_en="A variant")

        # Act
        folders = list(self.service.list_folders(self.asset.id))

        # Assert - default leads so UIs can open on it without extra sorting
        self.assertEqual(folders[0].id, self.default_folder.id)
        self.assertEqual(len(folders), 2)


class FindFolderByTokenTest(BaseTestCase):
    """The ?folder= value accepts either a slug or a name."""

    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.default_folder = RecitationFolder.objects.get(asset=self.asset, is_default=True)
        self.echo = RecitationFolder.objects.create(
            asset=self.asset, name="With echo", name_ar="مع صدى", name_en="With echo"
        )

    def test_find_folder_where_token_is_slug_should_return_folder(self):
        # Arrange / Act
        found = find_folder_by_token(self.asset.id, "with-echo")

        # Assert
        self.assertEqual(found.id, self.echo.id)

    def test_find_folder_where_token_is_english_name_should_return_folder(self):
        # Arrange / Act
        found = find_folder_by_token(self.asset.id, "With echo")

        # Assert
        self.assertEqual(found.id, self.echo.id)

    def test_find_folder_where_token_is_arabic_name_should_return_folder(self):
        # Arrange / Act
        found = find_folder_by_token(self.asset.id, "مع صدى")

        # Assert
        self.assertEqual(found.id, self.echo.id)

    def test_find_folder_where_token_case_differs_should_still_match(self):
        # Arrange / Act
        found = find_folder_by_token(self.asset.id, "wItH EcHo")

        # Assert
        self.assertEqual(found.id, self.echo.id)

    def test_find_folder_where_token_unknown_should_return_none(self):
        # Arrange / Act / Assert
        self.assertIsNone(find_folder_by_token(self.asset.id, "does-not-exist"))

    def test_find_folder_where_token_belongs_to_other_asset_should_return_none(self):
        # Arrange
        other = make_recitation_asset("Other")
        RecitationFolder.objects.create(asset=other, name="Secret", name_en="Secret")

        # Act / Assert - folders never leak across recitations
        self.assertIsNone(find_folder_by_token(self.asset.id, "secret"))

    def test_find_folder_where_name_matches_several_should_prefer_default_then_oldest(self):
        # Arrange - names are not unique per asset; the second "Clear" gets slug clear-1
        first = RecitationFolder.objects.create(asset=self.asset, name="Clear", name_en="Clear")
        second = RecitationFolder.objects.create(asset=self.asset, name="Clear", name_en="Clear")
        self.assertEqual("clear", first.slug)
        self.assertEqual("clear-1", second.slug)

        # Act
        found = find_folder_by_token(self.asset.id, "Clear")

        # Assert - deterministic (oldest), not arbitrary; pass the slug for an exact target
        self.assertEqual(found.id, first.id)

    def test_find_folder_where_slug_collides_with_another_folders_name_should_prefer_slug(self):
        # Arrange - a folder literally named "with-echo"
        RecitationFolder.objects.create(asset=self.asset, name="with-echo", name_en="with-echo")

        # Act
        found = find_folder_by_token(self.asset.id, "with-echo")

        # Assert - slug is the canonical identifier and wins
        self.assertEqual(found.id, self.echo.id)


class RecitationFolderVisibilityTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.default_folder = RecitationFolder.objects.get(asset=self.asset, is_default=True)
        RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        self.service = RecitationFolderService()

    def test_hide_variant_should_set_is_visible_false(self):
        updated = self.service.update_folder(
            asset_id=self.asset.id,
            folder_slug="with-echo",
            fields={"is_visible": False},
        )
        self.assertFalse(updated.is_visible)

    def test_hide_default_should_raise_cannot_hide_default_folder(self):
        with self.assertRaises(ItqanError) as ctx:
            self.service.update_folder(
                asset_id=self.asset.id,
                folder_slug=RecitationFolder.DEFAULT_SLUG,
                fields={"is_visible": False},
            )
        self.assertEqual(ctx.exception.error_name, "cannot_hide_default_folder")

    def test_promote_variant_should_swap_default_flag(self):
        promoted = self.service.update_folder(
            asset_id=self.asset.id,
            folder_slug="with-echo",
            fields={"is_default": True},
        )
        self.default_folder.refresh_from_db()
        self.assertTrue(promoted.is_default)
        self.assertFalse(self.default_folder.is_default)

    def test_promote_hidden_folder_should_raise_cannot_set_hidden_folder_as_default(self):
        echo = RecitationFolder.objects.get(asset=self.asset, slug="with-echo")
        echo.is_visible = False
        echo.save(update_fields=["is_visible"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.update_folder(
                asset_id=self.asset.id,
                folder_slug="with-echo",
                fields={"is_default": True},
            )
        self.assertEqual(ctx.exception.error_name, "cannot_set_hidden_folder_as_default")

    def test_unset_default_flag_should_raise_cannot_unset_default_folder(self):
        with self.assertRaises(ItqanError) as ctx:
            self.service.update_folder(
                asset_id=self.asset.id,
                folder_slug=RecitationFolder.DEFAULT_SLUG,
                fields={"is_default": False},
            )
        self.assertEqual(ctx.exception.error_name, "cannot_unset_default_folder")


class FindFolderVisibilityTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.echo = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

    def test_find_folder_where_hidden_and_require_visible_should_return_none(self):
        self.echo.is_visible = False
        self.echo.save(update_fields=["is_visible"])
        self.assertIsNone(find_folder_by_token(self.asset.id, "with-echo", require_visible=True))
        self.assertIsNotNone(find_folder_by_token(self.asset.id, "with-echo", require_visible=False))


class RecitationServiceFolderScopingTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.default_folder = RecitationFolder.objects.get(asset=self.asset, is_default=True)
        self.echo_folder = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        self.service = RecitationService(RecitationRepository())

        for surah_number in (1, 2):
            RecitationSurahTrack.objects.create(
                asset=self.asset,
                folder=self.default_folder,
                surah_number=surah_number,
                audio_file=SimpleUploadedFile(f"{surah_number:03}.mp3", b"x"),
            )
        RecitationSurahTrack.objects.create(
            asset=self.asset,
            folder=self.echo_folder,
            surah_number=1,
            audio_file=SimpleUploadedFile("001.mp3", b"x"),
        )

    def test_get_asset_tracks_where_no_folder_given_should_return_default_folder_tracks(self):
        # Arrange / Act
        tracks = self.service.get_asset_tracks(self.asset.id, publisher_q=None)

        # Assert - pre-folder callers must keep seeing one track per surah
        self.assertEqual(tracks.count(), 2)
        self.assertTrue(all(t.folder_id == self.default_folder.id for t in tracks))

    def test_get_asset_tracks_where_folder_given_should_return_only_that_folder_tracks(self):
        # Arrange / Act
        tracks = self.service.get_asset_tracks(self.asset.id, publisher_q=None, folder="with-echo")

        # Assert
        self.assertEqual(tracks.count(), 1)
        self.assertEqual(tracks.first().folder_id, self.echo_folder.id)

    def test_get_asset_tracks_where_folder_unknown_should_raise_folder_not_found(self):
        # Arrange / Act / Assert - a typo must not look like an empty folder
        with self.assertRaises(ItqanError) as ctx:
            self.service.get_asset_tracks(self.asset.id, publisher_q=None, folder="nope")

        self.assertEqual(ctx.exception.error_name, "folder_not_found")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_asset_tracks_where_folder_empty_should_return_empty_without_error(self):
        # Arrange
        RecitationFolder.objects.create(asset=self.asset, name="Video", name_en="Video")

        # Act
        tracks = self.service.get_asset_tracks(self.asset.id, publisher_q=None, folder="video")

        # Assert - an existing but empty folder is a valid 200, not a 404
        self.assertEqual(tracks.count(), 0)

    def test_get_all_recitations_where_multiple_folders_should_count_default_folder_surahs_only(self):
        # Arrange / Act
        qs = self.service.get_all_recitations(None, None, annotate_surahs_count=True)
        recitation = qs.get(id=self.asset.id)

        # Assert - 2 default tracks + 1 echo track must not report 3 surahs
        self.assertEqual(recitation.surahs_count, 2)

    def test_get_asset_tracks_where_folder_hidden_should_raise_folder_not_found(self):
        self.echo_folder.is_visible = False
        self.echo_folder.save(update_fields=["is_visible"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.get_asset_tracks(
                self.asset.id,
                publisher_q=None,
                folder="with-echo",
                require_visible_folder=True,
            )
        self.assertEqual(ctx.exception.error_name, "folder_not_found")


class RecitationCreationDefaultFolderTest(BaseTestCase):
    def test_create_recitation_should_create_exactly_one_default_folder(self):
        # Arrange
        publisher = Publisher.objects.create(name="Pub")
        reciter = baker.make("content.Reciter", name="Reciter")
        riwayah = baker.make("content.Riwayah", name="Riwayah")
        service = RecitationService(RecitationRepository())

        # Act
        recitation = service.create_recitation(
            publisher_id=publisher.id,
            name_ar="تلاوة",
            name_en="Recitation",
            description_ar="وصف",
            description_en="desc",
            license="CC0",
            reciter_id=reciter.id,
            qiraah_id=riwayah.qiraah_id,
            riwayah_id=riwayah.id,
            madd_level=None,
            meem_behaviour=None,
            year=None,
        )

        # Assert
        folders = RecitationFolder.objects.filter(asset_id=recitation.id)
        self.assertEqual(folders.count(), 1)
        self.assertTrue(folders.get().is_default)
        self.assertEqual(folders.get().slug, RecitationFolder.DEFAULT_SLUG)
