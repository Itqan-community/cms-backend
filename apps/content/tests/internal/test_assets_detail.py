from model_bakery import baker

from apps.content.models import Asset, LicenseChoice, Resource, UsageEvent
from apps.core.tests import BaseTestCase
from apps.users.models import User


class DetailAssetTest(BaseTestCase):
    def test_detail_assets_where_valid_id_should_return_full_payload_en(self):
        # Arrange
        asset = baker.make(
            Asset,
            name="Tafsir Ibn Katheer",
            description="A comprehensive tafsir of the Quran",
            long_description=(
                "This is a detailed explanation of the Quran by Ibn Katheer, covering various aspects of "
                "Islamic interpretation."
            ),
            category=Resource.CategoryChoice.TAFSIR,
            license=LicenseChoice.CC_BY_SA,
            thumbnail_url="thumbnails/tafseer.png",
        )

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(asset.id, body["id"])
        self.assertEqual("Tafsir Ibn Katheer", body["name"])
        self.assertEqual("tafsir", body["category"])
        self.assertEqual("A comprehensive tafsir of the Quran", body["description"])
        self.assertIn("publisher", body)
        self.assertIn("id", body["publisher"])  # Publisher structure
        self.assertIn("name", body["publisher"])  # Publisher structure
        self.assertIn("description", body["publisher"])  # Publisher structure
        self.assertIn("thumbnails/tafseer.png", body["thumbnail_url"])
        self.assertEqual("CC-BY-SA", body["license"])

    def test_detail_assets_where_response_schema_should_include_all_required_fields(
        self,
    ):
        # Arrange
        asset = baker.make(
            Asset,
            name="Schema Test Asset",
            description="Test asset for schema validation",
            long_description="Extended description for schema testing",
            license=LicenseChoice.CC_BY,
            category=Resource.CategoryChoice.MUSHAF,
            thumbnail_url="thumbs/schema.png",
        )

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/", format="json")

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
        # Verify license is a string
        self.assertIsInstance(body["license"], str, "License should be a string")

    def test_detail_assets_where_various_categories_should_return_correct_category_and_thumbnail(
        self,
    ):
        # Arrange
        assets = [
            baker.make(
                Asset,
                name="Tafsir Asset",
                description="desc",
                category=Resource.CategoryChoice.TAFSIR,
                license=LicenseChoice.CC0,
                thumbnail_url="thumbs/tafsir.png",
            ),
            baker.make(
                Asset,
                name="Recitation Asset",
                description="desc",
                category=Resource.CategoryChoice.RECITATION,
                license=LicenseChoice.CC0,
                thumbnail_url="thumbs/recitation.png",
                reciter=baker.make("content.Reciter", name="Test Reciter"),
                riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
            ),
            baker.make(
                Asset,
                name="Mushaf Asset",
                description="desc",
                category=Resource.CategoryChoice.MUSHAF,
                license=LicenseChoice.CC0,
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
                response = self.client.get(f"/cms-api/assets/{target.id}/", format="json")
                self.assertEqual(200, response.status_code, response.content)
                body = response.json()
                self.assertEqual(expected_category, body["category"])
                self.assertIn(expected_thumb, body["thumbnail_url"])

    def test_detail_assets_where_language_ar_should_return_arabic_content_if_present(
        self,
    ):
        # Arrange
        self.authenticate_user(None, language="ar")
        asset = baker.make(
            Asset,
            name="اسم الأصل",
            description="وصف عربي",
            long_description="وصف عربي مطول",
            category=Resource.CategoryChoice.TAFSIR,
            license=LicenseChoice.CC0,
            thumbnail_url="thumbs/localized.png",
        )

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("وصف عربي", body["description"])  # Arabic content preserved
        self.assertEqual("وصف عربي مطول", body["long_description"])  # Arabic content preserved
        self.assertEqual("CC0", body["license"])  # CC0 license code
        self.assertIn("thumbs/localized.png", body["thumbnail_url"])

    def test_detail_assets_where_language_ar_missing_translations_should_fallback(self):
        # Arrange
        self.authenticate_user(None, language="ar")
        asset = baker.make(
            Asset,
            name="Asset Name",
            description="English description",
            long_description="English long description",
            category=Resource.CategoryChoice.RECITATION,
            license=LicenseChoice.CC0,
            thumbnail_url="thumbs/en-only.png",
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("English description", body["description"])  # fallback
        self.assertEqual("English long description", body["long_description"])  # fallback
        self.assertEqual("CC0", body["license"])  # CC0 license code
        self.assertIn("thumbs/en-only.png", body["thumbnail_url"])

    def test_detail_assets_where_id_format_invalid_should_return_400(self):
        # Arrange - Invalid integer formats should return 400 validation error
        invalid_formats = [
            "not-a-number",  # Non-numeric
            "123.45",  # Decimal
            "abc123",  # Mixed alphanumeric
        ]

        for invalid_format in invalid_formats:
            with self.subTest(invalid_format=invalid_format):
                # Act
                response = self.client.get(f"/cms-api/assets/{invalid_format}/", format="json")

                # Assert - Invalid formats result in 400 validation error
                self.assertEqual(
                    400,
                    response.status_code,
                    f"Failed for format: {invalid_format}, response: {response.content}",
                )

    def test_detail_assets_where_path_is_empty_should_return_404(self):
        # Arrange
        empty_path = ""

        # Act
        response = self.client.get(f"/cms-api/assets/{empty_path}/", format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_detail_assets_where_authenticated_user_should_create_usage_event(self):
        # Arrange
        user = baker.make(User, email="test@example.com", is_active=True)
        asset = baker.make(
            Asset,
            name="Usage Event Test Asset",
            description="Test asset for usage event tracking",
            category=Resource.CategoryChoice.TAFSIR,
            license=LicenseChoice.CC_BY,
            thumbnail_url="thumbnails/test.png",
        )

        # Act
        self.authenticate_user(user)
        response = self.client.get(f"/cms-api/assets/{asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)

        # Verify usage event was created in database
        usage_events = UsageEvent.objects.filter(
            developer_user=user,
            usage_kind=UsageEvent.UsageKindChoice.VIEW,
            subject_kind=UsageEvent.SubjectKindChoice.ASSET,
            asset_id=asset.id,
        )
        self.assertEqual(1, usage_events.count())

        usage_event = usage_events.first()
        self.assertEqual(usage_event.developer_user, user)
        self.assertEqual(usage_event.usage_kind, UsageEvent.UsageKindChoice.VIEW)
        self.assertEqual(usage_event.subject_kind, UsageEvent.SubjectKindChoice.ASSET)
        self.assertEqual(usage_event.asset_id, asset.id)
        self.assertIsNone(usage_event.resource_id)
        self.assertEqual(usage_event.effective_license, asset.license)
        self.assertIsInstance(usage_event.metadata, dict)

    def test_detail_assets_where_anonymous_user_should_not_create_usage_event(self):
        # Arrange - Clear authentication for anonymous user
        self.authenticate_user(None)
        asset = baker.make(
            Asset,
            name="Anonymous Test Asset",
            description="Test asset for anonymous access",
            category=Resource.CategoryChoice.MUSHAF,
            license=LicenseChoice.CC0,
            thumbnail_url="thumbnails/anonymous.png",
        )

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)

        # Verify no usage event was created for anonymous user
        usage_events = UsageEvent.objects.filter(
            usage_kind=UsageEvent.UsageKindChoice.VIEW,
            subject_kind=UsageEvent.SubjectKindChoice.ASSET,
            asset_id=asset.id,
        )
        self.assertEqual(0, usage_events.count())

    def test_detail_assets_where_authenticated_user_should_include_request_metadata(
        self,
    ):
        # Arrange
        user = baker.make(User, email="metadata@example.com", is_active=True)
        self.authenticate_user(user)
        asset = baker.make(
            Asset,
            name="Metadata Test Asset",
            description="Test asset for request metadata",
            category=Resource.CategoryChoice.RECITATION,
            license=LicenseChoice.CC_BY_SA,
            thumbnail_url="thumbnails/metadata.png",
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )

        # Act - Include custom headers
        response = self.client.get(
            f"/cms-api/assets/{asset.id}/",
            format="json",
            headers={
                "user-agent": "Test Agent/1.0",
                "x-forwarded-for": "192.168.1.100",
            },
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)

        # Verify usage event was created with correct metadata
        usage_events = UsageEvent.objects.filter(
            developer_user=user,
            usage_kind=UsageEvent.UsageKindChoice.VIEW,
            subject_kind=UsageEvent.SubjectKindChoice.ASSET,
            asset_id=asset.id,
        )
        self.assertEqual(1, usage_events.count())

        usage_event = usage_events.first()
        self.assertEqual(usage_event.user_agent, "Test Agent/1.0")
        # Note: IP address capture depends on Django test client configuration
        # In real requests, this would capture the client IP

    def test_detail_assets_where_thumbnail_url_is_null_should_return_valid_response(
        self,
    ):
        # Arrange
        asset = baker.make(
            Asset,
            name="Asset Without Thumbnail",
            description="Test asset without thumbnail",
            long_description="This asset has no thumbnail URL to test optional field",
            category=Resource.CategoryChoice.TAFSIR,
            license=LicenseChoice.CC0,
            thumbnail_url=None,  # Test the optional field
        )

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(asset.id, body["id"])
        self.assertEqual("Asset Without Thumbnail", body["name"])
        self.assertEqual(body["thumbnail_url"], None)
        self.assertEqual("CC0", body["license"])

        # Verify other required fields are still present
        self.assertIn("publisher", body)
        self.assertIn("snapshots", body)
