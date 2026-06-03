from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, Qiraah, Reciter, Riwayah, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


class PortalPublisherScopingTest(BaseTestCase):
    """End-to-end coverage that /portal endpoints filter by user's publisher memberships."""

    def setUp(self) -> None:
        super().setUp()
        # Arrange: two publishers and one recitation under each
        self.publisher_a = baker.make(Publisher, name="Publisher A")
        self.publisher_b = baker.make(Publisher, name="Publisher B")
        reciter = baker.make(Reciter, name="Reciter X")
        qiraah = baker.make(Qiraah, name="Qiraah X")
        riwayah = baker.make(Riwayah, name="Riwayah X", qiraah=qiraah)

        self.recitation_a = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            status=StatusChoice.READY,
            publisher=self.publisher_a,
            reciter=reciter,
            qiraah=qiraah,
            riwayah=riwayah,
            name="Recitation A",
            slug="recitation-a",
        )
        self.recitation_b = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            status=StatusChoice.READY,
            publisher=self.publisher_b,
            reciter=reciter,
            qiraah=qiraah,
            riwayah=riwayah,
            name="Recitation B",
            slug="recitation-b",
        )

        # Three personas
        self.staff_user = User.objects.create_user(email="staff@example.com", name="Staff", is_staff=True)
        self.member_user = User.objects.create_user(email="member@example.com", name="Member")
        PublisherMember.objects.create(user=self.member_user, publisher=self.publisher_a, role="owner")
        self.no_membership_user = User.objects.create_user(email="orphan@example.com", name="Orphan")

        # Grant portal read perms (staff/membership filter is orthogonal to perm filter)
        for user in (self.staff_user, self.member_user, self.no_membership_user):
            self.give_permission(user, PermissionChoice.PORTAL_READ_RECITATION)
            self.give_permission(user, PermissionChoice.PORTAL_CREATE_RECITATION)
            self.give_permission(user, PermissionChoice.PORTAL_UPDATE_RECITATION)
            self.give_permission(user, PermissionChoice.PORTAL_DELETE_RECITATION)

    def test_list_recitations_where_user_is_staff_should_return_all(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(2, len(response.json()["results"]))

    def test_list_recitations_where_user_is_member_of_publisher_should_return_only_owned(self):
        # Arrange
        self.authenticate_user(self.member_user)

        # Act
        response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        results = response.json()["results"]
        self.assertEqual(1, len(results))
        self.assertEqual(self.recitation_a.id, results[0]["id"])

    def test_list_recitations_where_user_has_no_memberships_should_return_empty(self):
        # Arrange
        self.authenticate_user(self.no_membership_user)

        # Act
        response = self.client.get("/portal/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(0, len(response.json()["results"]))

    def test_retrieve_recitation_where_user_is_member_and_resource_belongs_should_return_200(self):
        # Arrange
        self.authenticate_user(self.member_user)

        # Act
        response = self.client.get(f"/portal/recitations/{self.recitation_a.slug}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(self.recitation_a.id, response.json()["id"])

    def test_retrieve_recitation_where_user_is_member_of_other_publisher_should_return_404(self):
        # Arrange
        self.authenticate_user(self.member_user)

        # Act
        response = self.client.get(f"/portal/recitations/{self.recitation_b.slug}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("recitation_not_found", response.json()["error_name"])

    def test_retrieve_recitation_where_user_has_no_memberships_should_return_404(self):
        # Arrange
        self.authenticate_user(self.no_membership_user)

        # Act
        response = self.client.get(f"/portal/recitations/{self.recitation_a.slug}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("recitation_not_found", response.json()["error_name"])

    def test_update_recitation_where_user_is_member_of_other_publisher_should_return_404(self):
        # Arrange
        self.authenticate_user(self.member_user)
        payload = {"description_en": "hijacked"}

        # Act
        response = self.client.patch(
            f"/portal/recitations/{self.recitation_b.slug}/",
            data=payload,
            content_type="application/json",
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("recitation_not_found", response.json()["error_name"])

    def test_delete_recitation_where_user_has_no_memberships_should_return_404(self):
        # Arrange
        self.authenticate_user(self.no_membership_user)

        # Act
        response = self.client.delete(f"/portal/recitations/{self.recitation_a.slug}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("recitation_not_found", response.json()["error_name"])

    def test_create_recitation_where_user_is_member_of_target_publisher_should_return_201(self):
        # Arrange
        self.authenticate_user(self.member_user)
        payload = {
            "name_en": "New Recitation",
            "publisher_id": self.publisher_a.id,
            "reciter_id": self.recitation_a.reciter_id,
            "qiraah_id": self.recitation_a.qiraah_id,
            "riwayah_id": self.recitation_a.riwayah_id,
            "license": "CC0",
        }

        # Act
        response = self.client.post("/portal/recitations/", data=payload, content_type="application/json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)

    def test_create_recitation_where_user_is_member_of_other_publisher_should_return_403(self):
        # Arrange
        self.authenticate_user(self.member_user)
        payload = {
            "name_en": "Forbidden",
            "publisher_id": self.publisher_b.id,
            "reciter_id": self.recitation_a.reciter_id,
            "qiraah_id": self.recitation_a.qiraah_id,
            "riwayah_id": self.recitation_a.riwayah_id,
            "license": "CC0",
        }

        # Act
        response = self.client.post("/portal/recitations/", data=payload, content_type="application/json")

        # Assert
        self.assertEqual(403, response.status_code, response.content)

    def test_create_recitation_where_user_has_no_memberships_should_return_403(self):
        # Arrange
        self.authenticate_user(self.no_membership_user)
        payload = {
            "name_en": "Forbidden",
            "publisher_id": self.publisher_a.id,
            "reciter_id": self.recitation_a.reciter_id,
            "qiraah_id": self.recitation_a.qiraah_id,
            "riwayah_id": self.recitation_a.riwayah_id,
            "license": "CC0",
        }

        # Act
        response = self.client.post("/portal/recitations/", data=payload, content_type="application/json")

        # Assert
        self.assertEqual(403, response.status_code, response.content)

    def test_list_publishers_where_user_is_staff_should_return_all(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_READ_PUBLISHER)

        # Act
        response = self.client.get("/portal/publishers/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(self.publisher_a.id, ids)
        self.assertIn(self.publisher_b.id, ids)

    def test_list_publishers_where_user_is_member_should_return_only_their_publishers(self):
        # Arrange
        self.authenticate_user(self.member_user)
        self.give_permission(self.member_user, PermissionChoice.PORTAL_READ_PUBLISHER)

        # Act
        response = self.client.get("/portal/publishers/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertEqual([self.publisher_a.id], ids)

    def test_list_publishers_where_user_has_no_memberships_should_return_empty(self):
        # Arrange
        self.authenticate_user(self.no_membership_user)
        self.give_permission(self.no_membership_user, PermissionChoice.PORTAL_READ_PUBLISHER)

        # Act
        response = self.client.get("/portal/publishers/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(0, len(response.json()["results"]))

    def test_retrieve_publisher_where_user_is_member_of_other_publisher_should_return_404(self):
        # Arrange
        self.authenticate_user(self.member_user)
        self.give_permission(self.member_user, PermissionChoice.PORTAL_READ_PUBLISHER)

        # Act
        response = self.client.get(f"/portal/publishers/{self.publisher_b.id}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("publisher_not_found", response.json()["error_name"])
