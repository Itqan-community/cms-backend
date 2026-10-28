from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_content import AssetContentService, source_group_keys
from apps.content.services.asset_content_import import AssetContentParseError, parse_content_file
from apps.content.services.asset_templates import (
    ColumnFilter,
    EntryFilters,
    QuranPosition,
    TextCondition,
    unit_spec_for,
)
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.content.unit_keys import encode_group_key
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class GroupReviewFixTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_group_quran()
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
            template=AssetTemplateChoice.AYAH_GROUP,
            language="ar",
            slug="grouped",
        )
        self.source = self.asset.get_or_create_source_language()
        self.english = AssetLanguage.objects.create(asset=self.asset, language="en")
        self.column = self.asset.ensure_text_columns()[0]
        self.service = AssetContentService()

    def _version(self, language: AssetLanguage, groups: dict, *, state=VersionStateChoice.PUBLISHED, name="1.0"):
        version = baker.make(AssetVersion, asset=self.asset, asset_language=language, state=state, name=name)
        for (start, end), text in groups.items():
            AssetVersionEntry.objects.create(
                version=version, column=self.column, text=text, order=start, from_ayah_id=start, to_ayah_id=end
            )
        return version

    def test_parse_content_file_where_word_group_file_uploaded_to_ayah_group_should_raise(self):
        # Arrange
        raw = b"from_surah,from_ayah,from_word,to_surah,to_ayah,to_word,text\n1,1,1,1,1,2,x\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(raw, unit_spec_for(self.asset), self.asset)

    def test_source_group_keys_where_translation_should_not_select_entry_text(self):
        # Arrange
        self._version(self.source, {(1, 3): "long source text", (4, 5): "more"})
        draft = self._version(self.english, {}, state=VersionStateChoice.DRAFT, name="")

        # Act
        with CaptureQueriesContext(connection) as queries:
            keys = source_group_keys(draft)

        # Assert
        self.assertEqual(keys, {encode_group_key(1, 3), encode_group_key(4, 5)})
        entry_selects = [
            q["sql"].split(" FROM ")[0] for q in queries.captured_queries if "content_assetversionentry" in q["sql"]
        ]
        self.assertTrue(entry_selects)
        self.assertFalse(any('"text"' in select for select in entry_selects))

    def test_restore_version_where_translation_holds_orphaned_range_should_raise(self):
        # Arrange — the old translation covers 1:1→1:3; the source now has only 2:1→2:2
        old = self._version(self.english, {(1, 3): "en"}, name="1.0")
        self._version(self.english, {(4, 5): "en two"}, name="1.1")
        self._version(self.source, {(4, 5): "src"})

        # Act
        with self.assertRaises(ItqanError) as raised:
            self.service.restore_version(self.asset.slug, CategoryChoice.TAFSIR, old.pk)

        # Assert
        self.assertEqual(raised.exception.error_name, "orphaned_groups")

    def test_restore_version_where_source_language_should_reconstruct_snapshot_once(self):
        # Arrange — the orphan check does not apply to the source, so only the restore reads it
        old = self._version(self.source, {(1, 3): "src"}, name="1.0")
        self._version(self.source, {(4, 5): "src two"}, name="1.1")
        repo = AssetContentRepository()

        # Act
        with patch.object(repo, repo.reconstruct_entries.__name__, wraps=repo.reconstruct_entries) as reconstruct:
            AssetContentService(repo).restore_version(self.asset.slug, CategoryChoice.TAFSIR, old.pk)

        # Assert
        self.assertEqual([call.args[0] for call in reconstruct.call_args_list].count(old), 1)

    def test_restore_version_where_translation_passes_orphan_check_should_reconstruct_snapshot_once(self):
        # Arrange — the check's snapshot is reused by the restore
        self._version(self.source, {(1, 3): "src"})
        old = self._version(self.english, {(1, 3): "en"}, name="1.0")
        self._version(self.english, {(1, 3): "en two"}, name="1.1")
        repo = AssetContentRepository()

        # Act
        with patch.object(repo, repo.reconstruct_entries.__name__, wraps=repo.reconstruct_entries) as reconstruct:
            AssetContentService(repo).restore_version(self.asset.slug, CategoryChoice.TAFSIR, old.pk)

        # Assert
        self.assertEqual([call.args[0] for call in reconstruct.call_args_list].count(old), 1)

    def test_add_group_where_version_committed_after_check_should_raise_not_editable(self):
        # Arrange — the draft is committed between the editable check and the row lock
        draft = self._version(self.source, {}, state=VersionStateChoice.DRAFT, name="")
        AssetVersion.objects.filter(pk=draft.pk).update(state=VersionStateChoice.PUBLISHED)
        draft.state = VersionStateChoice.DRAFT

        # Act
        with (
            patch.object(
                AssetContentService, AssetContentService._get_editable_draft_or_400.__name__, return_value=draft
            ),
            self.assertRaises(ItqanError) as raised,
        ):
            self.service.add_group(
                self.asset.slug,
                CategoryChoice.TAFSIR,
                draft.pk,
                start=QuranPosition(1, 1),
                end=QuranPosition(1, 2),
                cells={"text": "x"},
            )

        # Assert
        self.assertEqual(raised.exception.error_name, "version_not_editable")
        self.assertFalse(AssetVersionEntry.objects.filter(version=draft).exists())

    def test_publish_draft_where_source_moves_group_before_lock_should_raise_orphaned(self):
        # Arrange — the source drops 1:1→1:3 while the translation commit waits for the lock
        self._version(self.source, {(1, 3): "src"})
        draft = self._version(self.english, {(1, 3): "en"}, state=VersionStateChoice.DRAFT, name="")
        AssetVersion.objects.filter(pk=draft.pk).update(content_edited=True)
        repo = AssetContentRepository()
        real_lock = repo.lock_asset

        def lock_then_source_commit(asset: Asset) -> Asset:
            locked = real_lock(asset)
            if not AssetVersion.objects.filter(asset=asset, asset_language=self.source, name="2.0").exists():
                self._version(self.source, {(4, 5): "moved"}, name="2.0")
            return locked

        # Act
        with (
            patch.object(repo, repo.lock_asset.__name__, side_effect=lock_then_source_commit),
            self.assertRaises(ItqanError) as raised,
        ):
            AssetContentService(repo).publish_draft(
                self.asset.slug, CategoryChoice.TAFSIR, draft.pk, summary_en="commit", version_number="1.0"
            )

        # Assert
        self.assertEqual(raised.exception.error_name, "orphaned_groups")

    def test_units_page_where_reference_filter_matches_a_later_word_should_keep_group(self):
        # Arrange
        asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, status=StatusChoice.READY, template=AssetTemplateChoice.WORD_GROUP
        )
        column = asset.ensure_text_columns()[0]
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.PUBLISHED)
        AssetVersionEntry.objects.create(
            version=version, column=column, text="t", order=3, from_word_id=3, to_word_id=4
        )
        filters = EntryFilters(reference_text=ColumnFilter(conditions=(TextCondition("contains", "w4"),)))

        # Act
        rows, total = unit_spec_for(asset).units_page(asset, offset=0, limit=10, filters=filters, version=version)

        # Assert
        self.assertEqual(total, 1)
        self.assertEqual(rows[0].unit_id, encode_group_key(3, 4))

    def test_range_fields_where_declared_should_not_add_plain_fk_indexes(self):
        # Arrange
        models = (AssetVersionEntry, AssetVersionChange)

        # Act
        indexed = [
            f"{model.__name__}.{name}"
            for model in models
            for name in ("from_ayah", "to_ayah", "from_word", "to_word")
            if model._meta.get_field(name).db_index
        ]
        unconditional_range_uniques = [
            constraint.name
            for model in models
            for constraint in model._meta.constraints
            if "range_column" in constraint.name and getattr(constraint, "condition", None) is None
        ]

        # Assert
        self.assertEqual(indexed, [])
        self.assertEqual(unconditional_range_uniques, [])
