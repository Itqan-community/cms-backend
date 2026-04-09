from model_bakery import baker

from apps.content.models import Asset, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TafsirListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")

        # Create READY tafsir resources
        self.ready_tafsir_resource1 = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        self.ready_tafsir_resource2 = baker.make(
            Resource,
            publisher=self.publisher2,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )

        # Create DRAFT tafsir resource (should be excluded)
        self.draft_tafsir_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.DRAFT,
        )

        # Create non-tafsir resource (should be excluded)
        self.mushaf_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.MUSHAF,
            status=Resource.StatusChoice.READY,
        )

        # Valid tafsir assets
        self.tafsir1 = baker.make(
            Asset,
            category=Resource.CategoryChoice.TAFSIR,
            resource=self.ready_tafsir_resource1,
            name="Tafsir Al-Tabari",
            name_ar="تفسير الطبري",
            name_en="Tafsir Al-Tabari",
            description="A comprehensive tafsir",
            description_ar="تفسير شامل",
            description_en="A comprehensive tafsir",
            license=Asset._meta.get_field("license").choices[0][0],
            language="ar",
        )
        self.tafsir2 = baker.make(
            Asset,
            category=Resource.CategoryChoice.TAFSIR,
            resource=self.ready_tafsir_resource2,
            name="Ibn Kathir Tafsir",
            name_ar="تفسير ابن كثير",
            name_en="Ibn Kathir Tafsir",
            description="Explanation of the Quran",
            description_ar="شرح القرآن",
            description_en="Explanation of the Quran",
            license=Asset._meta.get_field("license").choices[0][0],
            language="en",
        )

        # Tafsir that should NOT be returned (draft)
        baker.make(
            Asset,
            category=Resource.CategoryChoice.TAFSIR,
            resource=self.draft_tafsir_resource,
            name="Draft Tafsir",
            description="Should not appear",
        )

        # Non-tafsir asset that should NOT be returned
        baker.make(
            Asset,
            category=Resource.CategoryChoice.MUSHAF,
            resource=self.mushaf_resource,
            name="Mushaf",
            description="Should not appear",
        )

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_list_tafsirs_where_assets_are_ready_should_return_only_ready_tafsir_assets(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/tafsirs/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        self.assertEqual(2, len(items))
        returned_ids = {item["id"] for item in items}
        self.assertIn(self.tafsir1.id, returned_ids)
        self.assertIn(self.tafsir2.id, returned_ids)

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

    def test_list_tafsirs_where_publisher_id_is_filtered_should_return_matching_tafsirs(self):
        self.authenticate_user(self.user)
        response = self.client.get(f"/portal/tafsirs/?publisher_id={self.publisher1.id}")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.tafsir1.id, items[0]["id"])
        self.assertEqual(self.publisher1.id, items[0]["publisher"]["id"])

    def test_list_tafsirs_where_license_code_is_filtered_should_return_matching_tafsirs(self):
        self.authenticate_user(self.user)
        # Set different licenses on tafsirs
        self.tafsir1.license = "CC0"
        self.tafsir1.save()
        self.tafsir2.license = "CC-BY"
        self.tafsir2.save()

        response = self.client.get("/portal/tafsirs/?license_code=CC0")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual("CC0", items[0]["license"])

    def test_list_tafsirs_where_language_is_filtered_should_return_matching_tafsirs(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/tafsirs/?language=ar")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.tafsir1.id, items[0]["id"])
        self.assertEqual("ar", self.tafsir1.language)

    def test_list_tafsirs_where_is_external_is_filtered_should_return_external_tafsir(self):
        self.authenticate_user(self.user)
        # Create an external tafsir resource
        external_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
            is_external=True,
            external_url="https://example.com/tafsir",
        )
        external_tafsir = baker.make(
            Asset,
            category=Resource.CategoryChoice.TAFSIR,
            resource=external_resource,
            name="External Tafsir",
            description="External",
        )

        response = self.client.get("/portal/tafsirs/?is_external=true")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(external_tafsir.id, items[0]["id"])

    def test_list_tafsirs_where_search_by_name_should_return_matching_tafsir(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/tafsirs/?search=Tabari")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.tafsir1.id, items[0]["id"])

    def test_list_tafsirs_where_search_by_publisher_name_should_return_matching_tafsir(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/tafsirs/?search=Publisher%20Two")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.tafsir2.id, items[0]["id"])

    def test_list_tafsirs_where_ordering_by_name_should_return_sorted_names(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/tafsirs/?ordering=name")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)

    def test_list_tafsirs_where_pagination_is_applied_should_return_page_and_count(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/tafsirs/?page_size=1")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertEqual(1, len(body["results"]))
        self.assertEqual(2, body["count"])

    def test_list_tafsirs_where_unauthenticated_should_return_401(self):
        response = self.client.get("/portal/tafsirs/")
        self.assertEqual(401, response.status_code)
