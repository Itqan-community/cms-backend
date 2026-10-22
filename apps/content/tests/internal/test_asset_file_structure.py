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
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.tests.base import BaseTestCase


class AssetFileStructureTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.AYAH,
            status=StatusChoice.READY,
            language="ar",
            restricted_for_tenant=False,
            is_open_access=False,
        )
        self.url = f"/cms-api/assets/{self.asset.id}/file-structure/"

    def _publish(self, keys: list[str], cells: dict, language: AssetLanguage | None = None) -> AssetVersion:
        rendition = language or self.asset.get_or_create_source_language()
        version = baker.make(
            AssetVersion,
            asset=self.asset,
            asset_language=rendition,
            state=VersionStateChoice.PUBLISHED,
            column_keys=keys,
            name="1.0",
        )
        for (ayah, column), text in cells.items():
            AssetVersionEntry.objects.create(version=version, ayah=ayah, column=column, text=text, order=ayah.id)
        rendition.published_version = version
        rendition.status = StatusChoice.READY
        rendition.save()
        return version

    def test_file_structure_where_two_columns_published_should_return_header_labels_and_rows(self):
        # Arrange
        question = AssetColumn.objects.create(asset=self.asset, key="question", order=0, label_en="Question")
        answer = AssetColumn.objects.create(asset=self.asset, key="answer", order=1, label_ar="الجواب")
        self._publish(
            ["question", "answer"],
            {
                (self.ayah1, question): "Q",
                (self.ayah1, answer): "A",
                (self.ayah2, answer): "A2",
                (self.ayah3, question): "Q3",
            },
        )

        # Act — anonymous: no access grant is needed
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["format"], "csv")
        self.assertEqual(body["template"], "ayah")
        self.assertEqual(body["header"], ["surah", "ayah", "question", "answer"])
        self.assertEqual(
            body["columns"],
            [
                {"key": "question", "label_en": "Question", "label_ar": ""},
                {"key": "answer", "label_en": "", "label_ar": "الجواب"},
            ],
        )
        self.assertEqual(body["rows"], [["1", "1", "Q", "A"], ["1", "2", "", "A2"], ["2", "1", "Q3", ""]])

    def test_file_structure_where_served_version_was_pruned_should_rebuild_its_rows(self):
        # Arrange
        question = AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        rendition = self.asset.get_or_create_source_language()
        repo = AssetContentRepository()
        committed = []
        for name, text in (("1.0", "old"), ("1.1", "new")):
            draft = baker.make(
                AssetVersion,
                asset=self.asset,
                asset_language=rendition,
                state=VersionStateChoice.DRAFT,
                content_edited=True,
                name=name,
            )
            AssetVersionEntry.objects.create(version=draft, ayah=self.ayah1, column=question, text=text, order=1)
            committed.append(repo.publish_draft(draft))
        first = committed[0]
        self.assertFalse(first.entries.exists())  # pruned to its deltas
        rendition.published_version = first  # rolled back
        rendition.status = StatusChoice.READY
        rendition.save()

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["rows"], [["1", "1", "old"]])

    def test_file_structure_where_more_than_three_rows_should_cap_at_three(self):
        # Arrange
        column = self.asset.ensure_text_columns()[0]
        extra_ayah = baker.make(
            "quran.Ayah", id=4, sura=self.sura2, number_in_sura=2, text="ayah 4", juz=1, hizb_quarter=1, page=2
        )
        self._publish(
            ["text"],
            {(ayah, column): f"t{ayah.id}" for ayah in (self.ayah1, self.ayah2, self.ayah3, extra_ayah)},
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(len(response.json()["rows"]), 3)

    def test_file_structure_where_single_column_should_report_text_header(self):
        # Arrange
        column = self.asset.ensure_text_columns()[0]
        self._publish(["text"], {(self.ayah1, column): "t"})

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.json()["header"], ["surah", "ayah", "text"])

    def test_file_structure_where_language_is_draft_should_return_404(self):
        # Arrange
        column = self.asset.ensure_text_columns()[0]
        self._publish(["text"], {(self.ayah1, column): "t"})
        english = AssetLanguage.objects.create(asset=self.asset, language="en", status=StatusChoice.DRAFT)

        # Act
        response = self.client.get(f"{self.url}?language={english.language}")

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "file_structure_unavailable")

    def test_file_structure_where_mushaf_should_return_404(self):
        # Arrange
        mushaf = baker.make(Asset, category=CategoryChoice.MUSHAF, status=StatusChoice.READY)

        # Act
        response = self.client.get(f"/cms-api/assets/{mushaf.id}/file-structure/")

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "file_structure_unavailable")

    def test_file_structure_where_published_should_stay_within_query_budget(self):
        # Arrange
        column = self.asset.ensure_text_columns()[0]
        self._publish(["text"], {(self.ayah1, column): "t"})

        # Act / Assert
        with self.assertNumQueries(6):
            self.client.get(self.url)
