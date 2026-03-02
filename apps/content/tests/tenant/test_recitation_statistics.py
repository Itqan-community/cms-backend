from unittest.mock import patch

from model_bakery import baker

from apps.content.models import Asset, Qiraah, Reciter, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationStatisticsTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher One")
        self.domain = baker.make(
            "publishers.Domain",
            domain="stats-test.com",
            publisher=self.publisher,
            is_primary=True,
        )
        self.user = User.objects.create_user(email="stats@example.com", name="Stats User")

    def _make_ready_resource(self, publisher=None):
        return baker.make(
            Resource,
            publisher=publisher or self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )

    def _make_recitation_asset(self, resource, reciter, riwayah=None, qiraah=None):
        return baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            resource=resource,
            reciter=reciter,
            riwayah=riwayah,
            qiraah=qiraah,
        )

    def test_statistics_returns_correct_counts(self):
        qiraah = baker.make(Qiraah, name="Qiraah Asim")
        riwayah1 = baker.make(Riwayah, qiraah=qiraah)
        riwayah2 = baker.make(Riwayah, qiraah=qiraah)
        reciter1 = baker.make(Reciter, name="Reciter A", is_active=True)
        reciter2 = baker.make(Reciter, name="Reciter B", is_active=True)
        resource = self._make_ready_resource()

        # 3 recitations, 2 reciters, 2 riwayahs
        self._make_recitation_asset(resource, reciter1, riwayah1, qiraah)
        self._make_recitation_asset(resource, reciter1, riwayah2, qiraah)
        self._make_recitation_asset(resource, reciter2, riwayah1, qiraah)

        self.authenticate_user(self.user, domain=self.domain)
        response = self.client.get("/tenant/recitation-statistics/")

        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertEqual(3, data["total_recitations"])
        self.assertEqual(2, data["total_reciters"])
        self.assertEqual(2, data["total_riwayahs"])

    def test_statistics_excludes_draft_resources(self):
        reciter = baker.make(Reciter, name="Reciter X", is_active=True)
        riwayah = baker.make(Riwayah)

        ready_resource = self._make_ready_resource()
        draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )

        self._make_recitation_asset(ready_resource, reciter, riwayah)
        self._make_recitation_asset(draft_resource, reciter, riwayah)

        self.authenticate_user(self.user, domain=self.domain)
        response = self.client.get("/tenant/recitation-statistics/")

        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        # Only the READY resource asset should count
        self.assertEqual(1, data["total_recitations"])

    def test_statistics_scoped_to_publisher(self):
        other_publisher = baker.make(Publisher, name="Other Publisher")
        reciter = baker.make(Reciter, name="Reciter Y", is_active=True)
        riwayah = baker.make(Riwayah)

        my_resource = self._make_ready_resource(self.publisher)
        other_resource = self._make_ready_resource(other_publisher)

        self._make_recitation_asset(my_resource, reciter, riwayah)
        self._make_recitation_asset(other_resource, reciter, riwayah)

        self.authenticate_user(self.user, domain=self.domain)
        response = self.client.get("/tenant/recitation-statistics/")

        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertEqual(1, data["total_recitations"])

    def test_statistics_empty_when_no_recitations(self):
        self.authenticate_user(self.user, domain=self.domain)
        response = self.client.get("/tenant/recitation-statistics/")

        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertEqual(0, data["total_recitations"])
        self.assertEqual(0, data["total_reciters"])
        self.assertEqual(0, data["total_riwayahs"])

    def test_statistics_are_cached(self):
        reciter = baker.make(Reciter, name="Reciter Z", is_active=True)
        riwayah = baker.make(Riwayah)
        resource = self._make_ready_resource()
        self._make_recitation_asset(resource, reciter, riwayah)

        self.authenticate_user(self.user, domain=self.domain)

        # First call populates cache
        response1 = self.client.get("/tenant/recitation-statistics/")
        self.assertEqual(200, response1.status_code)

        # Second call should return same data from cache
        with patch(
            "apps.content.repositories.recitation.RecitationRepository.get_recitation_statistics"
        ) as mock_stats:
            response2 = self.client.get("/tenant/recitation-statistics/")
            self.assertEqual(200, response2.status_code)
            # The repo method should NOT be called — cache should serve the response
            mock_stats.assert_not_called()

        self.assertEqual(response1.json(), response2.json())

    def test_statistics_response_shape(self):
        self.authenticate_user(self.user, domain=self.domain)
        response = self.client.get("/tenant/recitation-statistics/")

        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertIn("total_recitations", data)
        self.assertIn("total_reciters", data)
        self.assertIn("total_riwayahs", data)
        self.assertEqual(3, len(data))
