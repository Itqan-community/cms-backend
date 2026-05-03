from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TranslationListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")

        # Valid translation assets
        self.translation1 = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher1,
            status=StatusChoice.READY,
            name="Sahih International",
            name_ar="ترجمة صحيح إنترناشيونال",
            name_en="Sahih International",
            description="English translation of the Quran",
            description_ar="ترجمة القرآن الكريم باللغة الإنجليزية",
            description_en="English translation of the Quran",
            license=Asset._meta.get_field("license").choices[0][0],
            language="en",
        )
        self.translation2 = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher2,
            status=StatusChoice.READY,
            name="Pickthall Translation",
            name_ar="ترجمة بيكتال",
            name_en="Pickthall Translation",
            description="Translation by Pickthall",
            description_ar="ترجمة بيكتال",
            description_en="Translation by Pickthall",
            license=Asset._meta.get_field("license").choices[0][0],
            language="en",
        )

        # Translation that should NOT be returned (draft)
        baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher1,
            status=StatusChoice.DRAFT,
            name="Draft Translation",
            description="Should not appear",
        )

        # Non-translation asset that should NOT be returned
        baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            publisher=self.publisher1,
            status=StatusChoice.READY,
            name="Mushaf",
            description="Should not appear",
        )

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_list_translations_where_assets_are_ready_should_return_only_ready_assets(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TRANSLATION)
        response = self.client.get("/portal/translations/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        self.assertEqual(2, len(items))
        returned_ids = {item["id"] for item in items}
        self.assertIn(self.translation1.id, returned_ids)
        self.assertIn(self.translation2.id, returned_ids)

        # Check required fields
        for item in items:
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertIn("description", item)
            self.assertIn("publisher", item)
            self.assertIn("license", item)
            self.assertIn("created_at", item)
            self.assertIsInstance(item["publisher"], dict)
            self.assertSetEqual(set(item["publisher"].keys()), {"id", "name"})

    def test_list_translations_where_publisher_id_is_filtered_should_return_matching_translations(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TRANSLATION)
        response = self.client.get(f"/portal/translations/?publisher_id={self.publisher1.id}")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.translation1.id, items[0]["id"])
        self.assertEqual(self.publisher1.id, items[0]["publisher"]["id"])

    def test_list_translations_where_license_code_is_filtered_should_return_matching_translations(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TRANSLATION)
        # Set different licenses on translations
        self.translation1.license = "CC0"
        self.translation1.save()
        self.translation2.license = "CC-BY"
        self.translation2.save()

        response = self.client.get("/portal/translations/?license_code=CC0")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual("CC0", items[0]["license"])

    def test_list_translations_where_language_is_filtered_should_return_matching_translations(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TRANSLATION)
        self.translation1.language = "ar"
        self.translation1.save()

        response = self.client.get("/portal/translations/?language=ar")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.translation1.id, items[0]["id"])

    def test_list_translations_where_is_external_is_filtered_should_return_external_translation(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TRANSLATION)
        external_translation = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher1,
            status=StatusChoice.READY,
            is_external=True,
            external_url="https://example.com/translation",
            name="External Translation",
            description="External",
        )

        response = self.client.get("/portal/translations/?is_external=true")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(external_translation.id, items[0]["id"])

    def test_list_translations_where_search_by_name_should_return_matching_translation(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TRANSLATION)
        response = self.client.get("/portal/translations/?search=Sahih")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.translation1.id, items[0]["id"])

    def test_list_translations_where_search_by_publisher_name_should_return_matching_translation(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TRANSLATION)
        response = self.client.get("/portal/translations/?search=Publisher%20Two")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.translation2.id, items[0]["id"])

    def test_list_translations_where_ordering_by_name_should_return_sorted_names(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TRANSLATION)
        response = self.client.get("/portal/translations/?ordering=name")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)

    def test_list_translations_where_pagination_is_applied_should_return_page_and_count(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TRANSLATION)
        response = self.client.get("/portal/translations/?page_size=1")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertEqual(1, len(body["results"]))
        self.assertEqual(2, body["count"])

    def test_list_translations_where_unauthenticated_should_return_401(self):
        response = self.client.get("/portal/translations/")
        self.assertEqual(401, response.status_code)

    def test_list_translations_where_user_lacks_permission_should_return_403(self):
        user_without_permission = User.objects.create_user(email="noperm@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)
        response = self.client.get("/portal/translations/")
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
