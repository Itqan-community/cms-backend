from model_bakery import baker

from apps.content.models import Asset, Reciter, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher


class RecitationsListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")
        self.reciter1 = baker.make(Reciter, name="Reciter One")
        self.reciter2 = baker.make(Reciter, name="Reciter Two")
        self.riwayah1 = baker.make(Riwayah)
        self.riwayah2 = baker.make(Riwayah)

        self.ready_recitation_resource_pub1 = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.ready_recitation_resource_pub2 = baker.make(
            Resource,
            publisher=self.publisher2,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.draft_recitation_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        self.other_category_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )

        # Valid assets that should be returned
        self.asset1 = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource_pub1,
            reciter=self.reciter1,
            riwayah=self.riwayah1,
            name="First Recitation",
            description="Beautiful recitation",
        )
        self.asset2 = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource_pub2,
            reciter=self.reciter2,
            riwayah=self.riwayah2,
            name="Second Recitation",
            description="Calm recitation",
        )

        # Assets that should NOT be returned
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.draft_recitation_resource,
            reciter=self.reciter1,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.other_category_resource,
            reciter=self.reciter1,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.TAFSIR,
            resource=self.ready_recitation_resource_pub1,
            reciter=self.reciter1,
        )

    def test_list_recitations_should_return_only_ready_recitation_assets(self):
        response = self.client.get("/recitations/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        # Only two valid assets should be returned
        self.assertEqual(2, len(items))
        returned_ids = {item["id"] for item in items}
        self.assertIn(self.asset1.id, returned_ids)
        self.assertIn(self.asset2.id, returned_ids)

        # Check required fields
        for item in items:
            self.assertIn("id", item)
            self.assertIn("resource_id", item)
            self.assertIn("name", item)
            self.assertIn("slug", item)
            self.assertIn("description", item)
            self.assertIn("created_at", item)
            self.assertIn("updated_at", item)

    def test_list_recitations_filter_by_publisher(self):
        response = self.client.get(f"/recitations/?publisher_id={self.publisher1.id}")

        self.assertEqual(200, response.status_code)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])
        self.assertEqual(self.ready_recitation_resource_pub1.id, items[0]["resource_id"])

    def test_list_recitations_filter_by_reciter(self):
        response = self.client.get(f"/recitations/?reciter_id={self.reciter2.id}")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.asset2.id, items[0]["id"])

    def test_list_recitations_filter_by_riwayah(self):
        response = self.client.get(f"/recitations/?riwayah_id={self.riwayah1.id}")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

    def test_list_recitations_search_should_match_name_description_publisher_or_reciter(self):
        # Search by part of description
        response = self.client.get("/recitations/?search=Beautiful")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

        # Search by reciter name
        response = self.client.get("/recitations/?search=Reciter Two")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset2.id, items[0]["id"])

    def test_list_recitations_ordering_by_name(self):
        response = self.client.get("/recitations/?ordering=name")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)
