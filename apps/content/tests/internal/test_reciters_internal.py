from model_bakery import baker

from apps.content.models import Reciter, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher


class InternalRecitersApiTest(BaseTestCase):
    def test_list_reciters_returns_only_reciters_with_ready_recitations_for_publisher(self):
        # Arrange
        publisher = baker.make(Publisher)
        other_publisher = baker.make(Publisher)

        # Reciter with READY recitation asset for current tenant's publisher
        reciter_ok = baker.make(Reciter, is_active=True, name="Active Reciter")
        baker.make(
            "content.Asset",
            reciter=reciter_ok,
            category=Resource.CategoryChoice.RECITATION,
            resource__publisher=publisher,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
        )

        # Reciter with READY recitation but for another publisher (should be filtered out)
        reciter_other_publisher = baker.make(Reciter, is_active=True, name="Other Publisher Reciter")
        baker.make(
            "content.Asset",
            reciter=reciter_other_publisher,
            category=Resource.CategoryChoice.RECITATION,
            resource__publisher=other_publisher,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
        )

        # Reciter without READY recitation asset (should be filtered out)
        reciter_no_ready = baker.make(Reciter, is_active=True, name="No Ready Reciter")
        baker.make(
            "content.Asset",
            reciter=reciter_no_ready,
            category=Resource.CategoryChoice.RECITATION,
            resource__publisher=publisher,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.DRAFT,
        )

        self.authenticate_user()
        # Act
        response = self.client.get("/cms-api/reciters/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(reciter_ok.id, items[0]["id"])
        self.assertEqual(reciter_ok.name, items[0]["name"])
        self.assertEqual(1, items[0]["recitations_count"])

    def test_search_reciters_matches_arabic_and_slug(self):
        # Arrange
        publisher = baker.make(Publisher)

        reciter_arabic = baker.make(Reciter, is_active=True, name="Mishary", slug="mishary", name_ar="مشاري راشد العفاسي")

        baker.make(
            "content.Asset",
            reciter=reciter_arabic,
            category=Resource.CategoryChoice.RECITATION,
            resource__publisher=publisher,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
        )

        # Another reciter that should not match the search
        reciter_other = baker.make(Reciter, is_active=True, name="Other Reciter", slug="other-reciter")
        baker.make(
            "content.Asset",
            reciter=reciter_other,
            category=Resource.CategoryChoice.RECITATION,
            resource__publisher=publisher,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
        )

        self.authenticate_user()
        # Act: search by Arabic fragment
        response = self.client.get("/cms-api/reciters/", data={"search": "مشاري"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(reciter_arabic.id, items[0]["id"])

    def test_ordering_by_name_and_name_ar_supported(self):
        # Arrange
        publisher = baker.make(Publisher)

        reciter_b = baker.make(Reciter, is_active=True, name="B Reciter", name_ar="ب")
        baker.make(
            "content.Asset",
            reciter=reciter_b,
            category=Resource.CategoryChoice.RECITATION,
            resource__publisher=publisher,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
        )

        reciter_a = baker.make(Reciter, is_active=True, name="A Reciter", name_ar="ا")
        baker.make(
            "content.Asset",
            reciter=reciter_a,
            category=Resource.CategoryChoice.RECITATION,
            resource__publisher=publisher,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
        )

        self.authenticate_user()
        # Act & Assert: order by name
        response = self.client.get("/cms-api/reciters/", data={"ordering": "name"}, format="json")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(["A Reciter", "B Reciter"], [item["name"] for item in items])

        # Act & Assert: order by name_ar
        response = self.client.get("/cms-api/reciters/", data={"ordering": "name_ar"}, format="json")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(["A Reciter", "B Reciter"], [item["name"] for item in items])

