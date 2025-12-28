from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import Asset, Reciter, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.adapters import User


class RecitersListTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)

        # Valid resource/asset that should be counted
        self.recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.active_reciter = baker.make(Reciter, is_active=True, name="Active Reciter")

        self.valid_asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            reciter=self.active_reciter,
            resource=self.recitation_resource,
        )

        # Inactive reciter should NOT appear
        self.inactive_reciter = baker.make(Reciter, is_active=False, name="Inactive Reciter")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            reciter=self.inactive_reciter,
            resource=self.recitation_resource,
        )

        # Asset with non-RECITATION category should NOT be counted
        self.other_category_asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.TAFSIR,  # assuming another category exists
            reciter=self.active_reciter,
            resource=self.recitation_resource,
        )

        # Resource not READY should NOT be counted
        self.draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            reciter=self.active_reciter,
            resource=self.draft_resource,
        )

        # Resource with non-RECITATION category should NOT be counted
        self.other_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            reciter=self.active_reciter,
            resource=self.other_resource,
        )
        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )

    def test_list_reciters_should_return_only_active_reciters_with_ready_recitations(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/reciters/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        reciter_names = {item["name"] for item in items}

        self.assertIn("Active Reciter", reciter_names)
        self.assertNotIn("Inactive Reciter", reciter_names)

        # There should be exactly one reciter (the active one with at least one valid asset)
        self.assertEqual(1, len(items))

        reciter_item = items[0]
        self.assertEqual(self.active_reciter.id, reciter_item["id"])
        # Only the valid RECITATION asset with READY + RECITATION resource should be counted
        self.assertEqual(1, reciter_item["recitations_count"])

    def test_list_reciters_ordering_by_name(self):
        # Arrange – another active reciter so we can test ordering
        other_reciter = baker.make(Reciter, is_active=True, name="A Reciter")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            reciter=other_reciter,
            resource=self.recitation_resource,
        )
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/reciters/?ordering=name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)  # ascending by name
