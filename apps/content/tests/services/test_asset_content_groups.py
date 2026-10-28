from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    ChangeTypeChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_templates import unit_spec_for
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.content.unit_keys import encode_group_key
from apps.content.version_text import VersionText
from apps.core.tests.base import BaseTestCase


class GroupContentRepositoryTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_group_quran()
        self.repo = AssetContentRepository()
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
            template=AssetTemplateChoice.AYAH_GROUP,
            language="ar",
            slug="group-tafsir",
        )
        self.column = self.asset.ensure_text_columns()[0]
        self.versions = 0

    def _draft(self, groups: dict[tuple[int, int], str]) -> AssetVersion:
        draft = baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.DRAFT)
        for (start, end), text in groups.items():
            AssetVersionEntry.objects.create(
                version=draft, column=self.column, text=text, order=start, from_ayah_id=start, to_ayah_id=end
            )
        return draft

    def _commit(self, groups: dict[tuple[int, int], str]) -> AssetVersion:
        draft = self._draft(groups)
        self.versions += 1
        draft.name = f"{self.versions}.0"
        return self.repo.publish_draft(draft)

    @staticmethod
    def _changes(version: AssetVersion) -> set[tuple[str, int, int, str, str]]:
        return set(version.changes.values_list("change_type", "from_ayah_id", "to_ayah_id", "old_text", "new_text"))

    def test_publish_draft_where_group_text_changed_should_record_modified(self):
        # Arrange
        self._commit({(1, 3): "t"})

        # Act
        committed = self._commit({(1, 3): "u"})

        # Assert
        self.assertEqual(self._changes(committed), {(ChangeTypeChoice.MODIFIED, 1, 3, "t", "u")})

    def test_publish_draft_where_group_range_moved_should_record_removed_and_added(self):
        # Arrange
        self._commit({(1, 3): "t"})

        # Act
        committed = self._commit({(1, 2): "t"})

        # Assert
        self.assertEqual(
            self._changes(committed),
            {(ChangeTypeChoice.REMOVED, 1, 3, "t", ""), (ChangeTypeChoice.ADDED, 1, 2, "", "t")},
        )

    def test_publish_draft_where_two_groups_start_at_same_ayah_should_record_both_added(self):
        # Arrange — no earlier version

        # Act
        committed = self._commit({(1, 3): "long", (1, 1): "short"})

        # Assert
        self.assertEqual(
            self._changes(committed),
            {(ChangeTypeChoice.ADDED, 1, 3, "", "long"), (ChangeTypeChoice.ADDED, 1, 1, "", "short")},
        )

    def test_publish_draft_where_last_text_cleared_should_record_removed(self):
        # Arrange
        self._commit({(1, 3): "t", (4, 5): "keep"})

        # Act
        committed = self._commit({(1, 3): "", (4, 5): "keep"})

        # Assert
        self.assertEqual(self._changes(committed), {(ChangeTypeChoice.REMOVED, 1, 3, "t", "")})
        self.assertFalse(committed.entries.filter(from_ayah_id=1, to_ayah_id=3).exists())

    def test_reconstruct_entries_where_group_version_pruned_should_rebuild_ranges(self):
        # Arrange
        first = self._commit({(1, 3): "a"})
        self._commit({(1, 3): "b", (4, 5): "c"})
        first.refresh_from_db()

        # Act
        snapshot = self.repo.reconstruct_entries(first)

        # Assert
        self.assertFalse(first.entries.exists())
        self.assertEqual(snapshot, {(encode_group_key(1, 3), "text"): "a"})

    def test_restore_version_where_group_asset_should_restore_ranges(self):
        # Arrange
        first = self._commit({(1, 3): "a", (1, 1): "b"})
        self._commit({(4, 5): "c"})

        # Act
        restored = self.repo.restore_version(first, name="3.0")

        # Assert
        self.assertEqual(
            set(restored.entries.values_list("from_ayah_id", "to_ayah_id", "text")), {(1, 3, "a"), (1, 1, "b")}
        )
        self.assertEqual(
            self._changes(restored),
            {
                (ChangeTypeChoice.ADDED, 1, 3, "", "a"),
                (ChangeTypeChoice.ADDED, 1, 1, "", "b"),
                (ChangeTypeChoice.REMOVED, 4, 5, "c", ""),
            },
        )

    def test_create_draft_seeded_from_where_group_head_should_copy_ranges(self):
        # Arrange
        head = self._commit({(1, 3): "a", (4, 4): "b"})

        # Act
        draft = self.repo.create_draft_seeded_from(
            self.asset,
            head,
            asset_language=self.asset.get_or_create_source_language(),
            name="",
            text=VersionText.of(head),
            created_by_id=None,
        )

        # Assert
        self.assertEqual(
            set(draft.entries.values_list("from_ayah_id", "to_ayah_id", "text", "order")),
            {(1, 3, "a", 1), (4, 4, "b", 4)},
        )

    def test_version_diff_where_group_changes_should_label_ranges(self):
        # Arrange
        committed = self._commit({(1, 3): "a", (4, 4): "b"})

        # Act
        diff = self.repo.version_diff(committed)

        # Assert
        self.assertEqual(
            [(row["label"], row["unit_id"], row["unit_type"]) for row in diff],
            [("1:1 → 1:3", encode_group_key(1, 3), "ayah_group"), ("2:1", encode_group_key(4, 4), "ayah_group")],
        )

    def test_upsert_entries_where_existing_group_cell_should_update_not_duplicate(self):
        # Arrange
        draft = self._draft({(1, 3): "old"})
        spec = unit_spec_for(self.asset)

        # Act
        self.repo.upsert_entries(draft, spec, [{"unit_id": encode_group_key(1, 3), "column": "text", "text": "new"}])

        # Assert
        self.assertEqual(list(draft.entries.values_list("from_ayah_id", "to_ayah_id", "text")), [(1, 3, "new")])
        self.assertTrue(AssetVersion.objects.get(pk=draft.pk).content_edited)

    def test_upsert_entries_where_new_group_should_store_range_and_start_order(self):
        # Arrange
        draft = self._draft({})
        spec = unit_spec_for(self.asset)

        # Act
        self.repo.upsert_entries(draft, spec, [{"unit_id": encode_group_key(4, 5), "text": "x"}])

        # Assert
        self.assertEqual(list(draft.entries.values_list("from_ayah_id", "to_ayah_id", "order")), [(4, 5, 4)])
