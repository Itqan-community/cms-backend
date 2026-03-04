from model_bakery import baker

from apps.content.models import Qiraah, Riwayah
from apps.core.tests import BaseTestCase
from apps.users.models import User


class RiwayahCRUDTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="riwayah-crud@example.com", is_active=True, is_staff=True)
        self.authenticate_user(self.user)
        self.qiraah = baker.make(Qiraah, name="Qiraah Asim", is_active=True)

    # ── CREATE ──────────────────────────────────────────────────────

    def test_create_riwayah_should_return_201_with_riwayah_data(self):
        # Arrange
        data = {"name": "Hafs", "qiraah_id": self.qiraah.id}

        # Act
        response = self.client.post("/cms-api/riwayahs/create/", data=data, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Hafs", body["name"])
        self.assertIn("id", body)
        self.assertIn("slug", body)
        self.assertEqual(self.qiraah.id, body["qiraah"]["id"])

    def test_create_riwayah_with_arabic_name_should_return_201(self):
        # Arrange
        data = {
            "name": "Hafs An Asim",
            "name_ar": "حفص عن عاصم",
            "qiraah_id": self.qiraah.id,
        }

        # Act
        response = self.client.post("/cms-api/riwayahs/create/", data=data, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)

    def test_create_riwayah_without_name_should_return_422(self):
        # Arrange
        data = {"qiraah_id": self.qiraah.id}

        # Act
        response = self.client.post("/cms-api/riwayahs/create/", data=data, format="json")

        # Assert
        self.assertIn(response.status_code, [400, 422], response.content)

    def test_create_riwayah_without_qiraah_id_should_return_422(self):
        # Arrange
        data = {"name": "Orphan Riwayah"}

        # Act
        response = self.client.post("/cms-api/riwayahs/create/", data=data, format="json")

        # Assert
        self.assertIn(response.status_code, [400, 422], response.content)

    # ── DETAIL ──────────────────────────────────────────────────────

    def test_get_riwayah_detail_should_return_200(self):
        # Arrange
        riwayah = baker.make(
            Riwayah,
            name="Detail Riwayah",
            qiraah=self.qiraah,
            is_active=True,
        )

        # Act
        response = self.client.get(f"/cms-api/riwayahs/{riwayah.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Detail Riwayah", body["name"])
        self.assertEqual(self.qiraah.id, body["qiraah"]["id"])
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)

    def test_get_riwayah_detail_with_non_existent_id_should_return_404(self):
        # Act
        response = self.client.get("/cms-api/riwayahs/99999/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    # ── UPDATE ──────────────────────────────────────────────────────

    def test_update_riwayah_should_return_200_with_updated_data(self):
        # Arrange
        riwayah = baker.make(Riwayah, name="Original Riwayah", qiraah=self.qiraah)
        data = {"name": "Updated Riwayah"}

        # Act
        response = self.client.put(f"/cms-api/riwayahs/{riwayah.id}/update/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Updated Riwayah", body["name"])

    def test_update_riwayah_qiraah_should_change_parent(self):
        # Arrange
        qiraah2 = baker.make(Qiraah, name="Qiraah Nafi", is_active=True)
        riwayah = baker.make(Riwayah, name="Warsh", qiraah=self.qiraah)
        data = {"qiraah_id": qiraah2.id}

        # Act
        response = self.client.patch(f"/cms-api/riwayahs/{riwayah.id}/update/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(qiraah2.id, body["qiraah"]["id"])

    def test_partial_update_riwayah_should_return_200_with_partial_data(self):
        # Arrange
        riwayah = baker.make(Riwayah, name="Original Riwayah", qiraah=self.qiraah, is_active=True)
        data = {"is_active": False}

        # Act
        response = self.client.patch(f"/cms-api/riwayahs/{riwayah.id}/update/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Original Riwayah", body["name"])  # Unchanged
        self.assertFalse(body["is_active"])

    def test_update_riwayah_with_non_existent_id_should_return_404(self):
        # Act
        data = {"name": "Ghost"}
        response = self.client.put("/cms-api/riwayahs/99999/update/", data=data, format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    # ── DELETE ──────────────────────────────────────────────────────

    def test_delete_riwayah_should_return_200_and_remove_riwayah(self):
        # Arrange
        riwayah = baker.make(Riwayah, name="To Delete Riwayah", qiraah=self.qiraah)

        # Act
        response = self.client.delete(f"/cms-api/riwayahs/{riwayah.id}/delete/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(Riwayah.objects.filter(id=riwayah.id).exists())

    def test_delete_riwayah_with_non_existent_id_should_return_404(self):
        # Act
        response = self.client.delete("/cms-api/riwayahs/99999/delete/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)


class RiwayahModelTest(BaseTestCase):
    def test_riwayah_str_should_return_name(self):
        qiraah = baker.make(Qiraah, name="Q")
        riwayah = baker.make(Riwayah, name="Test Riwayah", qiraah=qiraah)
        self.assertEqual(str(riwayah), "Riwayah(name=Test Riwayah)")

    def test_riwayah_slug_auto_generated_on_save(self):
        qiraah = baker.make(Qiraah, name="Q Slug")
        riwayah = Riwayah(name="Hafs An Asim", qiraah=qiraah)
        riwayah.save()
        self.assertTrue(riwayah.slug)

    def test_riwayah_belongs_to_qiraah(self):
        qiraah = baker.make(Qiraah, name="Parent Qiraah")
        riwayah = baker.make(Riwayah, name="Child Riwayah", qiraah=qiraah)
        self.assertEqual(riwayah.qiraah_id, qiraah.id)

    def test_riwayah_unique_together_qiraah_name(self):
        """Two riwayahs with the same name under the same qiraah should fail."""
        qiraah = baker.make(Qiraah, name="Unique Q")
        Riwayah.objects.create(name="Same Name", qiraah=qiraah)
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Riwayah.objects.create(name="Same Name", qiraah=qiraah)

    def test_riwayah_created_at_updated_at_auto_set(self):
        qiraah = baker.make(Qiraah, name="Time Q")
        riwayah = baker.make(Riwayah, name="Timestamps Test", qiraah=qiraah)
        self.assertIsNotNone(riwayah.created_at)
        self.assertIsNotNone(riwayah.updated_at)
