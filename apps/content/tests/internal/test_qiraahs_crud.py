from model_bakery import baker

from apps.content.models import Qiraah
from apps.core.tests import BaseTestCase
from apps.users.models import User


class QiraahCRUDTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="qiraah-crud@example.com", is_active=True, is_staff=True)
        self.authenticate_user(self.user)

    # ── CREATE ──────────────────────────────────────────────────────

    def test_create_qiraah_should_return_201_with_qiraah_data(self):
        # Arrange
        data = {"name": "Qiraah Asim", "bio": "Well-known qiraah"}

        # Act
        response = self.client.post("/cms-api/qiraahs/create/", data=data, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Qiraah Asim", body["name"])
        self.assertIn("id", body)
        self.assertIn("slug", body)

    def test_create_qiraah_with_recitation_style_murattal_should_return_201(self):
        # Arrange
        data = {
            "name": "Qiraah Nafi Murattal",
            "bio": "Murattal style",
            "recitation_style": "murattal",
        }

        # Act
        response = self.client.post("/cms-api/qiraahs/create/", data=data, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        qiraah = Qiraah.objects.get(name="Qiraah Nafi Murattal")
        self.assertEqual(qiraah.recitation_style, "murattal")

    def test_create_qiraah_with_recitation_style_mujawwad_should_return_201(self):
        # Arrange
        data = {
            "name": "Qiraah Nafi Mujawwad",
            "bio": "Mujawwad style",
            "recitation_style": "mujawwad",
        }

        # Act
        response = self.client.post("/cms-api/qiraahs/create/", data=data, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        qiraah = Qiraah.objects.get(name="Qiraah Nafi Mujawwad")
        self.assertEqual(qiraah.recitation_style, "mujawwad")

    def test_create_qiraah_with_arabic_name_should_return_201(self):
        # Arrange
        data = {"name": "Test Qiraah", "name_ar": "قراءة عاصم", "bio": ""}

        # Act
        response = self.client.post("/cms-api/qiraahs/create/", data=data, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)

    def test_create_qiraah_without_name_should_return_422(self):
        # Arrange
        data = {"bio": "No name provided"}

        # Act
        response = self.client.post("/cms-api/qiraahs/create/", data=data, format="json")

        # Assert
        self.assertIn(response.status_code, [400, 422], response.content)

    # ── DETAIL ──────────────────────────────────────────────────────

    def test_get_qiraah_detail_should_return_200(self):
        # Arrange
        qiraah = baker.make(
            Qiraah,
            name="Detail Qiraah",
            bio="Test bio",
            is_active=True,
            recitation_style="murattal",
        )

        # Act
        response = self.client.get(f"/cms-api/qiraahs/{qiraah.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Detail Qiraah", body["name"])
        self.assertEqual("Test bio", body["bio"])
        self.assertEqual("murattal", body["recitation_style"])
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)

    def test_get_qiraah_detail_with_non_existent_id_should_return_404(self):
        # Act
        response = self.client.get("/cms-api/qiraahs/99999/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    # ── UPDATE ──────────────────────────────────────────────────────

    def test_update_qiraah_should_return_200_with_updated_data(self):
        # Arrange
        qiraah = baker.make(Qiraah, name="Original Qiraah", bio="Original bio")
        data = {"name": "Updated Qiraah", "bio": "Updated bio"}

        # Act
        response = self.client.put(f"/cms-api/qiraahs/{qiraah.id}/update/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Updated Qiraah", body["name"])
        self.assertEqual("Updated bio", body["bio"])

    def test_update_qiraah_recitation_style_should_change(self):
        # Arrange
        qiraah = baker.make(Qiraah, name="Style Test", recitation_style="murattal")
        data = {"recitation_style": "mujawwad"}

        # Act
        response = self.client.patch(f"/cms-api/qiraahs/{qiraah.id}/update/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("mujawwad", body["recitation_style"])

    def test_partial_update_qiraah_should_return_200_with_partial_data(self):
        # Arrange
        qiraah = baker.make(Qiraah, name="Original Qiraah", bio="Original bio")
        data = {"bio": "Partially updated bio"}

        # Act
        response = self.client.patch(f"/cms-api/qiraahs/{qiraah.id}/update/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Original Qiraah", body["name"])  # Unchanged
        self.assertEqual("Partially updated bio", body["bio"])

    def test_update_qiraah_with_non_existent_id_should_return_404(self):
        # Act
        data = {"name": "Ghost"}
        response = self.client.put("/cms-api/qiraahs/99999/update/", data=data, format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    # ── DELETE ──────────────────────────────────────────────────────

    def test_delete_qiraah_should_return_200_and_remove_qiraah(self):
        # Arrange
        qiraah = baker.make(Qiraah, name="To Delete Qiraah")

        # Act
        response = self.client.delete(f"/cms-api/qiraahs/{qiraah.id}/delete/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(Qiraah.objects.filter(id=qiraah.id).exists())

    def test_delete_qiraah_with_non_existent_id_should_return_404(self):
        # Act
        response = self.client.delete("/cms-api/qiraahs/99999/delete/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)


class QiraahModelTest(BaseTestCase):
    def test_qiraah_str_should_return_name(self):
        qiraah = baker.make(Qiraah, name="Test Qiraah")
        self.assertEqual(str(qiraah), "Qiraah(name=Test Qiraah)")

    def test_qiraah_slug_auto_generated_on_save(self):
        qiraah = Qiraah(name="Qiraah Asim")
        qiraah.save()
        self.assertTrue(qiraah.slug)

    def test_qiraah_recitation_style_choices(self):
        """Ensure recitation_style choices are murattal and mujawwad."""
        choices = dict(Qiraah.RecitationStyleChoice.choices)
        self.assertIn("murattal", choices)
        self.assertIn("mujawwad", choices)

    def test_qiraah_recitation_style_nullable(self):
        """recitation_style should be nullable."""
        qiraah = Qiraah(name="No Style Qiraah")
        qiraah.save()
        self.assertIsNone(qiraah.recitation_style)

    def test_qiraah_created_at_updated_at_auto_set(self):
        qiraah = baker.make(Qiraah, name="Timestamps Test")
        self.assertIsNotNone(qiraah.created_at)
        self.assertIsNotNone(qiraah.updated_at)
