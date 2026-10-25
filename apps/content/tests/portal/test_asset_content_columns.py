import json
from urllib.parse import quote

from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetColumn,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


def _filters(model: dict) -> str:
    return "filters=" + quote(json.dumps(model))


class MultiColumnEditorApiTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.user = User.objects.create_user(email="qa@example.com", name="Editor", is_staff=True)
        for permission in (
            PermissionChoice.PORTAL_READ_TAFSIR,
            PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT,
            PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES,
        ):
            self.give_permission(self.user, permission)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.AYAH,
            status=StatusChoice.READY,
            language="ar",
        )
        self.question = AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        self.answer = AssetColumn.objects.create(asset=self.asset, key="answer", order=1)
        self.source = self.asset.get_or_create_source_language()
        self.draft = baker.make(
            AssetVersion, asset=self.asset, asset_language=self.source, state=VersionStateChoice.DRAFT
        )
        self.base = f"/portal/content/tafsirs/{self.asset.slug}/versions/{self.draft.id}/"

    def _rows(self, response) -> dict[int, dict]:
        return {row["unit_id"]: row for row in response.json()["results"]}

    def test_list_entries_where_two_columns_should_return_cells_per_column(self):
        # Arrange
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah1, column=self.question, text="Q")
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{self.base}entries/?page_size=10")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        rows = self._rows(response)
        self.assertEqual(rows[self.ayah1.id]["cells"], {"question": "Q", "answer": ""})
        self.assertEqual(rows[self.ayah1.id]["text"], "Q")
        self.assertEqual(rows[self.ayah2.id]["cells"], {"question": "", "answer": ""})

    def test_list_entries_where_committed_version_had_fewer_columns_should_use_its_own_keys(self):
        # Arrange
        old = baker.make(
            AssetVersion,
            asset=self.asset,
            asset_language=self.source,
            state=VersionStateChoice.PUBLISHED,
            column_keys=["question"],
        )
        AssetVersionEntry.objects.create(version=old, ayah=self.ayah1, column=self.question, text="Q")
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"/portal/content/tafsirs/{self.asset.slug}/versions/{old.id}/entries/?page_size=10")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._rows(response)[self.ayah1.id]["cells"], {"question": "Q"})

    def test_list_entries_where_draft_cell_changed_should_name_its_column(self):
        # Arrange
        published = baker.make(
            AssetVersion,
            asset=self.asset,
            asset_language=self.source,
            state=VersionStateChoice.PUBLISHED,
            column_keys=["question", "answer"],
        )
        AssetVersionEntry.objects.create(version=published, ayah=self.ayah1, column=self.question, text="Q")
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah1, column=self.question, text="Q")
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah1, column=self.answer, text="A")
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{self.base}entries/?page_size=10")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        row = self._rows(response)[self.ayah1.id]
        self.assertTrue(row["changed"])
        self.assertEqual(row["changed_columns"], ["answer"])
        self.assertEqual(self._rows(response)[self.ayah2.id]["changed_columns"], [])

    def test_patch_entries_where_row_names_answer_column_should_store_it_there(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.patch(
            f"{self.base}entries/",
            data={"rows": [{"unit_id": self.ayah1.id, "column": "answer", "text": "A"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(list(self.draft.entries.values_list("column__key", "text")), [("answer", "A")])
        self.assertEqual(response.json()[0]["cells"], {"question": "", "answer": "A"})

    def test_patch_entries_where_unknown_column_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.patch(
            f"{self.base}entries/",
            data={"rows": [{"unit_id": self.ayah1.id, "column": "nope", "text": "x"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "unknown_column")

    def test_list_entries_where_cell_filter_on_answer_should_return_matching_rows(self):
        # Arrange
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah2, column=self.answer, text="Answer two")
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah1, column=self.question, text="Answer?")
        self.authenticate_user(self.user)
        model = {"cell__answer": {"filterType": "text", "type": "contains", "filter": "answer"}}

        # Act
        response = self.client.get(f"{self.base}entries/?page_size=10&{_filters(model)}")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(list(self._rows(response)), [self.ayah2.id])

    def test_list_entries_where_filter_names_unknown_column_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        model = {"cell__nope": {"filterType": "text", "type": "contains", "filter": "x"}}

        # Act
        response = self.client.get(f"{self.base}entries/?page_size=10&{_filters(model)}")

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "unknown_filter_column")

    def test_list_entries_where_text_filter_should_apply_to_first_column(self):
        # Arrange
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah1, column=self.question, text="needle")
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah2, column=self.answer, text="needle")
        self.authenticate_user(self.user)
        model = {"text": {"filterType": "text", "type": "contains", "filter": "needle"}}

        # Act
        response = self.client.get(f"{self.base}entries/?page_size=10&{_filters(model)}")

        # Assert
        self.assertEqual(list(self._rows(response)), [self.ayah1.id])

    def test_list_entries_where_translation_and_source_gained_column_should_read_empty_cells(self):
        # Arrange — the source was committed with two columns; `extra` came later
        committed = baker.make(
            AssetVersion,
            asset=self.asset,
            asset_language=self.source,
            state=VersionStateChoice.PUBLISHED,
            column_keys=["question", "answer"],
            name="1.0",
        )
        AssetVersionEntry.objects.create(version=committed, ayah=self.ayah1, column=self.question, text="Q")
        AssetColumn.objects.create(asset=self.asset, key="extra", order=2)
        english = AssetLanguage.objects.create(asset=self.asset, language="en")
        draft = baker.make(AssetVersion, asset=self.asset, asset_language=english, state=VersionStateChoice.DRAFT)
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"/portal/content/tafsirs/{self.asset.slug}/versions/{draft.id}/entries/")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        row = self._rows(response)[self.ayah1.id]
        self.assertEqual(row["source_cells"], {"question": "Q", "answer": "", "extra": ""})
        self.assertEqual(row["cells"], {"question": "", "answer": "", "extra": ""})
        self.assertEqual(row["source_text"], "Q")

    def test_list_entries_where_source_filter_on_column_should_filter_by_source_cells(self):
        # Arrange
        committed = baker.make(
            AssetVersion,
            asset=self.asset,
            asset_language=self.source,
            state=VersionStateChoice.PUBLISHED,
            column_keys=["question", "answer"],
            name="1.0",
        )
        AssetVersionEntry.objects.create(version=committed, ayah=self.ayah2, column=self.answer, text="hit")
        english = AssetLanguage.objects.create(asset=self.asset, language="en")
        draft = baker.make(AssetVersion, asset=self.asset, asset_language=english, state=VersionStateChoice.DRAFT)
        self.authenticate_user(self.user)
        model = {"source__answer": {"filterType": "text", "type": "contains", "filter": "hit"}}

        # Act
        response = self.client.get(
            f"/portal/content/tafsirs/{self.asset.slug}/versions/{draft.id}/entries/?{_filters(model)}"
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(list(self._rows(response)), [self.ayah2.id])

    def test_pending_diff_where_two_cells_edited_should_name_each_column(self):
        # Arrange
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah1, column=self.question, text="Q")
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah1, column=self.answer, text="A")
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{self.base}pending-diff/")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([item["column"] for item in response.json()["results"]], ["question", "answer"])

    def test_get_version_where_draft_should_report_live_column_keys(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(self.base)

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["column_keys"], ["question", "answer"])
        self.assertFalse(response.json()["requires_major"])

    def test_download_asset_csv_template_where_two_columns_should_list_both(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"/portal/content/tafsirs/{self.asset.slug}/csv-template/")

        # Assert
        self.assertEqual(response.status_code, 200)
        header = response.content.decode().splitlines()[0]
        self.assertEqual(header, "surah,ayah,surah_name,ayah_text,question,answer")

    def test_export_version_where_two_columns_should_write_both(self):
        # Arrange
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah1, column=self.answer, text="A")
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{self.base}export/")

        # Assert
        self.assertEqual(response.status_code, 200)
        lines = response.content.decode().splitlines()
        self.assertEqual(lines[0], "surah,ayah,surah_name,ayah_text,question,answer")
        self.assertEqual(lines[1], "1,1,الفاتحة,ayah 1,,A")

    def test_list_entries_where_more_columns_and_cells_should_not_add_queries(self):
        # Arrange
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah1, column=self.question, text="Q")
        self.authenticate_user(self.user)
        with CaptureQueriesContext(connection) as two_columns:
            self.client.get(f"{self.base}entries/?page_size=10")
        for order, key in enumerate(("hint", "source"), start=2):
            column = AssetColumn.objects.create(asset=self.asset, key=key, order=order)
            for ayah in (self.ayah1, self.ayah2, self.ayah3):
                AssetVersionEntry.objects.create(version=self.draft, ayah=ayah, column=column, text=key)

        # Act
        with CaptureQueriesContext(connection) as four_columns:
            response = self.client.get(f"{self.base}entries/?page_size=10")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(four_columns.captured_queries), len(two_columns.captured_queries))

    def _lookups(self, queries) -> tuple[int, int]:
        """How many queries loaded the asset (by slug or id), and the draft by id."""
        sqls = [query["sql"] for query in queries.captured_queries]
        asset = sum(
            1
            for sql in sqls
            if 'FROM "content_asset" ' in sql
            and (f"'{self.asset.slug}'" in sql or f'"content_asset"."id" = {self.asset.id} ' in sql)
        )
        draft = sum(
            1
            for sql in sqls
            if 'FROM "content_assetversion" ' in sql and f'"content_assetversion"."id" = {self.draft.id}' in sql
        )
        return asset, draft

    def test_list_entries_should_load_the_asset_and_version_once(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f"{self.base}entries/?page_size=10")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._lookups(queries), (1, 1))

    def test_pending_diff_should_load_the_asset_and_version_once(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f"{self.base}pending-diff/?page_size=1")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._lookups(queries), (1, 1))

    def test_patch_entries_where_more_cells_should_not_add_queries(self):
        # Arrange — each patch both updates existing cells and creates new ones
        AssetVersionEntry.objects.create(version=self.draft, ayah=self.ayah1, column=self.question, text="Q")
        self.authenticate_user(self.user)
        url = f"{self.base}entries/"

        def patch(cells):
            rows = [{"unit_id": ayah.id, "column": key, "text": f"{key} v2"} for ayah, key in cells]
            return self.client.patch(url, data={"rows": rows}, content_type="application/json")

        patch([(self.ayah1, "question")])  # the draft's first edit marks it edited, once
        with CaptureQueriesContext(connection) as two_cells:
            patch([(self.ayah1, "question"), (self.ayah1, "answer")])

        # Act
        with CaptureQueriesContext(connection) as six_cells:
            response = patch(
                [(ayah, key) for ayah in (self.ayah1, self.ayah2, self.ayah3) for key in ("question", "answer")]
            )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(six_cells.captured_queries), len(two_cells.captured_queries))
