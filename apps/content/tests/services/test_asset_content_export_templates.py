from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionEntry,
    CategoryChoice,
    ChangeTypeChoice,
    MushafLayout,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.repositories.tafsir import TafsirRepository
from apps.content.repositories.translation import TranslationRepository
from apps.content.services.asset_content import AssetContentService
from apps.content.services.asset_templates import unit_spec_for
from apps.content.services.asset_verse_text import extract_verse_text
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.tests.base import BaseTestCase


class EntriesToCsvTemplateTests(QuranDataMixin, BaseTestCase):
    """entries_to_csv_bytes must branch on the template, not assume ayah."""

    def setUp(self):
        super().setUp()
        self.bake_quran()

    def test_entries_to_csv_where_surah_template_should_emit_a_sura_column(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.SURAH)
        version = baker.make(AssetVersion, asset=asset)
        AssetVersionEntry.objects.create(version=version, sura_id=1, text="opening", order=1)
        repo = AssetContentRepository()

        # Act
        csv_bytes = repo.entries_to_csv_bytes(version, unit_spec_for(asset))

        # Assert
        lines = csv_bytes.decode("utf-8").splitlines()
        self.assertEqual("sura,text", lines[0])
        self.assertEqual("1,opening", lines[1])

    def test_entries_to_csv_where_word_template_should_emit_word_columns(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.WORD)
        version = baker.make(AssetVersion, asset=asset)
        AssetVersionEntry.objects.create(version=version, word_id=self.word1.id, text="the", order=1)
        repo = AssetContentRepository()

        # Act
        csv_bytes = repo.entries_to_csv_bytes(version, unit_spec_for(asset))

        # Assert — word_id, sura, aya (number in sura), word (position in ayah), text
        lines = csv_bytes.decode("utf-8").splitlines()
        self.assertEqual("word_id,sura,aya,word,text", lines[0])
        self.assertEqual(f"{self.word1.id},1,1,1,the", lines[1])

    def test_entries_to_csv_where_page_template_should_emit_a_page_column(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )
        version = baker.make(AssetVersion, asset=asset)
        AssetVersionEntry.objects.create(version=version, page_no=3, text="third", order=3)
        repo = AssetContentRepository()

        # Act
        csv_bytes = repo.entries_to_csv_bytes(version, unit_spec_for(asset))

        # Assert
        lines = csv_bytes.decode("utf-8").splitlines()
        self.assertEqual("page,text", lines[0])
        self.assertEqual("3,third", lines[1])

    def test_entries_to_csv_where_multiple_rows_should_come_back_in_order(self):
        # Arrange — two page entries, deliberately created out of display order so
        # the `order_by("order", "id")` tiebreak (not insertion/pk order) is what
        # this actually proves.
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )
        version = baker.make(AssetVersion, asset=asset)
        AssetVersionEntry.objects.create(version=version, page_no=5, text="fifth", order=5)
        AssetVersionEntry.objects.create(version=version, page_no=1, text="first", order=1)
        repo = AssetContentRepository()

        # Act
        csv_bytes = repo.entries_to_csv_bytes(version, unit_spec_for(asset))

        # Assert
        lines = csv_bytes.decode("utf-8").splitlines()
        self.assertEqual(["page,text", "1,first", "5,fifth"], lines)

    def test_entries_to_csv_where_ayah_template_should_be_byte_identical_to_before_templates(self):
        # Arrange — the exact lean/verbose shape the ayah exporter produced before
        # other templates existed: this asset's export must not change one byte.
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)
        version = baker.make(AssetVersion, asset=asset)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, text="in the name of...", order=1)
        repo = AssetContentRepository()
        spec = unit_spec_for(asset)

        # Act
        lean = repo.entries_to_csv_bytes(version, spec).decode("utf-8")
        verbose = repo.entries_to_csv_bytes(version, spec, verbose=True).decode("utf-8")

        # Assert
        self.assertEqual("surah,ayah,text\r\n1,1,in the name of...\r\n", lean)
        self.assertEqual(
            "surah,ayah,surah_name,ayah_text,text\r\n1,1,الفاتحة,ayah 1,in the name of...\r\n",
            verbose,
        )


