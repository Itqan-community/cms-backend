from model_bakery import baker

from apps.content.models import Asset, Reciter, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationStatisticsTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher One")
        self.domain = baker.make(
            "publishers.Domain",
            domain="publisher1.com",
            publisher=self.publisher,
            is_primary=True,
        )

        self.reciter1 = baker.make(Reciter, name="Reciter One")
        self.reciter2 = baker.make(Reciter, name="Reciter Two")
        self.riwayah1 = baker.make(Riwayah)
        self.riwayah2 = baker.make(Riwayah)

        ready_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )

        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            resource=ready_resource,
            reciter=self.reciter1,
            riwayah=self.riwayah1,
        )
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            resource=ready_resource,
            reciter=self.reciter2,
            riwayah=self.riwayah2,
        )
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            resource=ready_resource,
            reciter=self.reciter1,
            riwayah=self.riwayah1,
        )

        # Should NOT be counted: draft resource
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            resource=draft_resource,
            reciter=baker.make(Reciter, name="Draft Reciter"),
            riwayah=baker.make(Riwayah),
        )
        # Should NOT be counted: different category
        baker.make(
            Asset,
            category=Resource.CategoryChoice.TAFSIR,
            resource=ready_resource,
        )

        self.user = User.objects.create_user(email="stats@example.com", name="Stats User")

    def test_statistics_returns_correct_counts(self):
        self.authenticate_user(self.user, domain=self.domain)
        response = self.client.get("/tenant/recitations/statistics/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(3, body["total_recitations"])
        self.assertEqual(2, body["total_reciters"])
        self.assertEqual(2, body["total_riwayahs"])

    def test_statistics_excludes_other_publishers(self):
        other_publisher = baker.make(Publisher, name="Other Publisher")
        other_domain = baker.make(
            "publishers.Domain",
            domain="other.com",
            publisher=other_publisher,
            is_primary=True,
        )
        other_resource = baker.make(
            Resource,
            publisher=other_publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            resource=other_resource,
            reciter=baker.make(Reciter, name="Other Reciter"),
            riwayah=baker.make(Riwayah),
        )

        self.authenticate_user(self.user, domain=self.domain)
        response = self.client.get("/tenant/recitations/statistics/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(3, body["total_recitations"])
        self.assertEqual(2, body["total_reciters"])
        self.assertEqual(2, body["total_riwayahs"])

    def test_statistics_returns_zeros_when_no_data(self):
        empty_publisher = baker.make(Publisher, name="Empty Publisher")
        empty_domain = baker.make(
            "publishers.Domain",
            domain="empty.com",
            publisher=empty_publisher,
            is_primary=True,
        )
        self.authenticate_user(self.user, domain=empty_domain)
        response = self.client.get("/tenant/recitations/statistics/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(0, body["total_recitations"])
        self.assertEqual(0, body["total_reciters"])
        self.assertEqual(0, body["total_riwayahs"])
