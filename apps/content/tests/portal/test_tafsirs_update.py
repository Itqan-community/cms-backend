from model_bakery import baker

from apps.content.models import Asset, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TafsirUpdateTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")

        self.resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        self.tafsir = baker.make(
            Asset,
            category=Resource.CategoryChoice.TAFSIR,
            resource=self.resource,
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
        self.authenticate_user(self.user)
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
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertEqual("تفسير محدث", body["name_ar"])
        self.assertEqual("Updated Tafsir", body["name_en"])
        self.assertEqual("وصف محدث", body["description_ar"])
        self.assertEqual("Updated description", body["description_en"])
        self.assertEqual("شرح طويل جديد", body["long_description_ar"])
        self.assertEqual("New long explanation", body["long_description_en"])
        self.assertEqual("CC-BY", body["license"])

        # Verify in database
        updated_asset = Asset.objects.get(id=self.tafsir.id)
        self.assertEqual("تفسير محدث", updated_asset.name_ar)
        self.assertEqual("Updated Tafsir", updated_asset.name_en)
        self.assertEqual("CC-BY", updated_asset.license)

    def test_update_tafsir_where_patch_updates_partial_fields_should_return_200(self):
        self.authenticate_user(self.user)
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/",
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
        self.assertEqual("تفسير أصلي", body["name_ar"])
        self.assertEqual("Original description", body["description_en"])

    def test_update_tafsir_where_put_missing_required_field_should_return_400(self):
        self.authenticate_user(self.user)
        response = self.client.put(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "name_ar": "تفسير",
                "name_en": "Tafsir",
                # Missing license
                "language": "ar",
                "publisher_id": self.publisher1.id,
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(400, response.status_code, response.content)

    def test_update_tafsir_where_patch_with_invalid_name_should_return_400(self):
        self.authenticate_user(self.user)
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "name_ar": "",
                "name_en": "",  # Both names empty
            },
            content_type="application/json",
        )

        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("tafsir_name_required", body["error_name"])

    def test_update_tafsir_where_not_found_should_return_404(self):
        self.authenticate_user(self.user)
        response = self.client.patch(
            "/portal/tafsirs/nonexistent-slug/",
            data={
                "name_en": "Updated",
            },
            content_type="application/json",
        )

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("tafsir_not_found", body["error_name"])

    def test_update_tafsir_where_unauthenticated_should_return_401(self):
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/",
            data={
                "name_en": "Updated",
            },
        )

        self.assertEqual(401, response.status_code, response.content)
