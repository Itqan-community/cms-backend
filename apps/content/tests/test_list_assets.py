from model_bakery import baker

from apps.content.models import Asset
from apps.content.models import License
from apps.core.tests import BaseTestCase


class ListAssetTest(BaseTestCase):
    def test_list_asset_should_return_all_available_assets(self):
        # Arrange
        baker.make(Asset, name="Tafsir Ibn Katheer")

        # Act
        response = self.client.get("/content/assets/", format="json")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Tafsir Ibn Katheer", response_body["results"][0]["name"])

    def test_list_asset_filter_by_license_code_should_return_filtered_assets(self):
        # Arrange
        license1 = baker.make(License, code="CC-BY-SA-4.0")
        license2 = baker.make(License, code="CC-BY-NC-4.0")
        baker.make(Asset, name="Tafsir Al-Jalalayn", license=license1)
        baker.make(Asset, name="Tafsir Ibn Katheer", license=license2)

        # Act
        response = self.client.get("/content/assets/", data={"license_code": "CC-BY-SA-4.0"}, format="json")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Tafsir Al-Jalalayn", response_body["results"][0]["name"])

    def test_list_asset_filter_by_category_should_return_filtered_assets(self):
        # Arrange
        baker.make(Asset, name="Tafsir Al-Jalalayn", category=Asset.CategoryChoice.TAFSIR)
        baker.make(Asset, name="Muhammad Refaat", category=Asset.CategoryChoice.RECITATION)

        # Act
        response = self.client.get(
            "/content/assets/", data={"category": Asset.CategoryChoice.RECITATION}, format="json"
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Muhammad Refaat", response_body["results"][0]["name"])

    def test_list_asset_filter_by_multiple_categories_should_return_filtered_assets(self):
        # Arrange
        baker.make(Asset, name="Tafsir Al-Jalalayn", category=Asset.CategoryChoice.TAFSIR)
        baker.make(Asset, name="Muhammad Refaat", category=Asset.CategoryChoice.RECITATION)
        baker.make(Asset, name="King Fahd", category=Asset.CategoryChoice.MUSHAF)

        # Act
        response = self.client.get(
            f"/content/assets/?category={Asset.CategoryChoice.RECITATION}&category={Asset.CategoryChoice.TAFSIR}",
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(2, len(response_body["results"]))
        # self.assertEqual("Muhammad Refaat", response_body['results'][0]['name'])

    def test_list_order_by_name_descending_should_return_sorted_assets(self):
        # Arrange
        baker.make(Asset, name="A")
        baker.make(Asset, name="C")
        baker.make(Asset, name="B")

        # Act
        response = self.client.get("/content/assets/", data={"ordering": "-name"}, format="json")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(3, len(response_body["results"]))
        self.assertEqual("C", response_body["results"][0]["name"])
        self.assertEqual("B", response_body["results"][1]["name"])
        self.assertEqual("A", response_body["results"][2]["name"])

    def test_list_order_by_name_ascending_should_return_sorted_assets(self):
        # Arrange
        baker.make(Asset, name="A")
        baker.make(Asset, name="C")
        baker.make(Asset, name="B")

        # Act
        response = self.client.get("/content/assets/", data={"ordering": "name"}, format="json")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(3, len(response_body["results"]))
        self.assertEqual("A", response_body["results"][0]["name"])
        self.assertEqual("B", response_body["results"][1]["name"])
        self.assertEqual("C", response_body["results"][2]["name"])

    def test_list_assets_order_by_category_descending_should_return_sorted_assets(self):
        # Arrange
        baker.make(Asset, name="A", category=Asset.CategoryChoice.TAFSIR)
        baker.make(Asset, name="C", category=Asset.CategoryChoice.RECITATION)
        baker.make(Asset, name="B", category=Asset.CategoryChoice.TAFSIR)

        # Act
        response = self.client.get("/content/assets/", data={"ordering": "-category"}, format="json")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(3, len(response_body["results"]))
        self.assertEqual(Asset.CategoryChoice.TAFSIR, response_body["results"][0]["category"])
        self.assertEqual(Asset.CategoryChoice.TAFSIR, response_body["results"][1]["category"])
        self.assertEqual(Asset.CategoryChoice.RECITATION, response_body["results"][2]["category"])

    def test_list_assets_when_search_by_category_should_return_filtered_assets(self):
        # Arrange
        baker.make(Asset, name="Tafsir Al-Jalalayn", description="This is a tafsir book")
        baker.make(Asset, name="Muhammad Refaat", description="This is a recitation book")
        baker.make(Asset, name="King Fahd", description="This is a mushaf book")

        # Act
        response = self.client.get("/content/assets/", data={"search": "tafsir"}, format="json")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Tafsir Al-Jalalayn", response_body["results"][0]["name"])

    def test_list_assets_when_search_by_description_should_return_filtered_assets(self):
        # Arrange
        baker.make(Asset, name="Tafsir Al-Jalalayn", description="This is a tafsir book")
        baker.make(Asset, name="Muhammad Refaat", description="This is a recitation book")
        baker.make(Asset, name="King Fahd", description="This is a mushaf book")

        # Act
        response = self.client.get("/content/assets/", data={"search": "recitation book"}, format="json")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        response_body = response.json()
        self.assertEqual(1, len(response_body["results"]))
        self.assertEqual("Muhammad Refaat", response_body["results"][0]["name"])
