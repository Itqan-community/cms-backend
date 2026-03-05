from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class CreatePublisherTest(BaseTestCase):
    def setUp(self):
        self.user = baker.make(User, email="admin@test.com", is_staff=True)
        self.authenticate_user(self.user)

    def test_create_publisher_where_all_fields_provided_should_return_201(self):
        payload = {
            "name": "Tafsir Center",
            "name_ar": "مركز التفسير",
            "description": "A leading Tafsir publisher",
            "description_ar": "ناشر رائد في التفسير",
            "address": "Riyadh, KSA",
            "website": "https://tafsir.center",
            "contact_email": "info@tafsir.center",
            "is_verified": True,
            "foundation_year": 2010,
            "country": "Saudi Arabia",
        }
        response = self.client.post("/portal/publishers/", payload, content_type="application/json")

        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Tafsir Center", body["name"])
        self.assertEqual("مركز التفسير", body["name_ar"])
        self.assertIn("slug", body)
        self.assertIn("id", body)
        self.assertIn("created_at", body)
        self.assertEqual(2010, body["foundation_year"])
        self.assertEqual("Saudi Arabia", body["country"])

    def test_create_publisher_where_only_name_provided_should_return_201_with_defaults(self):
        payload = {"name": "Simple Publisher"}
        response = self.client.post("/portal/publishers/", payload, content_type="application/json")

        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Simple Publisher", body["name"])
        self.assertTrue(body["is_verified"])
        self.assertEqual("", body["description"])

    def test_create_publisher_where_name_empty_should_return_400(self):
        payload = {"name": ""}
        response = self.client.post("/portal/publishers/", payload, content_type="application/json")

        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_name_required", body["error_name"])

    def test_create_publisher_where_duplicate_slug_should_return_400(self):
        baker.make(Publisher, name="Existing Publisher", slug="existing-publisher")
        payload = {"name": "Existing Publisher"}
        response = self.client.post("/portal/publishers/", payload, content_type="application/json")

        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_already_exists", body["error_name"])

    def test_create_publisher_where_translated_fields_provided_should_store_correctly(self):
        payload = {
            "name": "Translation Test",
            "name_ar": "اختبار الترجمة",
            "description_ar": "وصف بالعربية",
        }
        response = self.client.post("/portal/publishers/", payload, content_type="application/json")

        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("اختبار الترجمة", body["name_ar"])
        self.assertEqual("وصف بالعربية", body["description_ar"])

    def test_create_publisher_where_unauthenticated_should_return_401(self):
        self.authenticate_user(None)
        payload = {"name": "Unauthorized Test"}
        response = self.client.post("/portal/publishers/", payload, content_type="application/json")

        self.assertEqual(401, response.status_code, response.content)


class RetrievePublisherTest(BaseTestCase):
    def setUp(self):
        self.user = baker.make(User, email="admin@test.com", is_staff=True)
        self.authenticate_user(self.user)

    def test_retrieve_publisher_where_exists_should_return_200_with_all_fields(self):
        publisher = baker.make(
            Publisher,
            name="Tafsir Center",
            slug="tafsir-center",
            description="Test description",
            address="Riyadh",
            website="https://tafsir.center",
            contact_email="info@tafsir.center",
            is_verified=True,
            foundation_year=2010,
            country="Saudi Arabia",
        )
        response = self.client.get(f"/portal/publishers/{publisher.id}/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(publisher.id, body["id"])
        self.assertEqual("Tafsir Center", body["name"])
        self.assertEqual("tafsir-center", body["slug"])
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)
        self.assertIn("name_ar", body)
        self.assertIn("name_en", body)
        self.assertIn("description_ar", body)
        self.assertIn("description_en", body)
        self.assertEqual(2010, body["foundation_year"])
        self.assertEqual("Saudi Arabia", body["country"])

    def test_retrieve_publisher_where_not_found_should_return_404(self):
        response = self.client.get("/portal/publishers/99999/")

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_not_found", body["error_name"])

    def test_retrieve_publisher_where_unauthenticated_should_return_401(self):
        self.authenticate_user(None)
        publisher = baker.make(Publisher, name="Test")
        response = self.client.get(f"/portal/publishers/{publisher.id}/")

        self.assertEqual(401, response.status_code, response.content)

    def test_retrieve_publisher_where_has_translated_fields_should_include_them(self):
        publisher = baker.make(
            Publisher,
            name="English Name",
            name_ar="اسم عربي",
            description="English desc",
            description_ar="وصف عربي",
        )
        response = self.client.get(f"/portal/publishers/{publisher.id}/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("اسم عربي", body["name_ar"])
        self.assertEqual("وصف عربي", body["description_ar"])


class ListPublishersTest(BaseTestCase):
    def setUp(self):
        self.user = baker.make(User, email="admin@test.com", is_staff=True)
        self.authenticate_user(self.user)

    def test_list_publishers_where_no_filters_should_return_all_paginated(self):
        baker.make(Publisher, name="Publisher A", slug="publisher-a")
        baker.make(Publisher, name="Publisher B", slug="publisher-b")
        baker.make(Publisher, name="Publisher C", slug="publisher-c")

        response = self.client.get("/portal/publishers/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIn("results", body)
        self.assertIn("count", body)
        self.assertEqual(3, body["count"])
        self.assertEqual(3, len(body["results"]))

    def test_list_publishers_where_search_by_name_should_filter_results(self):
        baker.make(Publisher, name="Tafsir Center", slug="tafsir-center")
        baker.make(Publisher, name="Hadith Press", slug="hadith-press")

        response = self.client.get("/portal/publishers/?search=Tafsir")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertEqual("Tafsir Center", body["results"][0]["name"])

    def test_list_publishers_where_search_by_name_ar_should_filter_results(self):
        baker.make(Publisher, name="Arabic Publisher", name_ar="ناشر عربي", slug="arabic-pub")
        baker.make(Publisher, name="English Only", slug="english-only")

        response = self.client.get("/portal/publishers/?search=ناشر")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])

    def test_list_publishers_where_filter_is_verified_true_should_return_only_verified(self):
        baker.make(Publisher, name="Verified", slug="verified", is_verified=True)
        baker.make(Publisher, name="Unverified", slug="unverified", is_verified=False)

        response = self.client.get("/portal/publishers/?is_verified=true")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertTrue(body["results"][0]["is_verified"])

    def test_list_publishers_where_filter_country_should_filter_results(self):
        baker.make(Publisher, name="Saudi Pub", slug="saudi", country="Saudi Arabia")
        baker.make(Publisher, name="Egypt Pub", slug="egypt", country="Egypt")

        response = self.client.get("/portal/publishers/?country=Saudi Arabia")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])

    def test_list_publishers_where_page_2_should_return_correct_offset(self):
        for i in range(25):
            baker.make(Publisher, name=f"Publisher {i:02d}", slug=f"publisher-{i:02d}")

        response = self.client.get("/portal/publishers/?page=2&page_size=20")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(25, body["count"])
        self.assertEqual(5, len(body["results"]))

    def test_list_publishers_where_unauthenticated_should_return_401(self):
        self.authenticate_user(None)
        response = self.client.get("/portal/publishers/")

        self.assertEqual(401, response.status_code, response.content)


