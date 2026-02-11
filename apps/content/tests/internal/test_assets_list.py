from model_bakery import baker

from apps.content.models import Asset, LicenseChoice, Resource
from apps.core.tests import BaseTestCase


class ListAssetTest(BaseTestCase):
    def test_list_asset_should_return_all_available_assets(self):
        # Arrange
        baker.make(Asset, name="Tafsir Ibn Katheer", category=Resource.CategoryChoice.TAFSIR)

        # Act
        response = self.client.get("/cms-api/assets/", format="json")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Tafsir Ibn Katheer", response_body["results"][0]["name"])

    def test_list_asset_filter_by_license_code_should_return_filtered_assets(self):
        # Arrange
        baker.make(
            Asset, name="Tafsir Al-Jalalayn", license=LicenseChoice.CC_BY_SA, category=Resource.CategoryChoice.TAFSIR
        )
        baker.make(
            Asset, name="Tafsir Ibn Katheer", license=LicenseChoice.CC_BY_NC, category=Resource.CategoryChoice.TAFSIR
        )

        # Act
        response = self.client.get("/cms-api/assets/", data={"license_code": LicenseChoice.CC_BY_SA}, format="json")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Tafsir Al-Jalalayn", response_body["results"][0]["name"])

    def test_list_asset_filter_by_category_should_return_filtered_assets(self):
        # Arrange
        baker.make(Asset, name="Tafsir Al-Jalalayn", category=Resource.CategoryChoice.TAFSIR)
        baker.make(
            Asset,
            name="Muhammad Refaat",
            category=Resource.CategoryChoice.RECITATION,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )

        # Act
        response = self.client.get(
            "/cms-api/assets/",
            data={"category": Resource.CategoryChoice.RECITATION},
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Muhammad Refaat", response_body["results"][0]["name"])

    def test_list_asset_filter_by_multiple_categories_should_return_filtered_assets(
        self,
    ):
        # Arrange
        baker.make(Asset, name="Tafsir Al-Jalalayn", category=Resource.CategoryChoice.TAFSIR)
        baker.make(
            Asset,
            name="Muhammad Refaat",
            category=Resource.CategoryChoice.RECITATION,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )
        baker.make(Asset, name="King Fahd", category=Resource.CategoryChoice.MUSHAF)

        # Act
        response = self.client.get(
            f"/cms-api/assets/?category={Resource.CategoryChoice.RECITATION}&category={Resource.CategoryChoice.TAFSIR}",
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(2, len(response_body["results"]))
        # self.assertEqual("Muhammad Refaat", response_body['results'][0]['name'])

    def test_list_order_by_name_descending_should_return_sorted_assets(self):
        # Arrange
        baker.make(Asset, name="A", category=Resource.CategoryChoice.TAFSIR)
        baker.make(Asset, name="C", category=Resource.CategoryChoice.TAFSIR)
        baker.make(Asset, name="B", category=Resource.CategoryChoice.TAFSIR)

        # Act
        response = self.client.get("/cms-api/assets/", data={"ordering": "-name"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(3, len(response_body["results"]))
        self.assertEqual("C", response_body["results"][0]["name"])
        self.assertEqual("B", response_body["results"][1]["name"])
        self.assertEqual("A", response_body["results"][2]["name"])

    def test_list_order_by_name_ascending_should_return_sorted_assets(self):
        # Arrange
        baker.make(Asset, name="A", category=Resource.CategoryChoice.TAFSIR)
        baker.make(Asset, name="C", category=Resource.CategoryChoice.TAFSIR)
        baker.make(Asset, name="B", category=Resource.CategoryChoice.TAFSIR)

        # Act
        response = self.client.get("/cms-api/assets/", data={"ordering": "name"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(3, len(response_body["results"]))
        self.assertEqual("A", response_body["results"][0]["name"])
        self.assertEqual("B", response_body["results"][1]["name"])
        self.assertEqual("C", response_body["results"][2]["name"])

    def test_list_assets_order_by_category_descending_should_return_sorted_assets(self):
        # Arrange
        baker.make(Asset, name="A", category=Resource.CategoryChoice.TAFSIR)
        baker.make(
            Asset,
            name="C",
            category=Resource.CategoryChoice.RECITATION,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )
        baker.make(Asset, name="B", category=Resource.CategoryChoice.TAFSIR)

        # Act
        response = self.client.get("/cms-api/assets/", data={"ordering": "-category"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(3, len(response_body["results"]))
        self.assertEqual(Resource.CategoryChoice.TAFSIR, response_body["results"][0]["category"])
        self.assertEqual(Resource.CategoryChoice.TAFSIR, response_body["results"][1]["category"])
        self.assertEqual(Resource.CategoryChoice.RECITATION, response_body["results"][2]["category"])

    def test_list_assets_when_search_should_return_filtered_assets_by_multiple_fields(
        self,
    ):
        """Test search functionality across name, description, category, and publisher fields."""
        # Arrange
        baker.make(
            Asset,
            name="Tafsir Al-Jalalayn",
            description="This is a tafsir book",
            category=Resource.CategoryChoice.TAFSIR,
        )
        baker.make(
            Asset,
            name="Muhammad Refaat",
            description="This is a recitation book",
            category=Resource.CategoryChoice.RECITATION,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )
        baker.make(
            Asset,
            name="King Fahd",
            description="This is a mushaf book",
            category=Resource.CategoryChoice.MUSHAF,
        )

        # Test search by name/category
        response = self.client.get("/cms-api/assets/", data={"search": "tafsir"}, format="json")
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Tafsir Al-Jalalayn", response_body["results"][0]["name"])

        # Test search by description
        response = self.client.get("/cms-api/assets/", data={"search": "recitation book"}, format="json")
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Muhammad Refaat", response_body["results"][0]["name"])
