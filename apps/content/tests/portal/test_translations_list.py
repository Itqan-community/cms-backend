from model_bakery import baker

from apps.content.models import Asset, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TranslationListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")

        # Create READY translation resources
        self.ready_translation_resource1 = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TRANSLATION,
            status=Resource.StatusChoice.READY,
        )
        self.ready_translation_resource2 = baker.make(
            Resource,
            publisher=self.publisher2,
            category=Resource.CategoryChoice.TRANSLATION,
            status=Resource.StatusChoice.READY,
        )

        # Create DRAFT translation resource (should be excluded)
        self.draft_translation_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TRANSLATION,
            status=Resource.StatusChoice.DRAFT,
        )

        # Create non-translation resource (should be excluded)
        self.mushaf_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.MUSHAF,
            status=Resource.StatusChoice.READY,
        )

        # Valid translation assets
        self.translation1 = baker.make(
            Asset,
            category=Resource.CategoryChoice.TRANSLATION,
            resource=self.ready_translation_resource1,
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
            category=Resource.CategoryChoice.TRANSLATION,
            resource=self.ready_translation_resource2,
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
            category=Resource.CategoryChoice.TRANSLATION,
            resource=self.draft_translation_resource,
            name="Draft Translation",
            description="Should not appear",
        )

        # Non-translation asset that should NOT be returned
        baker.make(
            Asset,
            category=Resource.CategoryChoice.MUSHAF,
            resource=self.mushaf_resource,
            name="Mushaf",
            description="Should not appear",
        )

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_list_translations_returns_only_ready_translation_assets(self):
        self.authenticate_user(self.user)
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

    def test_list_translations_filter_by_publisher_id(self):
        self.authenticate_user(self.user)
        response = self.client.get(f"/portal/translations/?publisher_id={self.publisher1.id}")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.translation1.id, items[0]["id"])
        self.assertEqual(self.publisher1.id, items[0]["publisher"]["id"])

    def test_list_translations_filter_by_license_code(self):
        self.authenticate_user(self.user)
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

    def test_list_translations_filter_by_language(self):
        self.authenticate_user(self.user)
        self.translation1.language = "ar"
        self.translation1.save()

        response = self.client.get("/portal/translations/?language=ar")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.translation1.id, items[0]["id"])

    def test_list_translations_filter_by_is_external(self):
        self.authenticate_user(self.user)
        # Create an external translation resource
        external_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TRANSLATION,
            status=Resource.StatusChoice.READY,
            is_external=True,
            external_url="https://example.com/translation",
        )
        external_translation = baker.make(
            Asset,
            category=Resource.CategoryChoice.TRANSLATION,
            resource=external_resource,
            name="External Translation",
            description="External",
        )

        response = self.client.get("/portal/translations/?is_external=true")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(external_translation.id, items[0]["id"])

    def test_list_translations_search_by_name(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/translations/?search=Sahih")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.translation1.id, items[0]["id"])

    def test_list_translations_search_by_publisher_name(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/translations/?search=Publisher%20Two")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.translation2.id, items[0]["id"])

    def test_list_translations_ordering_by_name(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/translations/?ordering=name")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)

    def test_list_translations_pagination(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/translations/?page_size=1")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertEqual(1, len(body["results"]))
        self.assertEqual(2, body["count"])

    def test_list_translations_unauthenticated_returns_401(self):
        response = self.client.get("/portal/translations/")
        self.assertEqual(401, response.status_code)
