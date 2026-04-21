from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TranslationUpdateTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")

        self.translation = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher1,
            status=StatusChoice.READY,
            name="Original Translation",
            name_ar="ترجمة أصلية",
            name_en="Original Translation",
            description="Original description",
            description_ar="وصف أصلي",
            description_en="Original description",
            long_description_ar="",
            long_description_en="",
            license="CC0",
            language="en",
        )

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_update_translation_where_put_updates_all_fields_should_return_200(self):
        self.authenticate_user(self.user)
        response = self.client.put(
            f"/portal/translations/{self.translation.slug}/",
            data={
                "name_ar": "ترجمة محدثة",
                "name_en": "Updated Translation",
                "description_ar": "وصف محدث",
                "description_en": "Updated description",
                "long_description_ar": "شرح طويل جديد",
                "long_description_en": "New long explanation",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher1.id,
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertEqual("ترجمة محدثة", body["name_ar"])
        self.assertEqual("Updated Translation", body["name_en"])
        self.assertEqual("وصف محدث", body["description_ar"])
        self.assertEqual("Updated description", body["description_en"])
        self.assertEqual("شرح طويل جديد", body["long_description_ar"])
        self.assertEqual("New long explanation", body["long_description_en"])
        self.assertEqual("CC-BY", body["license"])
        self.assertEqual("ar", body["language"])
        self.assertIn("slug", body)

        # Verify in database
        updated_asset = Asset.objects.get(id=self.translation.id)
        self.assertEqual("ترجمة محدثة", updated_asset.name_ar)
        self.assertEqual("Updated Translation", updated_asset.name_en)
        self.assertEqual("CC-BY", updated_asset.license)

    def test_update_translation_where_patch_updates_partial_fields_should_return_200(self):
        self.authenticate_user(self.user)
        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/",
            data={
                "name_en": "Patched English Name",
                "description_ar": "وصف معدل",
            },
            content_type="application/json",
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Changed fields
        self.assertEqual("Patched English Name", body["name_en"])
        self.assertEqual("وصف معدل", body["description_ar"])

        # Unchanged fields should remain
        self.assertEqual("ترجمة أصلية", body["name_ar"])
        self.assertEqual("Original description", body["description_en"])
        self.assertEqual("en", body["language"])
        self.assertIn("slug", body)

    def test_update_translation_where_put_missing_required_field_should_return_400(self):
        self.authenticate_user(self.user)
        response = self.client.put(
            f"/portal/translations/{self.translation.slug}/",
            data={
                "name_ar": "ترجمة",
                "name_en": "Translation",
                # Missing license
                "language": "en",
                "publisher_id": self.publisher1.id,
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(400, response.status_code, response.content)

    def test_update_translation_where_patch_with_invalid_name_should_return_400(self):
        self.authenticate_user(self.user)
        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/",
            data={
                "name_ar": "",
                "name_en": "",  # Both names empty
            },
            content_type="application/json",
        )

        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("translation_name_required", body["error_name"])

    def test_update_translation_where_not_found_should_return_404(self):
        self.authenticate_user(self.user)
        response = self.client.patch(
            "/portal/translations/nonexistent-slug/",
            data={
                "name_en": "Updated",
            },
            content_type="application/json",
        )

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("translation_not_found", body["error_name"])

    def test_update_translation_where_unauthenticated_should_return_401(self):
        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/",
            data={
                "name_en": "Updated",
            },
        )

        self.assertEqual(401, response.status_code, response.content)

    def test_update_translation_where_is_external_true_and_url_present_should_return_200(self):
        self.authenticate_user(self.user)
        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/",
            data={
                "is_external": True,
                "external_url": "https://example.com/updated",
            },
            content_type="application/json",
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertTrue(body["is_external"])
        self.assertEqual("https://example.com/updated", body["external_url"])

    def test_update_translation_where_is_external_true_and_no_url_should_return_400(self):
        self.authenticate_user(self.user)
        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/",
            data={
                "is_external": True,
                "external_url": "",  # explicitly absent
            },
            content_type="application/json",
        )

        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("external_url_required", body["error_name"])

    def test_update_translation_where_is_external_false_forces_url_null_should_return_200(self):
        self.authenticate_user(self.user)
        # first make it external
        self.translation.is_external = True
        self.translation.external_url = "https://example.com/old"
        self.translation.save()

        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/",
            data={
                "is_external": False,
                "external_url": "",  # what the frontend might submit
            },
            content_type="application/json",
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertFalse(body["is_external"])
        self.assertIsNone(body["external_url"])

        # check DB
        self.translation.refresh_from_db()
        self.assertFalse(self.translation.is_external)
        self.assertIsNone(self.translation.external_url)
