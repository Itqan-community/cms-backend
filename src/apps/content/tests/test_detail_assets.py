from model_bakery import baker

from apps.content.models import Asset
from apps.content.models import License
from apps.core.tests import BaseTestCase


class DetailAssetTest(BaseTestCase):
    def test_detail_assets_where_valid_id_should_return_full_payload_en(self):
        # Arrange
        license_obj = baker.make(
            License,
            code="CC-BY-SA-4.0",
            name="Creative Commons Attribution-ShareAlike 4.0",
            short_name="CC BY-SA 4.0",
        )
        asset = baker.make(
            Asset,
            name="Tafsir Ibn Katheer",
            description="A comprehensive tafsir of the Quran",
            long_description=(
                "This is a detailed explanation of the Quran by Ibn Katheer, covering various aspects of "
                "Islamic interpretation."
            ),
            category=Asset.CategoryChoice.TAFSIR,
            license=license_obj,
            thumbnail_url="thumbnails/tafseer.png",
        )

        # Act
        response = self.client.get(f"/content/assets/{asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(str(asset.id), body["id"])
        self.assertEqual("Tafsir Ibn Katheer", body["name"])
        self.assertEqual("tafsir", body["category"])
        self.assertEqual("A comprehensive tafsir of the Quran", body["description"])
        self.assertIn("publisher", body)
        self.assertIn("id", body["publisher"])  # Publisher structure
        self.assertIn("name", body["publisher"])  # Publisher structure
        self.assertIn("description", body["publisher"])  # Publisher structure
        self.assertTrue(body["thumbnail_url"].endswith("thumbnails/tafseer.png"))
        self.assertEqual("Creative Commons Attribution-ShareAlike 4.0", body["license"]["name"])
        self.assertEqual("CC-BY-SA-4.0", body["license"]["code"])
        self.assertEqual("CC BY-SA 4.0", body["license"]["short_name"])

    def test_detail_assets_where_response_schema_should_include_all_required_fields(self):
        # Arrange
        license_obj = baker.make(
            License, code="CC-BY-4.0", name="Creative Commons Attribution 4.0", short_name="CC BY 4.0"
        )
        asset = baker.make(
            Asset,
            name="Schema Test Asset",
            description="Test asset for schema validation",
            long_description="Extended description for schema testing",
            license=license_obj,
            category=Asset.CategoryChoice.MUSHAF,
            thumbnail_url="thumbs/schema.png",
        )

        # Act
        response = self.client.get(f"/content/assets/{asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        required_fields = [
            "id",
            "category",
            "name",
            "description",
            "long_description",
            "thumbnail_url",
            "publisher",
            "license",
        ]
        for field in required_fields:
            self.assertIn(field, body, f"Missing required field: {field}")
        for field in ["id", "name", "description"]:
            self.assertIn(field, body["publisher"], f"Missing publisher field: {field}")
        for field in ["code", "name", "short_name"]:
            self.assertIn(field, body["license"], f"Missing license field: {field}")

    def test_detail_assets_where_various_categories_should_return_correct_category_and_thumbnail(self):
        # Arrange
        license_obj = baker.make(License, code="CC0", name="Public Domain", short_name="CC0")
        assets = [
            baker.make(
                Asset,
                name="Tafsir Asset",
                description="desc",
                category=Asset.CategoryChoice.TAFSIR,
                license=license_obj,
                thumbnail_url="thumbs/tafsir.png",
            ),
            baker.make(
                Asset,
                name="Recitation Asset",
                description="desc",
                category=Asset.CategoryChoice.RECITATION,
                license=license_obj,
                thumbnail_url="thumbs/recitation.png",
            ),
            baker.make(
                Asset,
                name="Mushaf Asset",
                description="desc",
                category=Asset.CategoryChoice.MUSHAF,
                license=license_obj,
                thumbnail_url="thumbs/mushaf.png",
            ),
        ]

        # Act + Assert
        for expected_category, expected_thumb, target in [
            ("tafsir", "thumbs/tafsir.png", assets[0]),
            ("recitation", "thumbs/recitation.png", assets[1]),
            ("mushaf", "thumbs/mushaf.png", assets[2]),
        ]:
            with self.subTest(asset=target.name):
                response = self.client.get(f"/content/assets/{target.id}/", format="json")
                self.assertEqual(200, response.status_code, response.content)
                body = response.json()
                self.assertEqual(expected_category, body["category"])
                self.assertTrue(body["thumbnail_url"].endswith(expected_thumb))

    def test_detail_assets_where_language_ar_should_return_arabic_content_if_present(self):
        # Arrange
        self.authenticate_user(None, language="ar")
        license_obj = baker.make(
            License,
            code="AR-CODE",
            name="رخصة عربية",
            short_name="AR",
        )
        asset = baker.make(
            Asset,
            name="اسم الأصل",
            description="وصف عربي",
            long_description="وصف عربي مطول",
            category=Asset.CategoryChoice.TAFSIR,
            license=license_obj,
            thumbnail_url="thumbs/localized.png",
        )

        # Act
        response = self.client.get(f"/content/assets/{asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("وصف عربي", body["description"])  # Arabic content preserved
        self.assertEqual("وصف عربي مطول", body["long_description"])  # Arabic content preserved
        self.assertEqual("رخصة عربية", body["license"]["name"])  # Arabic license name preserved
        self.assertTrue(body["thumbnail_url"].endswith("thumbs/localized.png"))

    def test_detail_assets_where_language_ar_missing_translations_should_fallback(self):
        # Arrange
        self.authenticate_user(None, language="ar")
        license_obj = baker.make(
            License,
            code="MIT",
            name="MIT License",
            short_name="MIT",
        )
        asset = baker.make(
            Asset,
            name="Asset Name",
            description="English description",
            long_description="English long description",
            category=Asset.CategoryChoice.RECITATION,
            license=license_obj,
            thumbnail_url="thumbs/en-only.png",
        )

        # Act
        response = self.client.get(f"/content/assets/{asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("English description", body["description"])  # fallback
        self.assertEqual("English long description", body["long_description"])  # fallback
        self.assertEqual("MIT License", body["license"]["name"])  # fallback
        self.assertTrue(body["thumbnail_url"].endswith("thumbs/en-only.png"))

    def test_detail_assets_where_uuid_format_invalid_should_return_400(self):
        # Arrange
        invalid_formats = [
            "123",  # Too short
            "not-a-uuid-at-all",  # Not UUID format
            "12345678-1234-1234-1234-1234567890123",  # Too long
            "12345678-1234-1234-1234-12345678901",  # Invalid characters
        ]

        for invalid_format in invalid_formats:
            with self.subTest(invalid_format=invalid_format):
                # Act
                response = self.client.get(f"/content/assets/{invalid_format}/", format="json")

                # Assert
                self.assertEqual(
                    400,
                    response.status_code,
                    f"Failed for format: {invalid_format}, response: {response.content}",
                )

    def test_detail_assets_where_path_is_empty_should_return_404(self):
        # Arrange
        empty_path = ""

        # Act
        response = self.client.get(f"/content/assets/{empty_path}/", format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
