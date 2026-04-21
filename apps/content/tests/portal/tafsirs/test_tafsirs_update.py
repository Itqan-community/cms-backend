from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TafsirUpdateTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")

        self.tafsir = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher1,
            status=StatusChoice.READY,
            name="Original Tafsir",
            name_ar="تفسير أصلي",
            name_en="Original Tafsir",
            description="Original description",
            description_ar="وصف أصلي",
            description_en="Original description",
            long_description_ar="",
            long_description_en="",
            license="CC0",
            language="ar",
        )

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_update_tafsir_where_put_updates_all_fields_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.put(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "name_ar": "تفسير محدث",
                "name_en": "Updated Tafsir",
                "description_ar": "وصف محدث",
                "description_en": "Updated description",
                "long_description_ar": "شرح طويل جديد",
                "long_description_en": "New long explanation",
                "license": "CC-BY",
                "language": "en",
                "publisher_id": self.publisher1.id,
                "is_external": False,
            },
            format="multipart",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertEqual("تفسير محدث", body["name_ar"])
        self.assertEqual("Updated Tafsir", body["name_en"])
        self.assertEqual("وصف محدث", body["description_ar"])
        self.assertEqual("Updated description", body["description_en"])
        self.assertEqual("شرح طويل جديد", body["long_description_ar"])
        self.assertEqual("New long explanation", body["long_description_en"])
        self.assertEqual("CC-BY", body["license"])
        self.assertEqual("en", body["language"])

        # Verify in database
        updated_asset = Asset.objects.get(id=self.tafsir.id)
        self.assertEqual("تفسير محدث", updated_asset.name_ar)
        self.assertEqual("Updated Tafsir", updated_asset.name_en)
        self.assertEqual("CC-BY", updated_asset.license)
        self.assertEqual("en", updated_asset.language)

    def test_update_tafsir_where_patch_updates_partial_fields_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "name_en": "Patched English Name",
                "description_ar": "وصف معدل",
            },
            format="multipart",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Changed fields
        self.assertEqual("Patched English Name", body["name_en"])
        self.assertEqual("وصف معدل", body["description_ar"])

        # Unchanged fields should remain
        self.assertEqual("تفسير أصلي", body["name_ar"])
        self.assertEqual("Original description", body["description_en"])
        self.assertEqual("ar", body["language"])

    def test_update_tafsir_where_put_missing_required_field_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.put(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "name_ar": "تفسير",
                "name_en": "Tafsir",
                # Missing license
                "language": "ar",
                "publisher_id": self.publisher1.id,
                "is_external": False,
            },
            format="multipart",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)

    def test_update_tafsir_where_patch_with_invalid_name_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "name_ar": "",
                "name_en": "",  # Both names empty
            },
            format="multipart",
        )

        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("tafsir_name_required", body["error_name"])

    def test_update_tafsir_where_not_found_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.patch(
            "/portal/tafsirs/nonexistent-slug/",
            data={
                "name_en": "Updated",
            },
            format="multipart",
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("tafsir_not_found", body["error_name"])

    def test_update_tafsir_where_unauthenticated_should_return_401(self):
        # Arrange

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "name_en": "Updated",
            },
            format="multipart",
        )

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertEqual("authentication_error", body["error_name"])

    def test_update_tafsir_where_thumbnail_provided_should_upload_and_return_url(self):
        # Arrange
        self.authenticate_user(self.user)
        image = SimpleUploadedFile("thumb.jpg", b"file_content", content_type="image/jpeg")

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "name_en": "Updated Name",
                "thumbnail": image,
            },
            format="multipart",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIsNotNone(body.get("thumbnail_url"))
        self.assertTrue(body["thumbnail_url"].endswith(".jpg"))

        # Verify persisted in database
        self.tafsir.refresh_from_db()
        self.assertTrue(bool(self.tafsir.thumbnail_url))
        self.assertTrue(self.tafsir.thumbnail_url.name.endswith(".jpg"))

        # Clean up uploaded file
        self.tafsir.thumbnail_url.delete()

    def test_update_tafsir_where_is_external_true_and_url_present_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "is_external": True,
                "external_url": "https://example.com/updated",
            },
            format="multipart",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertTrue(body["is_external"])
        self.assertEqual("https://example.com/updated", body["external_url"])

    def test_update_tafsir_where_is_external_true_and_no_url_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "is_external": True,
                "external_url": "",  # explicitly missing URL
            },
            format="multipart",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("external_url_required", body["error_name"])

    def test_update_tafsir_where_is_external_false_forces_url_null_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)
        # first make it external
        self.tafsir.is_external = True
        self.tafsir.external_url = "https://example.com/original"
        self.tafsir.save()

        # Act
        # turning it false, the external url should be set to None natively
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "is_external": False,
                "external_url": "",  # what client might pass
            },
            format="multipart",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertFalse(body["is_external"])
        self.assertIsNone(body["external_url"])

        # Check db
        self.tafsir.refresh_from_db()
        self.assertFalse(self.tafsir.is_external)
        self.assertIsNone(self.tafsir.external_url)
