import json
from urllib.parse import quote

from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    MushafLayout,
    StatusChoice,
)
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah
from apps.users.models import User


def _filters(model: dict) -> str:
    """The `filters` query param carrying an AG Grid filter model."""
    return "filters=" + quote(json.dumps(model))


class EntriesEnumerationTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

    def _draft_for(self, template, layout=None):
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=template,
            mushaf_layout=layout,
        )
        version = baker.make(AssetVersion, asset=asset)
        return asset, version

    def test_list_entries_where_surah_asset_is_empty_should_return_baked_sura_rows(self):
        # Arrange — QuranDataMixin bakes 2 suras (see module docstring)
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=200"
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(len(body["results"]), 2)
        self.assertTrue(all(item["text"] == "" for item in body["results"]))
        self.assertEqual(AssetVersionEntry.objects.filter(version=version).count(), 0)

    def test_list_entries_where_surah_asset_has_one_entry_should_overlay_its_text(self):
        # Arrange
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)
        AssetVersionEntry.objects.create(version=version, sura_id=self.sura2.id, text="content", order=2)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=200"
        )

        # Assert
        items = {item["unit_id"]: item["text"] for item in response.json()["results"]}
        self.assertEqual(items[self.sura2.id], "content")
        self.assertEqual(items[self.sura1.id], "")

    def test_list_entries_where_page_asset_should_return_layout_page_count_rows(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset, version = self._draft_for(AssetTemplateChoice.PAGE, layout=layout)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=5"
        )

        # Assert
        body = response.json()
        self.assertEqual(body["count"], 604)
        self.assertEqual([item["unit_id"] for item in body["results"]], [1, 2, 3, 4, 5])
        self.assertEqual(body["results"][0]["unit_type"], "page")

    def test_list_entries_where_word_asset_filtered_by_sura_should_narrow_the_count(self):
        # Arrange — 2 words baked, both in sura 1 (see QuranDataMixin docstring)
        asset, version = self._draft_for(AssetTemplateChoice.WORD)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=10&sura=1"
        )

        # Assert
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertTrue(all(item["sura"] == 1 for item in body["results"]))

    def test_list_entries_where_ayah_asset_should_return_baked_ayah_rows(self):
        # Arrange — 3 ayahs baked, not the canonical 6236 (see QuranDataMixin docstring)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=1"
        )

        # Assert
        body = response.json()
        self.assertEqual(body["count"], 3)
        self.assertEqual(body["results"][0]["label"], "1:1")

    def test_list_entries_where_page_is_zero_should_return_400(self):
        # Arrange — the hand-rolled page/page_size params must keep the same
        # lower bound NinjaPagination.Input enforced (page: int = Field(1, ge=1)),
        # otherwise offset goes negative and QuerySet slicing 500s instead. This
        # project's global handler turns every ninja validation error into 400
        # (apps.core.ninja_utils.error_handling.handle_ninja_validation_error),
        # not django-ninja's library default of 422 — confirmed empirically
        # against an existing @paginate endpoint (.../diff/?page=0) before
        # writing this assertion.
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)

        # Act
        response = self.client.get(f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page=0")

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "validation_error")

    def test_list_entries_where_page_two_should_return_the_second_slice(self):
        # Arrange — a 604-page layout gives enough rows to prove page 2 is not
        # page 1 again (the classic off-by-one risk of a hand-rolled offset).
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset, version = self._draft_for(AssetTemplateChoice.PAGE, layout=layout)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page=2&page_size=5"
        )

        # Assert
        body = response.json()
        self.assertEqual(body["count"], 604)
        self.assertEqual([item["unit_id"] for item in body["results"]], [6, 7, 8, 9, 10])


