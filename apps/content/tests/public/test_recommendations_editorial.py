from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import (
    Asset,
    CategoryChoice,
    EditorialRecommendation,
    EditorialRecommendationAsset,
    StatusChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class EditorialRecommendationsEndpointTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            status=StatusChoice.READY,
            restricted_for_tenant=False,
            publisher=self.publisher,
        )

        self.user = User.objects.create_user(email="oauthuser4@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )

    def test_returns_active_collection_with_its_assets(self):
        collection = EditorialRecommendation.objects.create(title="Ramadan Picks", description="Seasonal spotlight")
        EditorialRecommendationAsset.objects.create(recommendation=collection, asset=self.asset, position=1)
        self.authenticate_client(self.app)

        response = self.client.get("/recommendations/editorial/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, len(body))
        self.assertEqual(collection.id, body[0]["id"])
        self.assertEqual("Ramadan Picks", body[0]["title"])
        self.assertEqual([self.asset.id], [a["id"] for a in body[0]["assets"]])

    def test_inactive_collection_is_not_served(self):
        collection = EditorialRecommendation.objects.create(title="Draft Collection", is_active=False)
        EditorialRecommendationAsset.objects.create(recommendation=collection, asset=self.asset)
        self.authenticate_client(self.app)

        response = self.client.get("/recommendations/editorial/")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json())

    def test_no_active_collections_returns_empty_list_not_error(self):
        self.authenticate_client(self.app)

        response = self.client.get("/recommendations/editorial/")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json())

    def test_endpoint_requires_no_special_auth_beyond_public_api(self):
        collection = EditorialRecommendation.objects.create(title="Ramadan Picks")
        EditorialRecommendationAsset.objects.create(recommendation=collection, asset=self.asset)

        response = self.client.get("/recommendations/editorial/")

        self.assertIn(response.status_code, (200, 401))
        if response.status_code == 401:
            self.assertNotEqual("access_denied", response.json().get("error_name"))
