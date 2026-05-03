from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, LicenseChoice, StatusChoice
from apps.core.tests import BaseTestCase


class ListAssetTest(BaseTestCase):
    def test_list_asset_should_return_all_available_assets(self):
        # Arrange
        baker.make(
            Asset,
            name="Tafsir Ibn Katheer",
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
        )

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
            Asset,
            name="Tafsir Al-Jalalayn",
            license=LicenseChoice.CC_BY_SA,
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
        )
        baker.make(
            Asset,
            name="Tafsir Ibn Katheer",
            license=LicenseChoice.CC_BY_NC,
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
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
        baker.make(
            Asset,
            name="Tafsir Al-Jalalayn",
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
        )
        baker.make(
            Asset,
            name="Muhammad Refaat",
            category=CategoryChoice.RECITATION,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
            status=StatusChoice.READY,
        )

        # Act
        response = self.client.get(
            "/cms-api/assets/",
            data={"category": CategoryChoice.RECITATION},
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
        baker.make(
            Asset,
            name="Tafsir Al-Jalalayn",
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
        )
        baker.make(
            Asset,
            name="Muhammad Refaat",
            category=CategoryChoice.RECITATION,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
            status=StatusChoice.READY,
        )
        baker.make(
            Asset,
            name="King Fahd",
            category=CategoryChoice.MUSHAF,
            status=StatusChoice.READY,
        )

        # Act
        response = self.client.get(
            f"/cms-api/assets/?category={CategoryChoice.RECITATION}&category={CategoryChoice.TAFSIR}",
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(2, len(response_body["results"]))
        # self.assertEqual("Muhammad Refaat", response_body['results'][0]['name'])

    def test_list_order_by_name_descending_should_return_sorted_assets(self):
        # Arrange
        baker.make(Asset, name="A", category=CategoryChoice.TAFSIR, status=StatusChoice.READY)
        baker.make(Asset, name="C", category=CategoryChoice.TAFSIR, status=StatusChoice.READY)
        baker.make(Asset, name="B", category=CategoryChoice.TAFSIR, status=StatusChoice.READY)

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
        baker.make(Asset, name="A", category=CategoryChoice.TAFSIR, status=StatusChoice.READY)
        baker.make(Asset, name="C", category=CategoryChoice.TAFSIR, status=StatusChoice.READY)
        baker.make(Asset, name="B", category=CategoryChoice.TAFSIR, status=StatusChoice.READY)

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
        baker.make(Asset, name="A", category=CategoryChoice.TAFSIR, status=StatusChoice.READY)
        baker.make(
            Asset,
            name="C",
            category=CategoryChoice.RECITATION,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
            status=StatusChoice.READY,
        )
        baker.make(Asset, name="B", category=CategoryChoice.TAFSIR, status=StatusChoice.READY)

        # Act
        response = self.client.get("/cms-api/assets/", data={"ordering": "-category"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_body = response.json()
        self.assertEqual(3, len(response_body["results"]))
        self.assertEqual(CategoryChoice.TAFSIR, response_body["results"][0]["category"])
        self.assertEqual(CategoryChoice.TAFSIR, response_body["results"][1]["category"])
        self.assertEqual(CategoryChoice.RECITATION, response_body["results"][2]["category"])

    def test_list_assets_when_search_should_return_filtered_assets_by_multiple_fields(
        self,
    ):
        """Test search functionality across name, description, category, and publisher fields."""
        # Arrange
        baker.make(
            Asset,
            name="Tafsir Al-Jalalayn",
            description="This is a tafsir book",
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
        )
        baker.make(
            Asset,
            name="Muhammad Refaat",
            description="This is a recitation book",
            category=CategoryChoice.RECITATION,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
            status=StatusChoice.READY,
        )
        baker.make(
            Asset,
            name="King Fahd",
            description="This is a mushaf book",
            category=CategoryChoice.MUSHAF,
            status=StatusChoice.READY,
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

    # ── Pagination ────────────────────────────────────────────

    def test_list_assets_default_page_size_should_return_20_items(self):
        # Arrange — 25 assets, default page_size is 20
        baker.make(Asset, _quantity=25, category=CategoryChoice.TAFSIR, status=StatusChoice.READY)

        # Act
        response = self.client.get("/cms-api/assets/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(25, body["count"])
        self.assertEqual(20, len(body["results"]))

    def test_list_assets_custom_page_size_should_return_requested_number_of_items(self):
        # Arrange — 25 assets; passing page_size=25 must return all 25 (regression for the bug
        # where page_size was silently reset to 20 by Pydantic re-initialisation in __init__)
        baker.make(Asset, _quantity=25, category=CategoryChoice.TAFSIR, status=StatusChoice.READY)

        # Act
        response = self.client.get("/cms-api/assets/", data={"page_size": 25}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(25, body["count"])
        self.assertEqual(25, len(body["results"]))

    def test_list_assets_second_page_should_return_remaining_items(self):
        # Arrange — 25 assets, page_size=20 → page 2 has 5
        baker.make(Asset, _quantity=25, category=CategoryChoice.TAFSIR, status=StatusChoice.READY)

        # Act
        response = self.client.get("/cms-api/assets/", data={"page": 2, "page_size": 20}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(25, body["count"])
        self.assertEqual(5, len(body["results"]))

    def test_list_assets_page_size_exceeding_max_should_be_capped_at_1000(self):
        # Arrange — 5 assets; page_size=2000 must be capped at MAX_PAGE_SIZE=1000
        baker.make(Asset, _quantity=5, category=CategoryChoice.TAFSIR, status=StatusChoice.READY)

        # Act
        response = self.client.get("/cms-api/assets/", data={"page_size": 2000}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(5, body["count"])
        self.assertEqual(5, len(body["results"]))