class EntriesFilterTests(QuranDataMixin, BaseTestCase):
    """Column filters on the entries endpoint, applied across the whole asset (not one page)."""

    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.user = User.objects.create_user(email="filter@example.com", name="Editor", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

    def _draft_for(self, template, layout=None):
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=template,
            mushaf_layout=layout,
        )
        version = baker.make(AssetVersion, asset=asset)
        return asset, version

    def _list(self, asset, version, query):
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=50&{query}"
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        return body["count"], [item["unit_id"] for item in body["results"]]

    def test_list_entries_where_text_contains_should_match_case_insensitively(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, text="The Mercy", order=1)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah2, text="other", order=2)

        # Act
        count, unit_ids = self._list(
            asset,
            version,
            _filters({"text": {"filterType": "text", "type": "contains", "filter": "mercy"}}),
        )

        # Assert
        self.assertEqual(count, 1)
        self.assertEqual(unit_ids, [self.ayah1.id])

    def test_list_entries_where_text_not_contains_should_include_units_without_entries(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, text="mercy", order=1)

        # Act
        count, unit_ids = self._list(
            asset,
            version,
            _filters({"text": {"filterType": "text", "type": "notContains", "filter": "mercy"}}),
        )

        # Assert
        self.assertEqual(count, 2)
        self.assertEqual(unit_ids, [self.ayah2.id, self.ayah3.id])

    def test_list_entries_where_text_blank_should_return_empty_and_missing_units(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, text="done", order=1)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah2, text="", order=2)

        # Act
        count, unit_ids = self._list(asset, version, _filters({"text": {"filterType": "text", "type": "blank"}}))

        # Assert
        self.assertEqual(count, 2)
        self.assertEqual(unit_ids, [self.ayah2.id, self.ayah3.id])

    def test_list_entries_where_reference_text_starts_with_should_filter_the_quran_text(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        count, unit_ids = self._list(
            asset,
            version,
            _filters({"reference_text": {"filterType": "text", "type": "startsWith", "filter": "AYAH 3"}}),
        )

        # Assert
        self.assertEqual(count, 1)
        self.assertEqual(unit_ids, [self.ayah3.id])

    def test_list_entries_where_aya_equals_should_match_the_number_in_every_sura(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        count, unit_ids = self._list(
            asset,
            version,
            _filters({"aya": {"filterType": "number", "type": "equals", "filter": 1}}),
        )

        # Assert
        self.assertEqual(count, 2)
        self.assertEqual(unit_ids, [self.ayah1.id, self.ayah3.id])

    def test_list_entries_where_aya_in_range_should_include_both_ends(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        count, unit_ids = self._list(
            asset,
            version,
            "sura=1&" + _filters({"aya": {"filterType": "number", "type": "inRange", "filter": 2, "filterTo": 2}}),
        )

        # Assert
        self.assertEqual(count, 1)
        self.assertEqual(unit_ids, [self.ayah2.id])

    def test_list_entries_where_word_aya_greater_than_should_filter_by_the_parent_ayah(self):
        # Arrange — both baked words sit in ayah 1
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.WORD)

        # Act
        count, _unit_ids = self._list(
            asset,
            version,
            _filters({"aya": {"filterType": "number", "type": "greaterThan", "filter": 1}}),
        )

        # Assert
        self.assertEqual(count, 0)

    def test_list_entries_where_page_text_contains_should_filter_pages(self):
        # Arrange
        self.authenticate_user(self.user)
        layout = baker.make(MushafLayout, name="Small", page_count=5)
        asset, version = self._draft_for(AssetTemplateChoice.PAGE, layout=layout)
        AssetVersionEntry.objects.create(version=version, page_no=3, text="Hello page", order=3)

        # Act
        count, unit_ids = self._list(
            asset,
            version,
            _filters({"text": {"filterType": "text", "type": "contains", "filter": "hello"}}),
        )

        # Assert
        self.assertEqual(count, 1)
        self.assertEqual(unit_ids, [3])

    def test_list_entries_where_page_text_not_blank_and_offset_should_slice_the_filtered_pages(self):
        # Arrange
        self.authenticate_user(self.user)
        layout = baker.make(MushafLayout, name="Small", page_count=5)
        asset, version = self._draft_for(AssetTemplateChoice.PAGE, layout=layout)
        for page_no in (2, 4, 5):
            AssetVersionEntry.objects.create(version=version, page_no=page_no, text="x", order=page_no)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/"
            "?page=2&page_size=2&" + _filters({"text": {"filterType": "text", "type": "notBlank"}})
        )

        # Assert
        body = response.json()
        self.assertEqual(body["count"], 3)
        self.assertEqual([item["unit_id"] for item in body["results"]], [5])

    def test_list_entries_where_text_type_is_unknown_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?"
            + _filters({"text": {"filterType": "text", "type": "regex", "filter": "a"}})
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "validation_error")

    def test_list_entries_where_text_has_two_conditions_joined_by_or_should_match_either(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, text="alpha", order=1)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah2, text="beta", order=2)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah3, text="gamma", order=3)
        query = _filters(
            {
                "text": {
                    "filterType": "text",
                    "operator": "OR",
                    "conditions": [
                        {"filterType": "text", "type": "equals", "filter": "alpha"},
                        {"filterType": "text", "type": "equals", "filter": "gamma"},
                    ],
                }
            }
        )

        # Act
        count, unit_ids = self._list(asset, version, query)

        # Assert
        self.assertEqual(count, 2)
        self.assertEqual(unit_ids, [self.ayah1.id, self.ayah3.id])

    def test_list_entries_where_sura_column_filter_equals_should_keep_that_surah(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        count, unit_ids = self._list(
            asset,
            version,
            _filters({"sura": {"filterType": "number", "type": "equals", "filter": 2}}),
        )

        # Assert
        self.assertEqual(count, 1)
        self.assertEqual(unit_ids, [self.ayah3.id])

    def test_list_entries_where_filter_column_is_unknown_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?"
            + _filters({"label": {"filterType": "text", "type": "contains", "filter": "1"}})
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "validation_error")

    def test_list_entries_where_in_range_has_no_upper_bound_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?"
            + _filters({"aya": {"filterType": "number", "type": "inRange", "filter": 1}})
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "validation_error")

    def test_list_entries_where_surah_dropdown_and_sura_number_filter_should_both_apply(self):
        # Arrange — the dropdown keeps sura 1, the number filter keeps sura >= 2
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)
        query = _filters(
            {
                "surah": {"filterType": "number", "type": "equals", "filter": 1},
                "sura": {"filterType": "number", "type": "greaterThanOrEqual", "filter": 2},
            }
        )

        # Act
        count, unit_ids = self._list(asset, version, query)

        # Assert
        self.assertEqual(count, 0)
        self.assertEqual(unit_ids, [])

    def test_list_entries_where_surah_dropdown_selects_a_surah_should_keep_its_ayahs(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        count, unit_ids = self._list(
            asset, version, _filters({"surah": {"filterType": "number", "type": "equals", "filter": 1}})
        )

        # Assert
        self.assertEqual(count, 2)
        self.assertEqual(unit_ids, [self.ayah1.id, self.ayah2.id])

    def test_list_entries_where_reference_text_is_uthmani_should_match_plain_arabic(self):
        # Arrange — Uthmani text carries harakat, Quranic marks, alef wasla and a
        # dagger alef (ٱلۡعَٰلَمِينَ) where plain spelling writes a full alef (العالمين)
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)
        Ayah.objects.filter(id=self.ayah2.id).update(text="ٱلۡحَمۡدُ لِلَّهِ رَبِّ ٱلۡعَٰلَمِينَ")

        # Act
        contains = self._list(
            asset,
            version,
            _filters({"reference_text": {"filterType": "text", "type": "contains", "filter": "العالمين"}}),
        )
        starts = self._list(
            asset,
            version,
            _filters({"reference_text": {"filterType": "text", "type": "startsWith", "filter": "الحمد"}}),
        )

        # Assert
        self.assertEqual(contains, (1, [self.ayah2.id]))
        self.assertEqual(starts, (1, [self.ayah2.id]))

    def test_list_entries_where_text_filter_has_regex_characters_should_match_them_literally(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, text="see (note 1.2)", order=1)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah2, text="see note 1x2", order=2)

        # Act
        count, unit_ids = self._list(
            asset, version, _filters({"text": {"filterType": "text", "type": "contains", "filter": "(note 1.2"}})
        )

        # Assert
        self.assertEqual(count, 1)
        self.assertEqual(unit_ids, [self.ayah1.id])

    def test_list_entries_where_page_text_is_vocalized_should_match_plain_arabic(self):
        # Arrange
        self.authenticate_user(self.user)
        layout = baker.make(MushafLayout, name="Small", page_count=3)
        asset, version = self._draft_for(AssetTemplateChoice.PAGE, layout=layout)
        AssetVersionEntry.objects.create(version=version, page_no=2, text="ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ", order=2)

        # Act
        count, unit_ids = self._list(
            asset, version, _filters({"text": {"filterType": "text", "type": "equals", "filter": "الرحمن الرحيم"}})
        )

        # Assert
        self.assertEqual(count, 1)
        self.assertEqual(unit_ids, [2])
