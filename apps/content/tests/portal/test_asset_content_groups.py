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
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.content.unit_keys import encode_group_key
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class GroupContentApiTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_group_quran()
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        for permission in (
            PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT,
            PermissionChoice.PORTAL_READ_TAFSIR,
            PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES,
        ):
            self.give_permission(self.user, permission)
        self.asset = self._asset(AssetTemplateChoice.AYAH_GROUP)

    def _asset(self, template: str, slug: str = "grouped") -> Asset:
        asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
            template=template,
            language="ar",
            slug=slug,
        )
        asset.get_or_create_source_language()
        return asset

    def _head(self, groups: dict[tuple[int, int], str], *, asset: Asset | None = None) -> AssetVersion:
        """A committed source version with the given ayah ranges."""
        asset = asset or self.asset
        head = baker.make(
            AssetVersion,
            asset=asset,
            asset_language=asset.get_or_create_source_language(),
            state=VersionStateChoice.PUBLISHED,
            name="1.0",
        )
        column = asset.ensure_text_columns()[0]
        for (start, end), text in groups.items():
            AssetVersionEntry.objects.create(
                version=head, column=column, text=text, order=start, from_ayah_id=start, to_ayah_id=end
            )
        return head

    def _draft(self, language: str = "ar", *, asset: Asset | None = None) -> int:
        asset = asset or self.asset
        response = self.client.post(
            f"/portal/content/tafsirs/{asset.slug}/draft/", data={"language": language}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["id"]

    def _url(self, draft_id: int, tail: str = "groups/", *, asset: Asset | None = None) -> str:
        return f"/portal/content/tafsirs/{(asset or self.asset).slug}/versions/{draft_id}/{tail}"

    def _add(self, draft_id: int, start: dict, end: dict, cells: dict | None = None, **kwargs):
        return self.client.post(
            self._url(draft_id, **kwargs),
            data={"start": start, "end": end, "cells": cells if cells is not None else {"text": "t"}},
            content_type="application/json",
        )

    def _translation(self) -> int:
        AssetLanguage.objects.create(asset=self.asset, language="en")
        return self._draft("en")

    def test_add_group_where_source_draft_should_store_cells_and_return_row(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft()

        # Act
        response = self._add(draft_id, {"surah": 1, "ayah": 1}, {"surah": 1, "ayah": 3}, {"text": "commentary"})

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()[0]
        self.assertEqual(row["label"], "1:1 → 1:3")
        self.assertEqual(row["unit_id"], encode_group_key(1, 3))
        self.assertEqual(row["group_from"], {"surah": 1, "ayah": 1, "word": None})
        self.assertEqual(row["group_to"], {"surah": 1, "ayah": 3, "word": None})
        self.assertEqual(row["cells"], {"text": "commentary"})
        self.assertEqual(
            list(AssetVersionEntry.objects.filter(version_id=draft_id).values_list("from_ayah_id", "to_ayah_id")),
            [(1, 3)],
        )

    def test_add_group_where_range_exists_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft()
        self._add(draft_id, {"surah": 1, "ayah": 1}, {"surah": 1, "ayah": 3})

        # Act
        response = self._add(draft_id, {"surah": 1, "ayah": 1}, {"surah": 1, "ayah": 3})

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_exists")

    def test_add_group_where_end_before_start_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft()

        # Act
        response = self._add(draft_id, {"surah": 1, "ayah": 3}, {"surah": 1, "ayah": 1})

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_range_invalid")

    def test_add_group_where_all_cells_blank_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft()

        # Act
        response = self._add(draft_id, {"surah": 1, "ayah": 1}, {"surah": 1, "ayah": 1}, {"text": "  "})

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_text_required")

    def test_add_group_where_word_crosses_ayah_should_store(self):
        # Arrange
        self.authenticate_user(self.user)
        asset = self._asset(AssetTemplateChoice.WORD_GROUP, slug="words")
        draft_id = self._draft(asset=asset)

        # Act
        response = self._add(
            draft_id, {"surah": 1, "ayah": 1, "word": 3}, {"surah": 1, "ayah": 2, "word": 1}, asset=asset
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()[0]
        self.assertEqual(row["label"], "1:1:3 → 1:2:1")
        self.assertEqual(row["reference_text"], "w3 w4")

    def test_add_group_where_translated_language_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self._head({(1, 3): "src"})
        draft_id = self._translation()

        # Act
        response = self._add(draft_id, {"surah": 2, "ayah": 1}, {"surah": 2, "ayah": 2})

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_ranges_source_only")

    def test_add_group_where_single_unit_template_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        asset = self._asset(AssetTemplateChoice.AYAH, slug="plain")
        draft_id = self._draft(asset=asset)

        # Act
        response = self._add(draft_id, {"surah": 1, "ayah": 1}, {"surah": 1, "ayah": 1}, asset=asset)

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "template_not_grouped")

    def test_move_group_where_source_draft_should_move_every_column(self):
        # Arrange
        self.authenticate_user(self.user)
        baker.make("content.AssetColumn", asset=self.asset, key="text", order=0)
        baker.make("content.AssetColumn", asset=self.asset, key="notes", order=1)
        draft_id = self._draft()
        self._add(draft_id, {"surah": 1, "ayah": 1}, {"surah": 1, "ayah": 3}, {"text": "t", "notes": "n"})

        # Act
        response = self.client.put(
            self._url(draft_id, f"groups/{encode_group_key(1, 3)}/"),
            data={"start": {"surah": 1, "ayah": 2}, "end": {"surah": 2, "ayah": 1}},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()[0]["unit_id"], encode_group_key(2, 4))
        self.assertEqual(
            set(
                AssetVersionEntry.objects.filter(version_id=draft_id).values_list(
                    "from_ayah_id", "to_ayah_id", "column__key", "text", "order"
                )
            ),
            {(2, 4, "text", "t", 2), (2, 4, "notes", "n", 2)},
        )

    def test_move_group_where_unknown_key_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft()

        # Act
        response = self.client.put(
            self._url(draft_id, f"groups/{encode_group_key(1, 3)}/"),
            data={"start": {"surah": 1, "ayah": 1}, "end": {"surah": 1, "ayah": 2}},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(response.json()["error_name"], "group_not_found")

    def test_delete_group_where_source_draft_should_remove_cells(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft()
        self._add(draft_id, {"surah": 1, "ayah": 1}, {"surah": 1, "ayah": 3})
        self._add(draft_id, {"surah": 2, "ayah": 1}, {"surah": 2, "ayah": 1})

        # Act
        response = self.client.delete(self._url(draft_id, f"groups/{encode_group_key(1, 3)}/"))

        # Assert
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(
            list(AssetVersionEntry.objects.filter(version_id=draft_id).values_list("from_ayah_id", "to_ayah_id")),
            [(4, 4)],
        )
        self.assertTrue(AssetVersion.objects.get(pk=draft_id).content_edited)

    def test_delete_group_where_translation_orphan_should_remove(self):
        # Arrange
        self.authenticate_user(self.user)
        self._head({(1, 3): "src"})
        draft_id = self._translation()
        AssetVersionEntry.objects.create(
            version_id=draft_id,
            column=self.asset.ensure_text_columns()[0],
            text="stale",
            order=4,
            from_ayah_id=4,
            to_ayah_id=4,
        )

        # Act
        response = self.client.delete(self._url(draft_id, f"groups/{encode_group_key(4, 4)}/"))

        # Assert
        self.assertEqual(response.status_code, 204, response.content)
        self.assertFalse(AssetVersionEntry.objects.filter(version_id=draft_id, from_ayah_id=4).exists())

    def test_delete_group_where_translation_non_orphan_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self._head({(1, 3): "src"})
        draft_id = self._translation()
        self.client.patch(
            self._url(draft_id, "entries/"),
            data={"rows": [{"unit_id": encode_group_key(1, 3), "text": "en"}]},
            content_type="application/json",
        )

        # Act
        response = self.client.delete(self._url(draft_id, f"groups/{encode_group_key(1, 3)}/"))

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_ranges_source_only")

    def test_patch_entries_where_translation_range_not_in_source_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self._head({(1, 3): "src"})
        draft_id = self._translation()

        # Act
        response = self.client.patch(
            self._url(draft_id, "entries/"),
            data={"rows": [{"unit_id": encode_group_key(4, 5), "text": "en"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_not_in_source")

    def test_list_entries_where_translation_should_list_source_ranges_with_source_cells(self):
        # Arrange
        self.authenticate_user(self.user)
        self._head({(1, 3): "src", (4, 5): "src two"})
        draft_id = self._translation()
        self.client.patch(
            self._url(draft_id, "entries/"),
            data={"rows": [{"unit_id": encode_group_key(1, 3), "text": "en"}]},
            content_type="application/json",
        )
        AssetVersionEntry.objects.create(
            version_id=draft_id,
            column=self.asset.ensure_text_columns()[0],
            text="stale",
            order=2,
            from_ayah_id=2,
            to_ayah_id=2,
        )

        # Act
        response = self.client.get(self._url(draft_id, "entries/"))

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()["results"]
        self.assertEqual(
            [(row["label"], row["text"], row["source_text"], row["orphaned"]) for row in rows],
            [
                ("1:1 → 1:3", "en", "src", False),
                ("1:2", "stale", None, True),
                ("2:1 → 2:2", "", "src two", False),
            ],
        )

    def test_publish_draft_where_translation_has_orphan_text_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self._head({(4, 5): "src"})
        draft_id = self._translation()
        AssetVersionEntry.objects.create(
            version_id=draft_id,
            column=self.asset.ensure_text_columns()[0],
            text="stale",
            order=1,
            from_ayah_id=1,
            to_ayah_id=3,
        )
        AssetVersion.objects.filter(pk=draft_id).update(content_edited=True)

        # Act
        response = self.client.post(
            self._url(draft_id, "publish/"),
            data={"summary_en": "commit", "version_number": "1.0"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        body = response.json()
        self.assertEqual(body["error_name"], "orphaned_groups")
        self.assertEqual(body["extra"]["groups"], ["1:1 → 1:3"])

    def test_list_entries_where_group_draft_cell_cleared_should_still_list_row(self):
        # Arrange
        self.authenticate_user(self.user)
        self._head({(1, 3): "src"})
        draft_id = self._draft()
        self.client.patch(
            self._url(draft_id, "entries/"),
            data={"rows": [{"unit_id": encode_group_key(1, 3), "text": ""}]},
            content_type="application/json",
        )

        # Act
        response = self.client.get(self._url(draft_id, "entries/"))

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()["results"]
        self.assertEqual([(row["label"], row["text"], row["changed"]) for row in rows], [("1:1 → 1:3", "", True)])

    def test_list_entries_where_groups_page_should_use_constant_queries(self):
        # Arrange
        self.authenticate_user(self.user)
        small = self._head({(1, 2): "a"})
        url_small = self._url(small.id, "entries/")
        with CaptureQueriesContext(connection) as few:
            self.client.get(url_small)
        large = self._head({(start, end): "t" for start in range(1, 6) for end in range(start, 6)})

        # Act
        with CaptureQueriesContext(connection) as many:
            response = self.client.get(self._url(large.id, "entries/"))

        # Assert
        self.assertEqual(response.json()["count"], 15)
        self.assertEqual(len(many), len(few))
