from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, RecitationQuality, RecitationSurahTrack, StatusChoice
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.content.services.recitation_quality import RecitationQualityService
from apps.content.services.recitation_quality_resolution import find_quality_by_token
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


class RecitationQualityServiceTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.default_quality = RecitationQuality.objects.get(asset=self.asset, is_default=True)
        self.service = RecitationQualityService()

    def test_create_quality_where_names_given_should_create_non_default_quality(self):
        # Arrange / Act
        quality = self.service.create_quality(asset_id=self.asset.id, name_ar="مع صدى", name_en="With echo")

        # Assert - `name` is a modeltranslation descriptor resolving to the active
        # language (en under test), so assert the stored columns instead.
        self.assertEqual(quality.slug, "with-echo")
        self.assertFalse(quality.is_default)
        self.assertEqual(quality.name_ar, "مع صدى")
        self.assertEqual(quality.name_en, "With echo")

    def test_create_quality_where_both_names_blank_should_raise_quality_name_required(self):
        # Arrange / Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.create_quality(asset_id=self.asset.id, name_ar="   ", name_en="")

        self.assertEqual(ctx.exception.error_name, "quality_name_required")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_resolve_quality_where_slug_omitted_should_return_default_quality(self):
        # Arrange
        RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act
        resolved = self.service.resolve_quality(self.asset.id, quality_slug=None)

        # Assert
        self.assertEqual(resolved.id, self.default_quality.id)

    def test_resolve_quality_where_slug_given_should_return_that_quality(self):
        # Arrange
        echo = RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act
        resolved = self.service.resolve_quality(self.asset.id, quality_slug="with-echo")

        # Assert
        self.assertEqual(resolved.id, echo.id)

    def test_resolve_quality_where_slug_unknown_should_raise_quality_not_found(self):
        # Arrange / Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_quality(self.asset.id, quality_slug="does-not-exist")

        self.assertEqual(ctx.exception.error_name, "quality_not_found")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_resolve_quality_where_asset_has_no_default_should_raise_quality_not_found(self):
        # Arrange - simulate legacy/corrupt data whose default quality went missing;
        # normal creation can no longer produce this, since the signal guarantees one.
        orphan_asset = make_recitation_asset("Orphan")
        RecitationQuality.objects.filter(asset=orphan_asset).delete()

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_quality(orphan_asset.id, quality_slug=None)

        self.assertEqual(ctx.exception.error_name, "quality_not_found")

    def test_update_quality_where_renamed_should_keep_slug_stable(self):
        # Arrange
        RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act
        updated = self.service.update_quality(
            asset_id=self.asset.id,
            quality_slug="with-echo",
            fields={"name_en": "Echo and delay", "name_ar": "مع صدى وتأخير"},
        )

        # Assert - the slug is the public ?quality= value, so renaming must not move it
        self.assertEqual(updated.slug, "with-echo")
        self.assertEqual(updated.name_en, "Echo and delay")
        self.assertEqual(updated.name_ar, "مع صدى وتأخير")

    def test_update_quality_where_both_names_cleared_should_raise_quality_name_required(self):
        # Arrange
        RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.update_quality(
                asset_id=self.asset.id,
                quality_slug="with-echo",
                fields={"name_en": "", "name_ar": ""},
            )

        self.assertEqual(ctx.exception.error_name, "quality_name_required")

    def test_delete_quality_where_quality_is_default_should_raise_cannot_delete_default_quality(self):
        # Arrange / Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.delete_quality(asset_id=self.asset.id, quality_slug=RecitationQuality.DEFAULT_SLUG)

        self.assertEqual(ctx.exception.error_name, "cannot_delete_default_quality")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertTrue(RecitationQuality.objects.filter(id=self.default_quality.id).exists())

    def test_delete_quality_where_quality_is_variant_should_delete_it_and_its_tracks(self):
        # Arrange
        echo = RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        RecitationSurahTrack.objects.create(
            asset=self.asset, quality=echo, surah_number=1, audio_file=SimpleUploadedFile("001.mp3", b"x")
        )

        # Act
        self.service.delete_quality(asset_id=self.asset.id, quality_slug="with-echo")

        # Assert
        self.assertFalse(RecitationQuality.objects.filter(id=echo.id).exists())
        self.assertEqual(RecitationSurahTrack.objects.filter(quality_id=echo.id).count(), 0)

    def test_list_qualities_should_return_default_first(self):
        # Arrange
        RecitationQuality.objects.create(asset=self.asset, name="A variant", name_en="A variant")

        # Act
        qualities = list(self.service.list_qualities(self.asset.id))

        # Assert - default leads so UIs can open on it without extra sorting
        self.assertEqual(qualities[0].id, self.default_quality.id)
        self.assertEqual(len(qualities), 2)