class SnapshotToCsvTemplateTests(QuranDataMixin, BaseTestCase):
    """snapshot_to_csv_bytes must resolve unit ids through the template's own
    model, not silently assume every id is an ayah id."""

    def setUp(self):
        super().setUp()
        self.bake_quran()

    def test_snapshot_to_csv_where_surah_template_should_not_be_mis_keyed_as_ayah(self):
        # Arrange — a published, pruned surah-template commit: only its delta
        # remains, so the download path must reconstruct + re-key via `spec`.
        # sura id 1 and ayah id 1 coincide (QuranDataMixin bakes both as id=1),
        # so the old ayah-only lookup would silently resolve this to ayah 1's
        # data instead of erroring — a worse failure than a crash.
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.SURAH)
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.PUBLISHED)
        baker.make(
            AssetVersionChange,
            version=version,
            sura_id=1,
            change_type=ChangeTypeChoice.ADDED,
            new_text="opening surah",
            order=1,
        )
        repo = AssetContentRepository()
        spec = unit_spec_for(asset)
        snapshot = repo.reconstruct_entries(version)

        # Act
        csv_bytes = repo.snapshot_to_csv_bytes(snapshot, spec)

        # Assert — the surah's own row, not ayah 1's text under a "surah,text" header
        text = csv_bytes.decode("utf-8")
        self.assertEqual("sura,text\r\n1,opening surah\r\n", text)
        self.assertNotIn(self.ayah1.text, text)

    def test_snapshot_to_csv_where_word_template_should_resolve_via_word_model(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.WORD)
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.PUBLISHED)
        baker.make(
            AssetVersionChange,
            version=version,
            word_id=self.word1.id,
            change_type=ChangeTypeChoice.ADDED,
            new_text="the",
            order=1,
        )
        repo = AssetContentRepository()
        spec = unit_spec_for(asset)
        snapshot = repo.reconstruct_entries(version)

        # Act
        csv_bytes = repo.snapshot_to_csv_bytes(snapshot, spec)

        # Assert
        text = csv_bytes.decode("utf-8")
        self.assertEqual(f"word_id,sura,aya,word,text\r\n{self.word1.id},1,1,1,the\r\n", text)

    def test_snapshot_to_csv_where_ayah_template_verbose_should_not_scale_queries_with_row_count(self):
        # Arrange — a published, pruned ayah-template commit spanning all 3 baked
        # ayahs across 2 suras, so a per-row `.sura` lazy-load (the N+1 this
        # regression-tests against) would show up as more than one query.
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.PUBLISHED)
        for ayah, text in ((self.ayah1, "one"), (self.ayah2, "two"), (self.ayah3, "three")):
            baker.make(
                AssetVersionChange,
                version=version,
                ayah=ayah,
                change_type=ChangeTypeChoice.ADDED,
                new_text=text,
                order=ayah.id,
            )
        repo = AssetContentRepository()
        spec = unit_spec_for(asset)
        snapshot = repo.reconstruct_entries(version)

        # Act — exactly one query (the bulk fetch with `select_related("sura")`),
        # regardless of how many ayahs/suras are in the snapshot.
        with self.assertNumQueries(1):
            csv_bytes = repo.snapshot_to_csv_bytes(snapshot, spec, verbose=True)

        # Assert
        text = csv_bytes.decode("utf-8")
        self.assertIn("one", text)
        self.assertIn("two", text)
        self.assertIn("three", text)


