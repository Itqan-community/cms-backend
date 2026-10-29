from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.columns import validate_column_key
from apps.content.models import (
    Asset,
    AssetColumn,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_templates import unit_spec_for, unit_spec_for_template
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class GroupCsvExportTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_group_quran()
        self.repo = AssetContentRepository()

    def _version(self, template: str, groups: dict, *, keys: tuple[str, ...] = ("text",)) -> AssetVersion:
        asset = baker.make(Asset, category=CategoryChoice.TAFSIR, status=StatusChoice.READY, template=template)
        for order, key in enumerate(keys):
            baker.make(AssetColumn, asset=asset, key=key, order=order)
        columns = {column.key: column for column in asset.ensure_text_columns()}
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.PUBLISHED)
        prefix = "ayah" if template == AssetTemplateChoice.AYAH_GROUP else "word"
        for (start, end, *key), text in groups.items():
            AssetVersionEntry.objects.create(
                version=version,
                column=columns[key[0] if key else keys[0]],
                text=text,
                order=start,
                **{f"from_{prefix}_id": start, f"to_{prefix}_id": end},
            )
        return version

    def _lines(self, version: AssetVersion, *, verbose: bool = False) -> list[str]:
        content = self.repo.entries_to_csv_bytes(version, unit_spec_for(version.asset), verbose=verbose)
        return content.decode("utf-8").splitlines()

    def test_entries_to_csv_bytes_where_ayah_group_should_write_range_rows_sorted(self):
        # Arrange
        version = self._version(AssetTemplateChoice.AYAH_GROUP, {(4, 5): "c", (1, 3): "a", (1, 1): "b"})

        # Act
        lines = self._lines(version)

        # Assert
        self.assertEqual(
            lines,
            ["from_surah,from_ayah,to_surah,to_ayah,text", "1,1,1,1,b", "1,1,1,3,a", "2,1,2,2,c"],
        )

    def test_entries_to_csv_bytes_where_word_group_verbose_should_add_reference_text(self):
        # Arrange
        version = self._version(AssetTemplateChoice.WORD_GROUP, {(3, 4): "x"})

        # Act
        lines = self._lines(version, verbose=True)

        # Assert
        self.assertEqual(
            lines,
            [
                "from_surah,from_ayah,from_word,to_surah,to_ayah,to_word,reference_text,text",
                "1,1,3,1,2,1,w3 w4,x",
            ],
        )

    def test_blank_template_csv_bytes_where_group_template_should_return_header_only(self):
        # Arrange
        spec = unit_spec_for_template(AssetTemplateChoice.AYAH_GROUP)

        # Act
        content = self.repo.blank_template_csv_bytes(spec, page_count=None)

        # Assert
        self.assertEqual(
            content.decode("utf-8").splitlines(), ["from_surah,from_ayah,to_surah,to_ayah,reference_text,text"]
        )

    def test_entries_to_csv_bytes_where_multi_column_group_should_write_each_column(self):
        # Arrange
        version = self._version(
            AssetTemplateChoice.AYAH_GROUP,
            {(1, 3, "question"): "q", (1, 3, "answer"): "a", (4, 4, "answer"): "only"},
            keys=("question", "answer"),
        )
        version.column_keys = ["question", "answer"]

        # Act
        lines = self._lines(version)

        # Assert
        self.assertEqual(
            lines,
            ["from_surah,from_ayah,to_surah,to_ayah,question,answer", "1,1,1,3,q,a", "2,1,2,1,,only"],
        )

    def test_validate_column_key_where_key_is_reference_text_should_raise(self):
        # Arrange / Act / Assert
        with self.assertRaises(ItqanError):
            validate_column_key("reference_text")

    def test_entries_to_csv_bytes_where_many_groups_should_use_constant_queries(self):
        # Arrange
        small = self._version(AssetTemplateChoice.WORD_GROUP, {(1, 2): "a"})
        large = self._version(
            AssetTemplateChoice.WORD_GROUP, {(start, end): "t" for start in range(1, 9) for end in range(start, 9)}
        )

        # Act
        with CaptureQueriesContext(connection) as small_queries:
            self._lines(small, verbose=True)
        with CaptureQueriesContext(connection) as large_queries:
            lines = self._lines(large, verbose=True)

        # Assert
        self.assertEqual(len(lines), 37)
        self.assertEqual(len(large_queries), len(small_queries))
