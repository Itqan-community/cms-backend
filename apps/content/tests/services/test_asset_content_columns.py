"""Cells per (unit, column): history, reconstruction and CSV layout per column."""

from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetColumn,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionEntry,
    CategoryChoice,
    MushafLayout,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_templates import unit_spec_for
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.tests.base import BaseTestCase


class SingleColumnCsvBytesTests(QuranDataMixin, BaseTestCase):
    """A single `text` column must produce exactly the bytes it did before columns existed."""

    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.repo = AssetContentRepository()

    def _version(self, template, **asset_fields):
        asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, template=template, status=StatusChoice.READY, **asset_fields
        )
        return baker.make(AssetVersion, asset=asset)

    def test_entries_to_csv_bytes_where_surah_single_text_column_should_match_staging_bytes(self):
        # Arrange
        version = self._version(AssetTemplateChoice.SURAH)
        AssetVersionEntry.objects.create(version=version, sura=self.sura1, text="first", order=1)

        # Act
        content = self.repo.entries_to_csv_bytes(version, unit_spec_for(version.asset))

        # Assert
        self.assertEqual(content, b"sura,text\r\n1,first\r\n2,\r\n")

    def test_entries_to_csv_bytes_where_ayah_lean_single_text_column_should_match_staging_bytes(self):
        # Arrange
        version = self._version(AssetTemplateChoice.AYAH)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah2, text="two", order=2)

        # Act
        content = self.repo.entries_to_csv_bytes(version, unit_spec_for(version.asset))

        # Assert
        self.assertEqual(content, b"surah,ayah,text\r\n1,1,\r\n1,2,two\r\n2,1,\r\n")

    def test_entries_to_csv_bytes_where_ayah_verbose_single_text_column_should_match_staging_bytes(self):
        # Arrange
        version = self._version(AssetTemplateChoice.AYAH)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, text="one", order=1)

        # Act
        content = self.repo.entries_to_csv_bytes(version, unit_spec_for(version.asset), verbose=True)

        # Assert
        expected = (
            "surah,ayah,surah_name,ayah_text,text\r\n"
            "1,1,الفاتحة,ayah 1,one\r\n1,2,الفاتحة,ayah 2,\r\n2,1,البقرة,ayah 3,\r\n"
        ).encode()
        self.assertEqual(content, expected)

    def test_entries_to_csv_bytes_where_word_single_text_column_should_match_staging_bytes(self):
        # Arrange
        version = self._version(AssetTemplateChoice.WORD)
        AssetVersionEntry.objects.create(version=version, word=self.word2, text="w", order=2)

        # Act
        content = self.repo.entries_to_csv_bytes(version, unit_spec_for(version.asset))

        # Assert
        self.assertEqual(content, b"word_id,sura,aya,word,text\r\n1,1,1,1,\r\n2,1,1,2,w\r\n")

    def test_entries_to_csv_bytes_where_page_single_text_column_should_match_staging_bytes(self):
        # Arrange
        layout = baker.make(MushafLayout, page_count=2)
        version = self._version(AssetTemplateChoice.PAGE, mushaf_layout=layout)
        AssetVersionEntry.objects.create(version=version, page_no=2, text="p2", order=2)

        # Act
        content = self.repo.entries_to_csv_bytes(version, unit_spec_for(version.asset))

        # Assert
        self.assertEqual(content, b"page,text\r\n1,\r\n2,p2\r\n")


class MultiColumnContentTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.repo = AssetContentRepository()
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.AYAH,
            status=StatusChoice.READY,
            language="ar",
        )
        self.question = AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        self.answer = AssetColumn.objects.create(asset=self.asset, key="answer", order=1)

    def _draft(self, cells: dict[tuple[int, AssetColumn], str]) -> AssetVersion:
        draft = baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.DRAFT, content_edited=True)
        for (ayah_id, column), text in cells.items():
            AssetVersionEntry.objects.create(version=draft, ayah_id=ayah_id, column=column, text=text, order=ayah_id)
        return draft

    def _commit(self, cells: dict[tuple[int, AssetColumn], str], name: str) -> AssetVersion:
        draft = self._draft(cells)
        draft.name = name
        return self.repo.publish_draft(draft)

    def test_entries_to_csv_bytes_where_two_columns_should_write_both(self):
        # Arrange
        draft = self._draft({(self.ayah1.id, self.question): "Q", (self.ayah1.id, self.answer): "A"})

        # Act
        content = self.repo.entries_to_csv_bytes(draft, unit_spec_for(self.asset)).decode()

        # Assert
        lines = content.splitlines()
        self.assertEqual(lines[0], "surah,ayah,question,answer")
        self.assertEqual(lines[1], "1,1,Q,A")
        self.assertEqual(lines[2], "1,2,,")

    def test_publish_draft_where_two_columns_should_freeze_column_keys(self):
        # Arrange / Act
        committed = self._commit({(self.ayah1.id, self.question): "Q"}, "1.0")

        # Assert
        committed.refresh_from_db()
        self.assertEqual(committed.column_keys, ["question", "answer"])

    def test_record_changes_where_one_cell_modified_should_record_one_change_with_column(self):
        # Arrange
        self._commit({(self.ayah1.id, self.question): "Q", (self.ayah1.id, self.answer): "A"}, "1.0")

        # Act
        second = self._commit({(self.ayah1.id, self.question): "Q", (self.ayah1.id, self.answer): "A2"}, "1.1")

        # Assert
        changes = list(AssetVersionChange.objects.filter(version=second))
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].column.key, "answer")
        self.assertEqual((changes[0].old_text, changes[0].new_text), ("A", "A2"))

    def test_reconstruct_entries_where_pruned_version_should_rebuild_cells(self):
        # Arrange
        first = self._commit({(self.ayah1.id, self.question): "Q", (self.ayah1.id, self.answer): "A"}, "1.0")
        self._commit({(self.ayah1.id, self.question): "Q", (self.ayah1.id, self.answer): "A2"}, "1.1")
        self.assertFalse(first.entries.exists())  # pruned to its deltas

        # Act
        snapshot = self.repo.reconstruct_entries(first)

        # Assert
        self.assertEqual(snapshot, {(self.ayah1.id, "question"): "Q", (self.ayah1.id, "answer"): "A"})

    def test_version_diff_where_stored_changes_should_name_their_column(self):
        # Arrange
        committed = self._commit({(self.ayah1.id, self.answer): "A"}, "1.0")

        # Act
        diff = self.repo.version_diff(committed)

        # Assert
        self.assertEqual([(item["unit_id"], item["column"]) for item in diff], [(self.ayah1.id, "answer")])

    def test_diff_maps_where_two_cells_of_one_unit_should_order_by_column(self):
        # Arrange
        old = {}
        new = {(self.ayah1.id, "answer"): "A", (self.ayah1.id, "question"): "Q"}

        # Act
        diff = self.repo.diff_maps(unit_spec_for(self.asset), old, new, column_keys=["question", "answer"])

        # Assert
        self.assertEqual([item["column"] for item in diff], ["question", "answer"])

    def test_snapshot_to_csv_bytes_where_version_predates_new_column_should_use_its_own_keys(self):
        # Arrange
        first = self._commit({(self.ayah1.id, self.question): "Q", (self.ayah1.id, self.answer): "A"}, "1.0")
        extra = AssetColumn.objects.create(asset=self.asset, key="extra", order=2)
        second = self._commit(
            {(self.ayah1.id, self.question): "Q", (self.ayah1.id, self.answer): "A", (self.ayah1.id, extra): "E"},
            "1.1",
        )
        spec = unit_spec_for(self.asset)

        # Act
        old_csv = self.repo.snapshot_to_csv_bytes(
            self.repo.reconstruct_entries(first), spec, asset=self.asset, column_keys=first.resolved_column_keys
        ).decode()
        new_csv = self.repo.entries_to_csv_bytes(second, spec).decode()

        # Assert
        self.assertEqual(old_csv.splitlines()[0], "surah,ayah,question,answer")
        self.assertEqual(new_csv.splitlines()[0], "surah,ayah,question,answer,extra")
        self.assertEqual(new_csv.splitlines()[1], "1,1,Q,A,E")

    def test_restore_version_where_old_version_lacks_new_column_should_use_current_keys_with_blank(self):
        # Arrange
        first = self._commit({(self.ayah1.id, self.question): "Q", (self.ayah1.id, self.answer): "A"}, "1.0")
        extra = AssetColumn.objects.create(asset=self.asset, key="extra", order=2)
        self._commit({(self.ayah1.id, self.question): "Q2", (self.ayah1.id, extra): "E"}, "1.1")

        # Act
        restored = self.repo.restore_version(first, name="1.2")

        # Assert
        restored.refresh_from_db()
        self.assertEqual(restored.column_keys, ["question", "answer", "extra"])
        lines = restored.file_url.open("rb").read().decode().splitlines()
        self.assertEqual(lines[0], "surah,ayah,question,answer,extra")
        self.assertEqual(lines[1], "1,1,Q,A,")

    def test_create_draft_seeded_from_where_translation_of_two_column_asset_should_seed_row_per_ayah_and_column(self):
        # Arrange
        source = self._commit({(self.ayah1.id, self.question): "Q", (self.ayah2.id, self.answer): "A"}, "1.0")
        english = AssetLanguage.objects.create(asset=self.asset, language="en")

        # Act
        draft = self.repo.create_draft_seeded_from(
            self.asset,
            None,
            asset_language=english,
            name="",
            text=_empty_text(),
            created_by_id=None,
            mushaf_version=source,
        )

        # Assert
        cells = set(draft.entries.values_list("ayah_id", "column__key", "text"))
        self.assertEqual(
            cells,
            {
                (self.ayah1.id, "question", ""),
                (self.ayah1.id, "answer", ""),
                (self.ayah2.id, "question", ""),
                (self.ayah2.id, "answer", ""),
            },
        )

    def test_upsert_entries_where_rows_name_columns_should_write_each_cell(self):
        # Arrange
        draft = self._draft({})

        # Act
        self.repo.upsert_entries(
            draft,
            unit_spec_for(self.asset),
            [
                {"unit_id": self.ayah1.id, "column": "answer", "text": "A"},
                {"unit_id": self.ayah1.id, "text": "Q"},
            ],
        )

        # Assert
        self.assertEqual(set(draft.entries.values_list("column__key", "text")), {("answer", "A"), ("question", "Q")})

    def test_ensure_entries_where_pruned_version_should_rebuild_cells_per_column(self):
        # Arrange
        first = self._commit({(self.ayah1.id, self.question): "Q", (self.ayah1.id, self.answer): "A"}, "1.0")
        self._commit({(self.ayah1.id, self.question): "Q2", (self.ayah1.id, self.answer): "A"}, "1.1")

        # Act
        self.repo.ensure_entries(first)

        # Assert
        self.assertEqual(set(first.entries.values_list("column__key", "text")), {("question", "Q"), ("answer", "A")})


def _empty_text():
    from apps.content.version_text import VersionText

    return VersionText.of(None)