class PublishNonAyahDraftTests(QuranDataMixin, BaseTestCase):
    """Publishing a non-ayah draft must succeed end-to-end (Service -> Repository
    -> ORM) instead of 500ing on an ayah-only CSV writer."""

    def setUp(self):
        super().setUp()
        self.bake_quran()

    def test_publish_draft_where_surah_template_should_publish_and_generate_csv(self):
        # Arrange
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.SURAH,
            status=StatusChoice.READY,
            slug="surah-translation",
            language="ar",
        )
        draft = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.DRAFT, content_edited=True)
        AssetVersionEntry.objects.create(version=draft, sura_id=1, text="opening", order=1)
        service = AssetContentService()

        # Act
        published = service.publish_draft(
            asset.slug, CategoryChoice.TRANSLATION, draft.id, message="first surah commit"
        )

        # Assert
        self.assertEqual(VersionStateChoice.PUBLISHED, published.state)
        self.assertTrue(published.file_url)
        published.file_url.open("rb")
        try:
            content = published.file_url.read().decode("utf-8")
        finally:
            published.file_url.close()
        self.assertEqual("sura,text\r\n1,opening\r\n", content)

    def test_publish_draft_where_word_template_should_publish_and_generate_csv(self):
        # Arrange
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.WORD,
            status=StatusChoice.READY,
            slug="word-translation",
            language="ar",
        )
        draft = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.DRAFT, content_edited=True)
        AssetVersionEntry.objects.create(version=draft, word_id=self.word1.id, text="the", order=1)
        service = AssetContentService()

        # Act
        published = service.publish_draft(asset.slug, CategoryChoice.TRANSLATION, draft.id, message="first word commit")

        # Assert
        self.assertEqual(VersionStateChoice.PUBLISHED, published.state)
        published.file_url.open("rb")
        try:
            content = published.file_url.read().decode("utf-8")
        finally:
            published.file_url.close()
        self.assertEqual(f"word_id,sura,aya,word,text\r\n{self.word1.id},1,1,1,the\r\n", content)

    def test_publish_draft_where_page_template_should_publish_and_generate_csv(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
            status=StatusChoice.READY,
            slug="page-tafsir",
            language="ar",
        )
        draft = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.DRAFT, content_edited=True)
        AssetVersionEntry.objects.create(version=draft, page_no=1, text="first page", order=1)
        service = AssetContentService()

        # Act
        published = service.publish_draft(asset.slug, CategoryChoice.TAFSIR, draft.id, message="first page commit")

        # Assert
        self.assertEqual(VersionStateChoice.PUBLISHED, published.state)
        published.file_url.open("rb")
        try:
            content = published.file_url.read().decode("utf-8")
        finally:
            published.file_url.close()
        self.assertEqual("page,text\r\n1,first page\r\n", content)


class ExtractVerseTextTemplateGuardTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()

    def test_extract_verse_text_where_asset_is_word_based_should_return_none(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.WORD)

        # Act
        result = extract_verse_text(asset, surah=1, ayah=1)

        # Assert
        self.assertIsNone(result)

    def test_extract_verse_text_where_asset_is_surah_based_should_return_none(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.SURAH)

        # Act
        result = extract_verse_text(asset, surah=1, ayah=1)

        # Assert
        self.assertIsNone(result)

    def test_extract_verse_text_where_asset_is_page_based_should_return_none(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.PAGE, mushaf_layout=layout
        )

        # Act
        result = extract_verse_text(asset, surah=1, ayah=1)

        # Assert
        self.assertIsNone(result)


class SamplePickerTemplateFilterTests(QuranDataMixin, BaseTestCase):
    """get_ready_asset must skip non-ayah assets: they can never satisfy
    extract_verse_text's "surah:ayah"-keyed payload, so a surah/word/page asset
    must not be handed to the sampler even when it is otherwise READY."""

    def setUp(self):
        super().setUp()
        self.bake_quran()

    def test_get_ready_translation_where_word_and_ayah_both_ready_should_return_the_ayah_one(self):
        # Arrange — the word asset is created first (lower id); get_ready_asset
        # orders by id, so returning the ayah one proves the template filter is
        # doing the work, not id ordering happening to agree with it.
        baker.make(
            Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.WORD, status=StatusChoice.READY
        )
        ayah_asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH, status=StatusChoice.READY
        )

        # Act
        result = TranslationRepository().get_ready_asset()

        # Assert
        self.assertEqual(ayah_asset.id, result.id)

    def test_get_ready_tafsir_where_word_and_ayah_both_ready_should_return_the_ayah_one(self):
        # Arrange — same shape as the translation repository, for the tafsir one.
        baker.make(Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.WORD, status=StatusChoice.READY)
        ayah_asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH, status=StatusChoice.READY
        )

        # Act
        result = TafsirRepository().get_ready_asset()

        # Assert
        self.assertEqual(ayah_asset.id, result.id)
