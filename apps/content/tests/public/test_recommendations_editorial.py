from django.db import connection
from django.test.utils import CaptureQueriesContext
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
            category=CategoryChoice.PROGRAM,
            status=StatusChoice.READY,
            in_public_api=True,
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

    def test_get_editorial_recommendations_where_collection_has_many_assets_should_not_query_per_asset(self):
        # Arrange
        collection = EditorialRecommendation.objects.create(title="Ramadan Picks")
        EditorialRecommendationAsset.objects.create(recommendation=collection, asset=self.asset, position=0)
        self.client.get("/recommendations/editorial/")  # warm up per-process lookups
        with CaptureQueriesContext(connection) as one_asset:
            self.client.get("/recommendations/editorial/")
        for position in range(1, 6):
            extra = baker.make(
                Asset,
                category=CategoryChoice.PROGRAM,
                status=StatusChoice.READY,
                in_public_api=True,
                publisher=self.publisher,
            )
            EditorialRecommendationAsset.objects.create(recommendation=collection, asset=extra, position=position)

        # Act
        with CaptureQueriesContext(connection) as six_assets:
            response = self.client.get("/recommendations/editorial/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(6, len(response.json()[0]["assets"]))
        self.assertEqual(len(one_asset), len(six_assets))

    def test_get_editorial_recommendations_where_asset_has_no_visible_language_should_leave_it_out(self):
        # Arrange - a mushaf is listed only while one of its languages is READY and published
        hidden_mushaf = baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            status=StatusChoice.READY,
            in_public_api=True,
            publisher=self.publisher,
        )
        collection = EditorialRecommendation.objects.create(title="Ramadan Picks")
        EditorialRecommendationAsset.objects.create(recommendation=collection, asset=self.asset, position=1)
        EditorialRecommendationAsset.objects.create(recommendation=collection, asset=hidden_mushaf, position=2)

        # Act
        response = self.client.get("/recommendations/editorial/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.asset.id], [a["id"] for a in response.json()[0]["assets"]])

    def test_get_editorial_recommendations_where_every_asset_is_hidden_should_omit_the_collection(self):
        # Arrange
        hidden_mushaf = baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            status=StatusChoice.READY,
            in_public_api=True,
            publisher=self.publisher,
        )
        collection = EditorialRecommendation.objects.create(title="Hidden only")
        EditorialRecommendationAsset.objects.create(recommendation=collection, asset=hidden_mushaf)

        # Act
        response = self.client.get("/recommendations/editorial/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json())
