from model_bakery import baker

from apps.content.models import Asset, AssetVersion, CategoryChoice, Qiraah, Reciter, Riwayah, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationPortalTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.reciter = baker.make(Reciter, name="Test Reciter")
        self.qiraah = baker.make(Qiraah, name="Test Qiraah")
        self.riwayah = baker.make(Riwayah, name="Test Riwayah", qiraah=self.qiraah)

        self.user = User.objects.create_user(email="admin@example.com", name="Admin User")

    def test_list_recitations_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_RECITATION)
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Recitation 1",
        )

        # Act
        response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))

    def test_filter_recitations_by_publisher_should_return_filtered_results(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_RECITATION)
        pub2 = baker.make(Publisher, name="Other Publisher")
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Recitation 1",
        )
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=pub2,
            status=StatusChoice.READY,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Recitation 2",
        )

        # Act
        response = self.client.get(f"/portal/recitations/?publisher_id={self.publisher.id}")

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()["results"]))
        self.assertEqual("Recitation 1", response.json()["results"][0]["name"])

    def test_sort_recitations_by_reciter_name_should_return_sorted_results(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_RECITATION)
        reciter_a = baker.make(Reciter, name="A Reciter")
        reciter_z = baker.make(Reciter, name="Z Reciter")

        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=reciter_z,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Z Asset",
        )
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=reciter_a,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="A Asset",
        )

        # Act
        response = self.client.get("/portal/recitations/?ordering=reciter_name")

        # Assert
        self.assertEqual(200, response.status_code)
        items = response.json()["results"]
        self.assertEqual("A Asset", items[0]["name"])
        self.assertEqual("Z Asset", items[1]["name"])

    def test_create_recitation_should_return_201(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_RECITATION)
        payload = {
            "name_ar": "تلاوة جديدة",
            "name_en": "New Recitation",
            "description_ar": "وصف التلاوة",
            "description_en": "Recitation description",
            "publisher_id": self.publisher.id,
            "reciter_id": self.reciter.id,
            "qiraah_id": self.qiraah.id,
            "riwayah_id": self.riwayah.id,
            "madd_level": "twassut",
            "meem_behaviour": "silah",
            "year": 2024,
            "license": "CC0",
        }

        # Act
        response = self.client.post("/portal/recitations/", data=payload, content_type="application/json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("تلاوة جديدة", body["name_ar"])
        self.assertEqual("New Recitation", body["name_en"])
        self.assertEqual("twassut", body["madd_level"])
        self.assertEqual("silah", body["meem_behaviour"])
        self.assertEqual(2024, body["year"])

        # Verify DB
        asset = Asset.objects.get(id=body["id"])
        self.assertEqual(self.publisher.id, asset.publisher_id)
        self.assertEqual(self.reciter.id, asset.reciter_id)

    def test_update_recitation_put_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_RECITATION)
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Old Name",
            madd_level="qasr",
        )

        payload = {
            "name_ar": "تلاوة محدثة",
            "name_en": "Updated Recitation",
            "description_ar": "وصف محدث",
            "description_en": "Updated description",
            "publisher_id": self.publisher.id,
            "reciter_id": self.reciter.id,
            "qiraah_id": self.qiraah.id,
            "riwayah_id": self.riwayah.id,
            "madd_level": "twassut",
            "meem_behaviour": "skoun",
            "year": 2025,
            "license": "CC-BY",
        }

        # Act
        response = self.client.put(f"/portal/recitations/{asset.slug}/", data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("twassut", body["madd_level"])
        self.assertEqual("skoun", body["meem_behaviour"])
        self.assertEqual(2025, body["year"])
        self.assertEqual("CC-BY", body["license"])

    def test_delete_recitation_should_return_204(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_RECITATION)
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
        )
        asset_id = asset.id

        # Act
        response = self.client.delete(f"/portal/recitations/{asset.slug}/")

        # Assert
        self.assertEqual(204, response.status_code)
        self.assertFalse(Asset.objects.filter(id=asset_id).exists())

    def test_retrieve_recitation_where_version_exists_should_return_ayah_timings_url(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_RECITATION)
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
        )

        baker.make(
            AssetVersion,
            asset=asset,
            file_url=self.create_file("test.json", b'{"data": "test"}', "application/json"),
        )

        # Act
        response = self.client.get(f"/portal/recitations/{asset.slug}/")

        # Assert
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertIsNotNone(body["ayah_timings_url"])
        self.assertIn("test.json", body["ayah_timings_url"])

    def test_retrieve_recitation_where_no_version_exists_should_return_none_ayah_timings_url(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_RECITATION)
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
        )

        # Act
        response = self.client.get(f"/portal/recitations/{asset.slug}/")

        # Assert
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertIsNone(body["ayah_timings_url"])

    def test_list_recitations_where_unauthenticated_should_return_401(self):
        # Arrange
        # No authentication

        # Act
        response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_error", response.json()["error_name"])

    def test_list_recitations_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(email="noperm@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_create_recitation_where_unauthenticated_should_return_401(self):
        # Arrange
        # No authentication

        # Act
        response = self.client.post("/portal/recitations/", data={}, content_type="application/json")

        # Assert
        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_error", response.json()["error_name"])

    def test_create_recitation_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(email="noperm2@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.post(
            "/portal/recitations/",
            data={
                "reciter_id": self.reciter.id,
                "publisher_id": self.publisher.id,
                "license": "CC-BY",
            },
            content_type="application/json",
        )

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_update_recitation_where_unauthenticated_should_return_401(self):
        # Arrange
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
        )

        # Act
        response = self.client.patch(f"/portal/recitations/{asset.slug}/", data={}, content_type="application/json")

        # Assert
        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_error", response.json()["error_name"])

    def test_update_recitation_where_user_lacks_permission_should_return_403(self):
        # Arrange
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
        )
        user_without_permission = User.objects.create_user(email="noperm3@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.patch(f"/portal/recitations/{asset.slug}/", data={}, content_type="application/json")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_delete_recitation_where_unauthenticated_should_return_401(self):
        # Arrange
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
        )

        # Act
        response = self.client.delete(f"/portal/recitations/{asset.slug}/")

        # Assert
        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_error", response.json()["error_name"])

    def test_delete_recitation_where_user_lacks_permission_should_return_403(self):
        # Arrange
        asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
        )
        user_without_permission = User.objects.create_user(email="noperm4@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.delete(f"/portal/recitations/{asset.slug}/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
