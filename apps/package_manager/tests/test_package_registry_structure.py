"""`structure` on the package catalog and on resolve: what the itqan CLI describes in the manifest."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetColumn,
    AssetTemplateChoice,
    AssetVersion,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.tests.publishing import publish
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher


class PackageStructureTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher")

    def _asset(self, slug: str, category: str = "tafsir", columns: list[tuple[str, str, str]] | None = None) -> Asset:
        asset = Asset.objects.create(
            name=slug.title(),
            slug=slug,
            publisher=self.publisher,
            category=category,
            template=AssetTemplateChoice.AYAH if category in ("tafsir", "translation") else None,
            license="CC0",
            file_size="1 MB",
            format="csv",
            description="desc",
            language="ar",
            status=StatusChoice.READY,
        )
        for order, (key, label_en, label_ar) in enumerate(columns or []):
            AssetColumn.objects.create(asset=asset, key=key, label_en=label_en, label_ar=label_ar, order=order)
        return asset

    def _version(self, asset: Asset, name: str) -> AssetVersion:
        keys = [column.key for column in asset.text_columns()]
        version = baker.make(
            AssetVersion,
            asset=asset,
            asset_language=asset.get_or_create_source_language(),
            name=name,
            state=VersionStateChoice.PUBLISHED,
            column_keys=keys,
        )
        publish(version)
        version.file_url = SimpleUploadedFile(name=f"{asset.slug}-{name}.csv", content=b"x")
        version.save()
        return version

    def _qa(self, slug: str = "qa") -> Asset:
        return self._asset(slug, columns=[("question", "Question", "السؤال"), ("answer", "Answer", "الجواب")])

    def test_list_packages_where_two_column_tafsir_should_expose_structure(self):
        # Arrange
        self._version(self._qa(), "1.0")

        # Act
        response = self.client.get("/packages/")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        structure = response.json()["results"][0]["languages"][0]["structure"]
        self.assertEqual(
            structure,
            {
                "template": "ayah",
                "header": ["surah", "ayah", "question", "answer"],
                "columns": [
                    {"key": "question", "label_en": "Question", "label_ar": "السؤال"},
                    {"key": "answer", "label_en": "Answer", "label_ar": "الجواب"},
                ],
            },
        )

    def test_list_packages_where_latest_version_predates_new_column_should_describe_latest(self):
        # Arrange
        asset = self._qa()
        self._version(asset, "1.0")
        AssetColumn.objects.create(asset=asset, key="extra", order=2)

        # Act
        response = self.client.get("/packages/")

        # Assert
        structure = response.json()["results"][0]["languages"][0]["structure"]
        self.assertEqual(structure["header"], ["surah", "ayah", "question", "answer"])

    def test_resolve_package_manifest_where_two_column_tafsir_should_expose_structure(self):
        # Arrange
        self._version(self._qa(), "1.0")

        # Act
        response = self.client.post(
            "/packages/resolve/manifest/", data={"assets": {"qa": "^1.0"}}, content_type="application/json"
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["results"][0]
        self.assertEqual(result["structure"]["header"], ["surah", "ayah", "question", "answer"])

    def test_list_packages_where_mushaf_should_have_no_structure(self):
        # Arrange
        self._version(self._asset("mushaf", category="mushaf"), "1.0")

        # Act
        response = self.client.get("/packages/")

        # Assert
        self.assertIsNone(response.json()["results"][0]["languages"][0]["structure"])

    def test_list_packages_where_more_assets_should_not_add_structure_queries_per_asset(self):
        # Arrange
        self._version(self._qa("qa-0"), "1.0")
        with CaptureQueriesContext(connection) as one:
            self.client.get("/packages/")
        for index in range(1, 5):
            self._version(self._qa(f"qa-{index}"), "1.0")

        # Act
        with CaptureQueriesContext(connection) as five:
            self.client.get("/packages/")

        # Assert — the catalog already costs a few queries per asset; structure must add none
        per_asset_before = len(one.captured_queries)
        self.assertLessEqual(len(five.captured_queries), per_asset_before * 5)
        structure_queries = [q for q in five.captured_queries if "content_assetcolumn" in q["sql"]]
        self.assertLessEqual(len(structure_queries), 1)