class FindQualityByTokenTest(BaseTestCase):
    """The ?quality= value accepts either a slug or a name."""

    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.default_quality = RecitationQuality.objects.get(asset=self.asset, is_default=True)
        self.echo = RecitationQuality.objects.create(
            asset=self.asset, name="With echo", name_ar="مع صدى", name_en="With echo"
        )

    def test_find_quality_where_token_is_slug_should_return_quality(self):
        # Arrange / Act
        found = find_quality_by_token(self.asset.id, "with-echo")

        # Assert
        self.assertEqual(found.id, self.echo.id)

    def test_find_quality_where_token_is_english_name_should_return_quality(self):
        # Arrange / Act
        found = find_quality_by_token(self.asset.id, "With echo")

        # Assert
        self.assertEqual(found.id, self.echo.id)

    def test_find_quality_where_token_is_arabic_name_should_return_quality(self):
        # Arrange / Act
        found = find_quality_by_token(self.asset.id, "مع صدى")

        # Assert
        self.assertEqual(found.id, self.echo.id)

    def test_find_quality_where_token_case_differs_should_still_match(self):
        # Arrange / Act
        found = find_quality_by_token(self.asset.id, "wItH EcHo")

        # Assert
        self.assertEqual(found.id, self.echo.id)

    def test_find_quality_where_token_unknown_should_return_none(self):
        # Arrange / Act / Assert
        self.assertIsNone(find_quality_by_token(self.asset.id, "does-not-exist"))

    def test_find_quality_where_token_belongs_to_other_asset_should_return_none(self):
        # Arrange
        other = make_recitation_asset("Other")
        RecitationQuality.objects.create(asset=other, name="Secret", name_en="Secret")

        # Act / Assert - qualities never leak across recitations
        self.assertIsNone(find_quality_by_token(self.asset.id, "secret"))

    def test_find_quality_where_name_matches_several_should_prefer_default_then_oldest(self):
        # Arrange - names are not unique per asset; the second "Clear" gets slug clear-1
        first = RecitationQuality.objects.create(asset=self.asset, name="Clear", name_en="Clear")
        second = RecitationQuality.objects.create(asset=self.asset, name="Clear", name_en="Clear")
        self.assertEqual("clear", first.slug)
        self.assertEqual("clear-1", second.slug)

        # Act
        found = find_quality_by_token(self.asset.id, "Clear")

        # Assert - deterministic (oldest), not arbitrary; pass the slug for an exact target
        self.assertEqual(found.id, first.id)

    def test_find_quality_where_slug_collides_with_another_qualities_name_should_prefer_slug(self):
        # Arrange - a quality literally named "with-echo"
        RecitationQuality.objects.create(asset=self.asset, name="with-echo", name_en="with-echo")

        # Act
        found = find_quality_by_token(self.asset.id, "with-echo")

        # Assert - slug is the canonical identifier and wins
        self.assertEqual(found.id, self.echo.id)


class RecitationQualityVisibilityTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.default_quality = RecitationQuality.objects.get(asset=self.asset, is_default=True)
        RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        self.service = RecitationQualityService()

    def test_hide_variant_should_set_is_visible_false(self):
        updated = self.service.update_quality(
            asset_id=self.asset.id,
            quality_slug="with-echo",
            fields={"is_visible": False},
        )
        self.assertFalse(updated.is_visible)

    def test_hide_default_should_raise_cannot_hide_default_quality(self):
        with self.assertRaises(ItqanError) as ctx:
            self.service.update_quality(
                asset_id=self.asset.id,
                quality_slug=RecitationQuality.DEFAULT_SLUG,
                fields={"is_visible": False},
            )
        self.assertEqual(ctx.exception.error_name, "cannot_hide_default_quality")

    def test_promote_variant_should_swap_default_flag(self):
        promoted = self.service.update_quality(
            asset_id=self.asset.id,
            quality_slug="with-echo",
            fields={"is_default": True},
        )
        self.default_quality.refresh_from_db()
        self.assertTrue(promoted.is_default)
        self.assertFalse(self.default_quality.is_default)

    def test_promote_hidden_quality_should_raise_cannot_set_hidden_quality_as_default(self):
        echo = RecitationQuality.objects.get(asset=self.asset, slug="with-echo")
        echo.is_visible = False
        echo.save(update_fields=["is_visible"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.update_quality(
                asset_id=self.asset.id,
                quality_slug="with-echo",
                fields={"is_default": True},
            )
        self.assertEqual(ctx.exception.error_name, "cannot_set_hidden_quality_as_default")

    def test_unset_default_flag_should_raise_cannot_unset_default_quality(self):
        with self.assertRaises(ItqanError) as ctx:
            self.service.update_quality(
                asset_id=self.asset.id,
                quality_slug=RecitationQuality.DEFAULT_SLUG,
                fields={"is_default": False},
            )
        self.assertEqual(ctx.exception.error_name, "cannot_unset_default_quality")


class FindQualityVisibilityTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.echo = RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")

    def test_find_quality_where_hidden_and_require_visible_should_return_none(self):
        self.echo.is_visible = False
        self.echo.save(update_fields=["is_visible"])
        self.assertIsNone(find_quality_by_token(self.asset.id, "with-echo", require_visible=True))
        self.assertIsNotNone(find_quality_by_token(self.asset.id, "with-echo", require_visible=False))


class RecitationServiceQualityScopingTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = make_recitation_asset()
        self.default_quality = RecitationQuality.objects.get(asset=self.asset, is_default=True)
        self.echo_quality = RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        self.service = RecitationService(RecitationRepository())

        for surah_number in (1, 2):
            RecitationSurahTrack.objects.create(
                asset=self.asset,
                quality=self.default_quality,
                surah_number=surah_number,
                audio_file=SimpleUploadedFile(f"{surah_number:03}.mp3", b"x"),
            )
        RecitationSurahTrack.objects.create(
            asset=self.asset,
            quality=self.echo_quality,
            surah_number=1,
            audio_file=SimpleUploadedFile("001.mp3", b"x"),
        )

    def test_get_asset_tracks_where_no_quality_given_should_return_default_quality_tracks(self):
        # Arrange / Act
        tracks = self.service.get_asset_tracks(self.asset.id, publisher_q=None)

        # Assert - pre-quality callers must keep seeing one track per surah
        self.assertEqual(tracks.count(), 2)
        self.assertTrue(all(t.quality_id == self.default_quality.id for t in tracks))

    def test_get_asset_tracks_where_quality_given_should_return_only_that_quality_tracks(self):
        # Arrange / Act
        tracks = self.service.get_asset_tracks(self.asset.id, publisher_q=None, quality="with-echo")

        # Assert
        self.assertEqual(tracks.count(), 1)
        self.assertEqual(tracks.first().quality_id, self.echo_quality.id)

    def test_get_asset_tracks_where_quality_unknown_should_raise_quality_not_found(self):
        # Arrange / Act / Assert - a typo must not look like an empty quality
        with self.assertRaises(ItqanError) as ctx:
            self.service.get_asset_tracks(self.asset.id, publisher_q=None, quality="nope")

        self.assertEqual(ctx.exception.error_name, "quality_not_found")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_asset_tracks_where_quality_empty_should_return_empty_without_error(self):
        # Arrange
        RecitationQuality.objects.create(asset=self.asset, name="Video", name_en="Video")

        # Act
        tracks = self.service.get_asset_tracks(self.asset.id, publisher_q=None, quality="video")

        # Assert - an existing but empty quality is a valid 200, not a 404
        self.assertEqual(tracks.count(), 0)

    def test_get_all_recitations_where_multiple_qualities_should_count_default_quality_surahs_only(self):
        # Arrange / Act
        qs = self.service.get_all_recitations(None, None, annotate_surahs_count=True)
        recitation = qs.get(id=self.asset.id)

        # Assert - 2 default tracks + 1 echo track must not report 3 surahs
        self.assertEqual(recitation.surahs_count, 2)

    def test_get_asset_tracks_where_quality_hidden_should_raise_quality_not_found(self):
        self.echo_quality.is_visible = False
        self.echo_quality.save(update_fields=["is_visible"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.get_asset_tracks(
                self.asset.id,
                publisher_q=None,
                quality="with-echo",
                require_visible_quality=True,
            )
        self.assertEqual(ctx.exception.error_name, "quality_not_found")


class RecitationCreationDefaultQualityTest(BaseTestCase):
    def test_create_recitation_should_create_exactly_one_default_quality(self):
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
        qualities = RecitationQuality.objects.filter(asset_id=recitation.id)
        self.assertEqual(qualities.count(), 1)
        self.assertTrue(qualities.get().is_default)
        self.assertEqual(qualities.get().slug, RecitationQuality.DEFAULT_SLUG)
