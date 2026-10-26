from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
)
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.content.unit_keys import encode_group_key
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class GroupInlineEditingApiTests(GroupQuranDataMixin, BaseTestCase):
    """Editing groups from the grid itself: blank rows, "add next", grow / shrink."""

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

    def _draft(self, groups: dict[tuple[int, int], str], *, asset: Asset | None = None) -> int:
        """A source draft (opened through the API) holding the given ranges."""
        asset = asset or self.asset
        response = self.client.post(
            f"/portal/content/tafsirs/{asset.slug}/draft/", data={"language": "ar"}, content_type="application/json"
        )
        draft_id = response.json()["id"]
        column = asset.ensure_text_columns()[0]
        prefix = "ayah" if asset.template == AssetTemplateChoice.AYAH_GROUP else "word"
        for (start, end), text in groups.items():
            AssetVersionEntry.objects.create(
                version_id=draft_id,
                column=column,
                text=text,
                order=start,
                **{f"from_{prefix}_id": start, f"to_{prefix}_id": end},
            )
        return draft_id

    def _url(self, draft_id: int, tail: str, *, asset: Asset | None = None) -> str:
        return f"/portal/content/tafsirs/{(asset or self.asset).slug}/versions/{draft_id}/{tail}"

    def _ranges(self, draft_id: int) -> set[tuple[int, int, str]]:
        return set(
            AssetVersionEntry.objects.filter(version_id=draft_id).values_list("from_ayah_id", "to_ayah_id", "text")
        )

    def test_add_group_where_all_cells_blank_should_store_a_blank_row(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft({})

        # Act
        response = self.client.post(
            self._url(draft_id, "groups/"),
            data={"start": {"surah": 1, "ayah": 1}, "end": {"surah": 1, "ayah": 2}, "cells": {}},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()[0]["label"], "1:1 → 1:2")
        self.assertEqual(self._ranges(draft_id), {(1, 2, "")})

    def test_publish_draft_where_blank_group_never_filled_should_drop_it(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft({(1, 1): "kept", (2, 3): ""})
        AssetVersion.objects.filter(pk=draft_id).update(content_edited=True)

        # Act
        response = self.client.post(
            self._url(draft_id, "publish/"),
            data={"summary_en": "commit", "version_number": "1.0"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._ranges(draft_id), {(1, 1, "kept")})

    def test_append_group_where_no_groups_should_start_at_the_first_ayah(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft({})

        # Act
        response = self.client.post(self._url(draft_id, "groups/next/"))

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()[0]["unit_id"], encode_group_key(1, 1))
        self.assertEqual(self._ranges(draft_id), {(1, 1, "")})

    def test_append_group_where_groups_exist_should_start_after_the_furthest_end(self):
        # Arrange — 1:1→1:3 reaches furthest even though 1:2 starts later
        self.authenticate_user(self.user)
        draft_id = self._draft({(1, 3): "a", (2, 2): "b"})

        # Act
        response = self.client.post(self._url(draft_id, "groups/next/"))

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()[0]["label"], "2:1")
        self.assertIn((4, 4, ""), self._ranges(draft_id))

    def test_append_group_where_word_group_should_add_the_next_word(self):
        # Arrange — words 1-3 are 1:1, word 4 is 1:2:1
        self.authenticate_user(self.user)
        asset = self._asset(AssetTemplateChoice.WORD_GROUP, slug="words")
        draft_id = self._draft({(1, 3): "a"}, asset=asset)

        # Act
        response = self.client.post(self._url(draft_id, "groups/next/", asset=asset))

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()[0]["label"], "1:2:1")

    def test_append_group_where_last_unit_is_covered_should_return_400(self):
        # Arrange — ayah 5 is the last baked ayah
        self.authenticate_user(self.user)
        draft_id = self._draft({(4, 5): "a"})

        # Act
        response = self.client.post(self._url(draft_id, "groups/next/"))

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_range_invalid")

    def test_append_group_where_translated_language_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        AssetLanguage.objects.create(asset=self.asset, language="en")
        response = self.client.post(
            f"/portal/content/tafsirs/{self.asset.slug}/draft/",
            data={"language": "en"},
            content_type="application/json",
        )
        draft_id = response.json()["id"]

        # Act
        response = self.client.post(self._url(draft_id, "groups/next/"))

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_ranges_source_only")

    def test_extend_group_where_grown_should_move_the_end_across_a_surah(self):
        # Arrange — ayah 3 is 1:3, ayah 4 is 2:1
        self.authenticate_user(self.user)
        draft_id = self._draft({(1, 3): "t"})

        # Act
        response = self.client.post(
            self._url(draft_id, f"groups/{encode_group_key(1, 3)}/extend/"),
            data={"by": 1},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()[0]["label"], "1:1 → 2:1")
        self.assertEqual(self._ranges(draft_id), {(1, 4, "t")})

    def test_extend_group_where_shrunk_should_move_the_end_back(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft({(1, 3): "t"})

        # Act
        response = self.client.post(
            self._url(draft_id, f"groups/{encode_group_key(1, 3)}/extend/"),
            data={"by": -1},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._ranges(draft_id), {(1, 2, "t")})

    def test_extend_group_where_shrunk_below_its_start_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft({(2, 2): "t"})

        # Act
        response = self.client.post(
            self._url(draft_id, f"groups/{encode_group_key(2, 2)}/extend/"),
            data={"by": -1},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_range_invalid")

    def test_extend_group_where_grown_onto_an_existing_range_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft({(1, 2): "a", (1, 3): "b"})

        # Act
        response = self.client.post(
            self._url(draft_id, f"groups/{encode_group_key(1, 2)}/extend/"),
            data={"by": 1},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_exists")

    def test_extend_group_where_grown_past_the_last_ayah_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft({(4, 5): "t"})

        # Act
        response = self.client.post(
            self._url(draft_id, f"groups/{encode_group_key(4, 5)}/extend/"),
            data={"by": 1},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_range_invalid")

    def test_extend_group_where_by_is_not_one_step_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_id = self._draft({(1, 3): "t"})

        # Act
        response = self.client.post(
            self._url(draft_id, f"groups/{encode_group_key(1, 3)}/extend/"),
            data={"by": 5},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "validation_error")
