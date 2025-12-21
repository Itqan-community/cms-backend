from model_bakery import baker

from apps.content.models import Asset, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher


class RiwayahsListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)

        self.recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )

        self.active_riwayah = baker.make(Riwayah, is_active=True, name="Active Riwayah")
        self.valid_asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah,
            resource=self.recitation_resource,
        )

        # Inactive riwayah – should not appear
        self.inactive_riwayah = baker.make(Riwayah, is_active=False, name="Inactive Riwayah")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.inactive_riwayah,
            resource=self.recitation_resource,
        )

        # Asset with non-RECITATION category – should not count
        baker.make(
            Asset,
            category=Asset.CategoryChoice.TAFSIR,
            riwayah=self.active_riwayah,
            resource=self.recitation_resource,
        )

        # Resource not READY – should not count
        draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah,
            resource=draft_resource,
        )

        # Resource not RECITATION – should not count
        tafsir_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah,
            resource=tafsir_resource,
        )

    def test_list_riwayahs_should_return_only_active_with_ready_recitations(self):
        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        riwayah_names = {item["name"] for item in items}

        self.assertIn("Active Riwayah", riwayah_names)
        self.assertNotIn("Inactive Riwayah", riwayah_names)
        self.assertEqual(1, len(items))

        riwayah_item = items[0]
        self.assertEqual(self.active_riwayah.id, riwayah_item["id"])
        self.assertEqual(1, riwayah_item["recitations_count"])

    def test_list_riwayahs_ordering_by_name(self):
        other_riwayah = baker.make(Riwayah, is_active=True, name="A Riwayah")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=other_riwayah,
            resource=self.recitation_resource,
        )

        response = self.client.get("/riwayahs/?ordering=name")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)
