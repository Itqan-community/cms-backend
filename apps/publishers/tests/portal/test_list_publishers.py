from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class ListPublishersTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)
        self.url = "/portal/publishers/"

    def test_list_publishers_where_no_filters_should_return_all_paginated(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Publisher, name="Publisher A", slug="publisher-a")
        baker.make(Publisher, name="Publisher B", slug="publisher-b")
        baker.make(Publisher, name="Publisher C", slug="publisher-c")

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(3, body["total"])
        self.assertEqual(3, len(body["results"]))

    def test_list_publishers_where_search_by_name_should_filter_results(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Publisher, name="Tafsir Center", slug="tafsir-center")
        baker.make(Publisher, name="Hadith Press", slug="hadith-press")

        # Act
        response = self.client.get(self.url, {"search": "Tafsir"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["total"])
        self.assertEqual("Tafsir Center", body["results"][0]["name"])

    def test_list_publishers_where_search_by_name_ar_should_filter_results(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Publisher, name="Tafsir Center", name_ar="مركز التفسير", slug="tafsir-center")
        baker.make(Publisher, name="Hadith Press", name_ar="دار الحديث", slug="hadith-press")

        # Act
        response = self.client.get(self.url, {"search": "التفسير"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["total"])
        self.assertEqual("Tafsir Center", body["results"][0]["name"])

    def test_list_publishers_where_search_by_description_should_filter_results(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Publisher, name="Tafsir Pub", slug="tafsir-pub", description="Specializes in Quran exegesis")
        baker.make(Publisher, name="Hadith Pub", slug="hadith-pub", description="Hadith collections")

        # Act
        response = self.client.get(self.url, {"search": "exegesis"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["total"])
        self.assertEqual("Tafsir Pub", body["results"][0]["name"])

    def test_list_publishers_where_filter_is_verified_true_should_return_only_verified(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Publisher, name="Verified Pub", slug="verified-pub", is_verified=True)
        baker.make(Publisher, name="Unverified Pub", slug="unverified-pub", is_verified=False)

        # Act
        response = self.client.get(self.url, {"is_verified": "true"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["total"])
        self.assertEqual("Verified Pub", body["results"][0]["name"])

    def test_list_publishers_where_filter_country_should_filter_results(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Publisher, name="Saudi Pub", slug="saudi-pub", country="Saudi Arabia")
        baker.make(Publisher, name="Egypt Pub", slug="egypt-pub", country="Egypt")

        # Act
        response = self.client.get(self.url, {"country": "Saudi Arabia"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["total"])
        self.assertEqual("Saudi Pub", body["results"][0]["name"])

    def test_list_publishers_where_page_2_should_return_correct_offset(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        for i in range(25):
            baker.make(Publisher, name=f"Publisher {i:02d}", slug=f"publisher-{i:02d}")

        # Act
        response = self.client.get(self.url, {"page": 2, "page_size": 20})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(25, body["total"])
        self.assertEqual(5, len(body["results"]))

    def test_list_publishers_where_unauthenticated_should_return_401(self) -> None:
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(401, response.status_code, response.content)
