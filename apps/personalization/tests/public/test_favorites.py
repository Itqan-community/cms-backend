from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import Asset, Qiraah, Reciter, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.personalization.models import Favorite
from apps.publishers.models import Publisher
from apps.users.models import User


def _make_recitation_asset(name="Test Asset"):
    """Helper to create a valid recitation Asset with all required FK fields."""
    publisher = baker.make(Publisher)
    resource = baker.make(Resource, publisher=publisher, category="recitation", status="ready")
    reciter = baker.make(Reciter, name=f"{name} Reciter", is_active=True)
    qiraah = baker.make(Qiraah, name=f"{name} Qiraah", is_active=True)
    riwayah = baker.make(Riwayah, qiraah=qiraah, name=f"{name} Riwayah", is_active=True)
    asset = baker.make(
        Asset,
        resource=resource,
        name=name,
        category="recitation",
        reciter=reciter,
        qiraah=qiraah,
        riwayah=riwayah,
    )
    return asset, reciter


class FavoriteToggleTest(BaseTestCase):
    """Tests for POST /favorites/toggle/ endpoint."""

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="fav-user@example.com", is_active=True)
        self.app = Application.objects.create(
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App",
        )
        self.authenticate_client(self.app, self.user)

        self.reciter = baker.make(Reciter, name="Test Reciter", is_active=True)

    def test_toggle_favorite_add_should_return_201(self):
        # Act
        response = self.client.post(
            "/favorites/toggle/",
            data={"content_type": "reciter", "object_id": self.reciter.id},
            format="json",
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("added", body["action"])
        self.assertEqual(1, body["favorite_count"])
        self.assertTrue(Favorite.objects.filter(user=self.user, object_id=self.reciter.id).exists())

    def test_toggle_favorite_remove_should_return_200(self):
        # Arrange — first add a favorite
        self.client.post(
            "/favorites/toggle/",
            data={"content_type": "reciter", "object_id": self.reciter.id},
            format="json",
        )

        # Act — toggle again to remove
        response = self.client.post(
            "/favorites/toggle/",
            data={"content_type": "reciter", "object_id": self.reciter.id},
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("removed", body["action"])
        self.assertEqual(0, body["favorite_count"])
        self.assertFalse(Favorite.objects.filter(user=self.user, object_id=self.reciter.id).exists())

    def test_toggle_favorite_with_invalid_content_type_should_return_422(self):
        # Act
        response = self.client.post(
            "/favorites/toggle/",
            data={"content_type": "invalid_type", "object_id": 1},
            format="json",
        )

        # Assert — Pydantic validation catches the invalid Literal value
        self.assertIn(response.status_code, [400, 422], response.content)

    def test_toggle_favorite_with_nonexistent_object_should_return_404(self):
        # Act
        response = self.client.post(
            "/favorites/toggle/",
            data={"content_type": "reciter", "object_id": 99999},
            format="json",
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_toggle_favorite_on_asset_should_work(self):
        # Arrange
        asset, _ = _make_recitation_asset("Fav Asset")

        # Act
        response = self.client.post(
            "/favorites/toggle/",
            data={"content_type": "asset", "object_id": asset.id},
            format="json",
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("added", response.json()["action"])

    def test_favorite_count_reflects_multiple_users(self):
        # Arrange — another user favorites the same reciter
        user2 = baker.make(User, email="fav-user2@example.com", is_active=True)
        app2 = Application.objects.create(
            user=user2,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App 2",
        )

        # User 1 favorites
        self.client.post(
            "/favorites/toggle/",
            data={"content_type": "reciter", "object_id": self.reciter.id},
            format="json",
        )

        # User 2 favorites
        self.authenticate_client(app2, user2)
        response = self.client.post(
            "/favorites/toggle/",
            data={"content_type": "reciter", "object_id": self.reciter.id},
            format="json",
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual(2, response.json()["favorite_count"])


class FavoriteListTest(BaseTestCase):
    """Tests for GET /favorites/ endpoint."""

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="fav-list@example.com", is_active=True)
        self.app = Application.objects.create(
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App",
        )
        self.authenticate_client(self.app, self.user)

    def test_list_favorites_empty_should_return_200(self):
        # Act
        response = self.client.get("/favorites/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(0, body["count"])
        self.assertEqual([], body["results"])

    def test_list_favorites_should_return_user_favorites(self):
        # Arrange
        reciter1 = baker.make(Reciter, name="Reciter 1", is_active=True)
        reciter2 = baker.make(Reciter, name="Reciter 2", is_active=True)

        self.client.post(
            "/favorites/toggle/",
            data={"content_type": "reciter", "object_id": reciter1.id},
            format="json",
        )
        self.client.post(
            "/favorites/toggle/",
            data={"content_type": "reciter", "object_id": reciter2.id},
            format="json",
        )

        # Act
        response = self.client.get("/favorites/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(2, body["count"])

    def test_list_favorites_filter_by_content_type(self):
        # Arrange
        reciter = baker.make(Reciter, name="Reciter", is_active=True)
        publisher = baker.make(Publisher)
        resource = baker.make(Resource, publisher=publisher, category="recitation", status="ready")

        self.client.post(
            "/favorites/toggle/",
            data={"content_type": "reciter", "object_id": reciter.id},
            format="json",
        )
        self.client.post(
            "/favorites/toggle/",
            data={"content_type": "resource", "object_id": resource.id},
            format="json",
        )

        # Act — filter for reciters only
        response = self.client.get("/favorites/?content_type=reciter")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertEqual("reciter", body["results"][0]["content_type"])

    def test_list_favorites_should_not_return_other_users_favorites(self):
        # Arrange — another user creates favorites
        user2 = baker.make(User, email="other-fav@example.com", is_active=True)
        reciter = baker.make(Reciter, name="Someone Else Reciter", is_active=True)
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(Reciter)
        Favorite.objects.create(user=user2, content_type=ct, object_id=reciter.id)

        # Act
        response = self.client.get("/favorites/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(0, response.json()["count"])
