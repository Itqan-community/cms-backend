from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.services.asset_templates import (
    REFERENCE_TEXT_LIMIT,
    ColumnFilter,
    EntryFilters,
    TextCondition,
    unit_spec_for,
)
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.content.unit_keys import encode_group_key
from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah


class GroupUnitSpecTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_group_quran()

    def _asset(self, template: str) -> Asset:
        return baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
            template=template,
            language="ar",
        )

    def _version(self, asset: Asset, groups: dict, *, language: AssetLanguage | None = None) -> AssetVersion:
        """A published version whose entries are ``{(from, to): text}`` (or ``{(from, to, key): text}``)."""
        version = baker.make(AssetVersion, asset=asset, asset_language=language, state=VersionStateChoice.PUBLISHED)
        columns = {column.key: column for column in asset.ensure_text_columns()}
        prefix = "ayah" if asset.template == AssetTemplateChoice.AYAH_GROUP else "word"
        for unit, text in groups.items():
            start, end, *key = unit
            AssetVersionEntry.objects.create(
                version=version,
                column=columns[key[0] if key else "text"],
                text=text,
                order=start,
                **{f"from_{prefix}_id": start, f"to_{prefix}_id": end},
            )
        return version

    def test_units_page_where_ayah_group_source_should_list_stored_ranges_in_order(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH_GROUP)
        version = self._version(asset, {(1, 3): "x", (1, 1): "y", (4, 5): "z"})

        # Act
        rows, total = unit_spec_for(asset).units_page(asset, offset=0, limit=10, version=version)

        # Assert
        self.assertEqual([row.label for row in rows], ["1:1", "1:1 → 1:3", "2:1 → 2:2"])
        self.assertEqual([row.unit_id for row in rows], [1_000_001, 1_000_003, 4_000_005])
        self.assertEqual(total, 3)

    def test_units_page_where_group_has_two_columns_should_list_range_once(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH_GROUP)
        baker.make("content.AssetColumn", asset=asset, key="text", order=0)
        baker.make("content.AssetColumn", asset=asset, key="notes", order=1)
        version = self._version(asset, {(1, 3, "text"): "x", (1, 3, "notes"): "n"})

        # Act
        rows, total = unit_spec_for(asset).units_page(asset, offset=0, limit=10, version=version)

        # Assert
        self.assertEqual([row.unit_id for row in rows], [encode_group_key(1, 3)])
        self.assertEqual(total, 1)

    def test_units_page_where_translation_should_list_source_ranges_and_flag_orphans(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH_GROUP)
        source = self._version(asset, {(1, 3): "src"})
        english = baker.make(AssetLanguage, asset=asset, language="en", is_source=False)
        translation = self._version(asset, {(1, 3): "en", (4, 4): "old"}, language=english)

        # Act
        rows, total = unit_spec_for(asset).units_page(
            asset, offset=0, limit=10, version=translation, source_version=source
        )

        # Assert
        self.assertEqual(
            [(row.unit_id, row.orphaned) for row in rows],
            [(encode_group_key(1, 3), False), (encode_group_key(4, 4), True)],
        )
        self.assertEqual(total, 2)

    def test_units_page_where_word_group_crosses_ayah_should_join_reference_text(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.WORD_GROUP)
        version = self._version(asset, {(3, 4): "x"})

        # Act
        rows, _total = unit_spec_for(asset).units_page(asset, offset=0, limit=10, version=version)

        # Assert
        row = rows[0]
        self.assertEqual(row.reference_text, "w3 w4")
        self.assertEqual(row.label, "1:1:3 → 1:2:1")
        self.assertEqual(row.group_from, (1, 1, 3))
        self.assertEqual(row.group_to, (1, 2, 1))
        self.assertEqual((row.surah, row.ayah), (1, 1))

    def test_units_page_where_reference_text_long_should_truncate_to_limit(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH_GROUP)
        Ayah.objects.filter(id__in=[1, 2]).update(text="ب" * REFERENCE_TEXT_LIMIT)
        version = self._version(asset, {(1, 2): "x"})

        # Act
        rows, _total = unit_spec_for(asset).units_page(asset, offset=0, limit=10, version=version)

        # Assert
        self.assertEqual(len(rows[0].reference_text), REFERENCE_TEXT_LIMIT + 1)
        self.assertTrue(rows[0].reference_text.endswith("…"))

    def test_units_page_where_surah_filter_should_match_from_position(self):
        # Arrange — 1:3 → 2:1 starts in surah 1
        asset = self._asset(AssetTemplateChoice.AYAH_GROUP)
        version = self._version(asset, {(3, 4): "x"})
        spec = unit_spec_for(asset)

        # Act
        in_one, _ = spec.units_page(asset, offset=0, limit=10, surah=1, version=version)
        in_two, _ = spec.units_page(asset, offset=0, limit=10, surah=2, version=version)

        # Assert
        self.assertEqual(len(in_one), 1)
        self.assertEqual(in_two, [])

    def test_units_page_where_cell_filter_should_filter_before_paging(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH_GROUP)
        version = self._version(asset, {(1, 1): "apple", (2, 2): "pear", (3, 3): "apple pie"})
        filters = EntryFilters(cells={"text": ColumnFilter(conditions=(TextCondition("contains", "apple"),))})

        # Act
        rows, total = unit_spec_for(asset).units_page(asset, offset=1, limit=1, filters=filters, version=version)

        # Assert
        self.assertEqual(total, 2)
        self.assertEqual([row.unit_id for row in rows], [encode_group_key(3, 3)])

    def test_units_page_where_page_of_groups_should_use_constant_queries(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.WORD_GROUP)
        small = self._version(asset, {(1, 2): "a", (3, 4): "b"})
        large = self._version(asset, {(start, end): "t" for start in range(1, 9) for end in range(start, 9)})
        spec = unit_spec_for(asset)

        # Act
        with CaptureQueriesContext(connection) as small_queries:
            spec.units_page(asset, offset=0, limit=50, version=small)
        with CaptureQueriesContext(connection) as large_queries:
            rows, _ = spec.units_page(asset, offset=0, limit=50, version=large)

        # Assert
        self.assertEqual(len(rows), 36)
        self.assertEqual(len(large_queries), len(small_queries))

    def test_valid_unit_ids_where_group_candidates_should_reject_missing_and_reversed(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH_GROUP)
        candidates = [encode_group_key(1, 3), encode_group_key(3, 1), encode_group_key(1, 99)]

        # Act
        valid = unit_spec_for(asset).valid_unit_ids(asset, candidates)

        # Assert
        self.assertEqual(valid, {encode_group_key(1, 3)})

    def test_unit_columns_where_group_key_should_return_range_kwargs(self):
        # Arrange
        spec = unit_spec_for(self._asset(AssetTemplateChoice.WORD_GROUP))

        # Act
        columns = spec.unit_columns(encode_group_key(6, 7))

        # Assert
        self.assertEqual(columns, {"from_word_id": 6, "to_word_id": 7})

    def test_entries_q_where_group_keys_should_match_only_those_ranges(self):
        # Arrange
        asset = self._asset(AssetTemplateChoice.AYAH_GROUP)
        version = self._version(asset, {(1, 3): "a", (1, 1): "b", (4, 5): "c"})
        spec = unit_spec_for(asset)

        # Act
        matched = version.entries.filter(spec.entries_q([encode_group_key(1, 3), encode_group_key(4, 5)]))

        # Assert
        self.assertEqual(sorted(entry.text for entry in matched), ["a", "c"])

    def test_order_for_where_group_key_should_return_from_id(self):
        # Arrange
        spec = unit_spec_for(self._asset(AssetTemplateChoice.WORD_GROUP))

        # Act
        order = spec.order_for(encode_group_key(77_000, 77_431))

        # Assert
        self.assertEqual(order, 77_000)
