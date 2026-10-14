"""`package` on the gallery's asset detail: what the CMS shows for `itqan add`."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import Asset, AssetLanguage, CategoryChoice, StatusChoice
from apps.content.tests.publishing import publish
from apps.package_manager.tests.test_package_registry_withdrawal import WithdrawalBaseTest


class DetailAssetPackageTest(WithdrawalBaseTest):
    def _detail(self, asset: Asset) -> dict:
        response = self.client.get(f"/cms-api/assets/{asset.id}/", format="json")
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    def test_detail_assets_where_asset_installable_should_return_slug_and_languages(self):
        # Arrange
        self._commit("1.0.0", asset=self.mushaf)

        # Act
        body = self._detail(self.mushaf)

        # Assert
        self.assertEqual({"slug": "m1", "languages": [{"language": "ar", "is_source": True}]}, body["package"])

    def test_detail_assets_where_only_a_translation_is_published_should_list_only_that_language(self):
        # Arrange
        publish(self._commit("1.0"))

        # Act
        body = self._detail(self.asset)

        # Assert
        self.assertEqual({"slug": "t1", "languages": [{"language": "fr", "is_source": False}]}, body["package"])

    def test_detail_assets_where_asset_has_no_installable_version_should_return_null_package(self):
        # Act
        body = self._detail(self.mushaf)

        # Assert
        self.assertIsNone(body["package"])

    def test_detail_assets_where_recitation_should_return_null_package(self):
        # Arrange
        recitation = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=True,
            slug="r1",
            reciter=baker.make("content.Reciter", name="Reciter"),
            riwayah=baker.make("content.Riwayah", name="Riwayah"),
        )

        # Act
        body = self._detail(recitation)

        # Assert
        self.assertIsNone(body["package"])

    def test_detail_assets_where_asset_not_ready_should_return_null_package(self):
        # Arrange
        self._commit("1.0.0", asset=self.mushaf)
        Asset.objects.filter(pk=self.mushaf.pk).update(status=StatusChoice.DRAFT)

        # Act
        body = self._detail(self.mushaf)

        # Assert
        self.assertIsNone(body["package"])

    def test_detail_assets_where_published_version_removed_should_fall_back_to_older_released_version(self):
        # Arrange
        self._commit("1.0.0", asset=self.mushaf)
        self._remove(self._commit("1.1.0", asset=self.mushaf))

        # Act
        body = self._detail(self.mushaf)

        # Assert
        self.assertEqual({"slug": "m1", "languages": [{"language": "ar", "is_source": True}]}, body["package"])

    def test_detail_assets_where_only_version_removed_should_return_null_package(self):
        # Arrange
        self._remove(self._commit("1.0.0", asset=self.mushaf))

        # Act
        body = self._detail(self.mushaf)

        # Assert
        self.assertIsNone(body["package"])

    def test_detail_assets_where_more_languages_should_not_run_more_queries(self):
        # Arrange
        publish(self._commit("1.0"))
        with CaptureQueriesContext(connection) as one_language:
            self._detail(self.asset)
        self.fr = AssetLanguage.objects.create(asset=self.asset, language="de", status=StatusChoice.READY)
        publish(self._commit("1.0"))

        # Act
        with CaptureQueriesContext(connection) as two_languages:
            body = self._detail(self.asset)

        # Assert
        self.assertEqual(["de", "fr"], sorted(lang["language"] for lang in body["package"]["languages"]))
        self.assertEqual(len(one_language.captured_queries), len(two_languages.captured_queries))
