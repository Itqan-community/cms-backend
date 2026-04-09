from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class PublisherFiltersTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One", name_ar="ناشر واحد")
        self.publisher2 = baker.make(Publisher, name="Publisher Two", name_ar="ناشر اثنين")
        self.publisher3 = baker.make(Publisher, name="Other Publisher", name_ar="ناشر آخر")

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_list_publishers_for_filter_returns_all(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/filters/publishers/")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Should return a paginated list with all publishers
        self.assertIn("results", body)
        self.assertEqual(3, len(body["results"]))

        # Each item should have id and name
        for item in body["results"]:
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertIsNotNone(item["id"])
            self.assertIsNotNone(item["name"])

    def test_list_publishers_for_filter_search_by_name(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/filters/publishers/?search=Publisher%20One")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Should return only matching publishers
        self.assertEqual(1, len(body["results"]))
        self.assertEqual(self.publisher1.id, body["results"][0]["id"])
        self.assertEqual("Publisher One", body["results"][0]["name"])

    def test_list_publishers_for_filter_search_by_name_ar(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/filters/publishers/?search=ناشر%20واحد")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Should find by Arabic name
        self.assertEqual(1, len(body["results"]))
        self.assertEqual(self.publisher1.id, body["results"][0]["id"])

    def test_list_publishers_for_filter_pagination(self):
        self.authenticate_user(self.user)
        # Create more publishers
        for i in range(15):
            baker.make(Publisher, name=f"Publisher {i}")

        response = self.client.get("/portal/filters/publishers/?page=1&page_size=10")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Should be paginated with max 10 items per page
        self.assertLessEqual(len(body["results"]), 10)
        self.assertIn("count", body)
        # Total count should be greater than initial 3
        self.assertGreater(body["count"], 3)

    def test_list_publishers_for_filter_ordered_by_name(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/filters/publishers/")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Should return publishers ordered by name
        names = [item["name"] for item in body["results"]]
        self.assertEqual(sorted(names), names)
