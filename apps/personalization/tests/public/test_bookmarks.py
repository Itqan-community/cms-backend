from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import Asset, Qiraah, Reciter, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.personalization.models import Bookmark
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


class BookmarkCreateTest(BaseTestCase):
    """Tests for POST /bookmarks/ endpoint."""

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="bm-user@example.com", is_active=True)
        self.app = Application.objects.create(
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App",
        )
        self.authenticate_client(self.app, self.user)
        self.asset, self.reciter = _make_recitation_asset("BM Asset")

    def test_create_bookmark_should_return_201(self):
        # Act
        response = self.client.post(
            "/bookmarks/",
            data={"asset_id": self.asset.id, "position_ms": 120000},
            format="json",
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual(self.asset.id, body["asset_id"])
        self.assertEqual(120000, body["position_ms"])
        self.assertEqual("BM Asset", body["asset_name"])

    def test_create_bookmark_with_surah_and_note_should_return_201(self):
        # Act
        response = self.client.post(
            "/bookmarks/",
            data={
                "asset_id": self.asset.id,
                "position_ms": 55000,
                "surah_number": 2,
                "note": "Beautiful recitation of Ayat al-Kursi",
            },
            format="json",
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual(2, body["surah_number"])
        self.assertEqual("Beautiful recitation of Ayat al-Kursi", body["note"])

    def test_create_bookmark_with_nonexistent_asset_should_return_404(self):
        # Act
        response = self.client.post(
            "/bookmarks/",
            data={"asset_id": 99999, "position_ms": 1000},
            format="json",
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_create_bookmark_with_negative_position_should_return_422(self):
        # Act
        response = self.client.post(
            "/bookmarks/",
            data={"asset_id": self.asset.id, "position_ms": -100},
            format="json",
        )

        # Assert
        self.assertIn(response.status_code, [400, 422], response.content)


class BookmarkListTest(BaseTestCase):
    """Tests for GET /bookmarks/ endpoint."""

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="bm-list@example.com", is_active=True)
        self.app = Application.objects.create(
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App",
        )
        self.authenticate_client(self.app, self.user)

    def test_list_bookmarks_empty_should_return_200(self):
        # Act
        response = self.client.get("/bookmarks/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(0, response.json()["count"])

    def test_list_bookmarks_should_return_user_bookmarks(self):
        # Arrange
        asset, _ = _make_recitation_asset("List Asset")

        self.client.post(
            "/bookmarks/",
            data={"asset_id": asset.id, "position_ms": 5000},
            format="json",
        )
        self.client.post(
            "/bookmarks/",
            data={"asset_id": asset.id, "position_ms": 10000, "surah_number": 3},
            format="json",
        )

        # Act
        response = self.client.get("/bookmarks/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(2, response.json()["count"])


class BookmarkDeleteTest(BaseTestCase):
    """Tests for DELETE /bookmarks/{id}/ endpoint."""

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="bm-del@example.com", is_active=True)
        self.app = Application.objects.create(
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App",
        )
        self.authenticate_client(self.app, self.user)
        self.asset, _ = _make_recitation_asset("Del Asset")

    def test_delete_bookmark_should_return_200(self):
        # Arrange
        response = self.client.post(
            "/bookmarks/",
            data={"asset_id": self.asset.id, "position_ms": 5000},
            format="json",
        )
        bookmark_id = response.json()["id"]

        # Act
        response = self.client.delete(f"/bookmarks/{bookmark_id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(Bookmark.objects.filter(id=bookmark_id).exists())

    def test_delete_nonexistent_bookmark_should_return_404(self):
        # Act
        response = self.client.delete("/bookmarks/99999/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_delete_other_users_bookmark_should_return_404(self):
        # Arrange — create bookmark as current user
        response = self.client.post(
            "/bookmarks/",
            data={"asset_id": self.asset.id, "position_ms": 5000},
            format="json",
        )
        bookmark_id = response.json()["id"]

        # Switch to another user
        user2 = baker.make(User, email="bm-other@example.com", is_active=True)
        app2 = Application.objects.create(
            user=user2,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App 2",
        )
        self.authenticate_client(app2, user2)

        # Act — try to delete the other user's bookmark
        response = self.client.delete(f"/bookmarks/{bookmark_id}/")

        # Assert — should not find it because of user filter
        self.assertEqual(404, response.status_code, response.content)
        # Original bookmark should still exist
        self.assertTrue(Bookmark.objects.filter(id=bookmark_id).exists())
