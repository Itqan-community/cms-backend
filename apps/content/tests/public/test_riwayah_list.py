from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import Asset, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RiwayahsListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.reciter = baker.make("content.Reciter", name="Test Reciter")
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
            reciter=self.reciter,
        )

        # Inactive riwayah – should not appear
        self.inactive_riwayah = baker.make(Riwayah, is_active=False, name="Inactive Riwayah")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.inactive_riwayah,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Asset with non-RECITATION category – should not count
        baker.make(
            Asset,
            category=Asset.CategoryChoice.TAFSIR,
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
            reciter=self.reciter,
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
            reciter=self.reciter,
        )
        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )

    def test_list_riwayahs_should_return_only_active_with_ready_recitations(self):
        # Arrange
        self.authenticate_client(self.app)

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
        # Arrange
        self.authenticate_client(self.app)
        other_riwayah = baker.make(Riwayah, is_active=True, name="A Riwayah")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=other_riwayah,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Act
        response = self.client.get("/riwayahs/?ordering=name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)