class UpdatePublisherTest(BaseTestCase):
    def setUp(self):
        self.user = baker.make(User, email="admin@test.com", is_staff=True)
        self.authenticate_user(self.user)

    def test_put_publisher_where_valid_data_should_return_200(self):
        publisher = baker.make(Publisher, name="Old Name", slug="old-name")
        payload = {
            "name": "New Name",
            "name_ar": "اسم جديد",
            "description": "Updated description",
        }
        response = self.client.put(
            f"/portal/publishers/{publisher.id}/", payload, content_type="application/json"
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("New Name", body["name"])
        self.assertEqual("اسم جديد", body["name_ar"])

    def test_put_publisher_where_not_found_should_return_404(self):
        payload = {"name": "Test"}
        response = self.client.put("/portal/publishers/99999/", payload, content_type="application/json")

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_not_found", body["error_name"])

    def test_patch_publisher_where_partial_data_should_update_only_provided_fields(self):
        publisher = baker.make(
            Publisher, name="Original", slug="original", description="Original desc", country="Egypt"
        )
        payload = {"country": "Saudi Arabia"}
        response = self.client.patch(
            f"/portal/publishers/{publisher.id}/", payload, content_type="application/json"
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Saudi Arabia", body["country"])
        self.assertEqual("Original", body["name"])
        self.assertEqual("Original desc", body["description"])

    def test_patch_publisher_where_name_changed_should_regenerate_slug(self):
        publisher = baker.make(Publisher, name="Old Name", slug="old-name")
        payload = {"name": "Brand New Name"}
        response = self.client.patch(
            f"/portal/publishers/{publisher.id}/", payload, content_type="application/json"
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Brand New Name", body["name"])
        self.assertEqual("brand-new-name", body["slug"])

    def test_patch_publisher_where_translated_fields_updated_should_persist(self):
        publisher = baker.make(Publisher, name="Test", slug="test", name_ar="قديم")
        payload = {"name_ar": "جديد", "description_ar": "وصف جديد"}
        response = self.client.patch(
            f"/portal/publishers/{publisher.id}/", payload, content_type="application/json"
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("جديد", body["name_ar"])
        self.assertEqual("وصف جديد", body["description_ar"])

    def test_update_publisher_where_unauthenticated_should_return_401(self):
        self.authenticate_user(None)
        publisher = baker.make(Publisher, name="Test")
        response = self.client.put(
            f"/portal/publishers/{publisher.id}/",
            {"name": "New"},
            content_type="application/json",
        )

        self.assertEqual(401, response.status_code, response.content)


class DeletePublisherTest(BaseTestCase):
    def setUp(self):
        self.user = baker.make(User, email="admin@test.com", is_staff=True)
        self.authenticate_user(self.user)

    def test_delete_publisher_where_exists_should_return_204(self):
        publisher = baker.make(Publisher, name="To Delete", slug="to-delete")
        response = self.client.delete(f"/portal/publishers/{publisher.id}/")

        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(Publisher.objects.filter(id=publisher.id).exists())

    def test_delete_publisher_where_not_found_should_return_404(self):
        response = self.client.delete("/portal/publishers/99999/")

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_not_found", body["error_name"])

    def test_delete_publisher_where_unauthenticated_should_return_401(self):
        self.authenticate_user(None)
        publisher = baker.make(Publisher, name="Test")
        response = self.client.delete(f"/portal/publishers/{publisher.id}/")

        self.assertEqual(401, response.status_code, response.content)

    def test_delete_publisher_where_has_resources_should_handle_gracefully(self):
        publisher = baker.make(Publisher, name="With Resources", slug="with-resources")
        response = self.client.delete(f"/portal/publishers/{publisher.id}/")

        self.assertEqual(204, response.status_code, response.content)
