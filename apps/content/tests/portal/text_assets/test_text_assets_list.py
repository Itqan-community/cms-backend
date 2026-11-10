from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TextAssetListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")

        # Valid text asset assets
        self.text_asset1 = baker.make(
            Asset,
            category=CategoryChoice.TEXT,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher1,
            status=StatusChoice.READY,
            name="Text asset Al-Tabari",
            name_ar="تفسير الطبري",
            name_en="Text asset Al-Tabari",
            description="A comprehensive text_asset",
            description_ar="تفسير شامل",
            description_en="A comprehensive text_asset",
            license=Asset._meta.get_field("license").choices[0][0],
            language="ar",
        )
        self.text_asset2 = baker.make(
            Asset,
            category=CategoryChoice.TEXT,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher2,
            status=StatusChoice.READY,
            name="Ibn Kathir Text asset",
            name_ar="تفسير ابن كثير",
            name_en="Ibn Kathir Text asset",
            description="Explanation of the Quran",
            description_ar="شرح القرآن",
            description_en="Explanation of the Quran",
            license=Asset._meta.get_field("license").choices[0][0],
            language="en",
        )

        # A draft stays listed in the portal (consumers don't see it)
        self.draft = baker.make(
            Asset,
            category=CategoryChoice.TEXT,
            template=AssetTemplateChoice.AYAH,
            publisher=baker.make(Publisher, name="Publisher Three"),
            status=StatusChoice.DRAFT,
            license="CC-BY-ND",
            name="Draft Text asset",
            description="Hidden from consumers",
        )

        # Non-text_asset asset that should NOT be returned
        baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            publisher=self.publisher1,
            status=StatusChoice.READY,
            name="Mushaf",
            description="Should not appear",
        )

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)

    def test_list_text_assets_should_return_ready_and_draft_assets_with_status(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        response = self.client.get("/portal/text-assets/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        self.assertEqual(3, len(items))
        statuses = {item["id"]: item["status"] for item in items}
        self.assertEqual("draft", statuses[self.draft.id])
        returned_ids = {item["id"] for item in items}
        self.assertIn(self.text_asset1.id, returned_ids)
        self.assertIn(self.text_asset2.id, returned_ids)

        # Check required fields
        for item in items:
            self.assertIn("id", item)
            self.assertIn("slug", item)
            self.assertIn("name", item)
            self.assertIn("description", item)
            self.assertIn("publisher", item)
            self.assertIn("license", item)
            self.assertIn("created_at", item)
            self.assertIsInstance(item["publisher"], dict)
            self.assertSetEqual(set(item["publisher"].keys()), {"id", "name"})

    def test_list_text_assets_where_publisher_id_is_filtered_should_return_matching_text_assets(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        response = self.client.get(f"/portal/text-assets/?publisher_id={self.publisher1.id}")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.text_asset1.id, items[0]["id"])
        self.assertEqual(self.publisher1.id, items[0]["publisher"]["id"])

    def test_list_text_assets_where_license_code_is_filtered_should_return_matching_text_assets(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        # Set different licenses on text_assets
        self.text_asset1.license = "CC0"
        self.text_asset1.save()
        self.text_asset2.license = "CC-BY"
        self.text_asset2.save()

        response = self.client.get("/portal/text-assets/?license_code=CC0")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual("CC0", items[0]["license"])

    def test_list_text_assets_where_language_is_filtered_should_return_matching_text_assets(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        response = self.client.get("/portal/text-assets/?language=ar")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.text_asset1.id, items[0]["id"])
        self.assertEqual("ar", self.text_asset1.language)

    def test_list_text_assets_where_is_external_is_filtered_should_return_external_text_asset(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        external_text_asset = baker.make(
            Asset,
            category=CategoryChoice.TEXT,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher1,
            status=StatusChoice.READY,
            is_external=True,
            external_url="https://example.com/text_asset",
            name="External Text asset",
            description="External",
        )

        response = self.client.get("/portal/text-assets/?is_external=true")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(external_text_asset.id, items[0]["id"])

    def test_list_text_assets_where_search_by_name_should_return_matching_text_asset(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        response = self.client.get("/portal/text-assets/?search=Tabari")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.text_asset1.id, items[0]["id"])

    def test_list_text_assets_where_search_by_publisher_name_should_return_matching_text_asset(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        response = self.client.get("/portal/text-assets/?search=Publisher%20Two")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.text_asset2.id, items[0]["id"])

    def test_list_text_assets_where_ordering_by_name_should_return_sorted_names(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        response = self.client.get("/portal/text-assets/?ordering=name")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)

    def test_list_text_assets_where_pagination_is_applied_should_return_page_and_count(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        response = self.client.get("/portal/text-assets/?page_size=1")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertEqual(1, len(body["results"]))
        self.assertEqual(3, body["count"])

    def test_list_text_assets_where_unauthenticated_should_return_401(self):
        response = self.client.get("/portal/text-assets/")
        self.assertEqual(401, response.status_code)

    def test_list_text_assets_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.get("/portal/text-assets/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
