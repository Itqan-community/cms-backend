from model_bakery import baker

from apps.content.models import Reciter
from apps.core.tests import BaseTestCase
from apps.users.models import User


class ReciterCRUDTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="reciter-crud@example.com", is_active=True, is_staff=True)
        self.authenticate_user(self.user)

    # ── CREATE ──────────────────────────────────────────────────────

    def test_create_reciter_should_return_201_with_reciter_data(self):
        # Arrange
        data = {"name": "Mshari Al-Afasi", "bio": "Famous Kuwaiti reciter"}

        # Act
        response = self.client.post("/cms-api/reciters/create/", data=data, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Mshari Al-Afasi", body["name"])
        self.assertIn("id", body)
        self.assertIn("slug", body)

    def test_create_reciter_with_arabic_name_should_return_201(self):
        # Arrange
        data = {"name": "Saad Al-Ghamidi", "name_ar": "سعد الغامدي", "bio": ""}

        # Act
        response = self.client.post("/cms-api/reciters/create/", data=data, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)

    def test_create_reciter_without_name_should_return_422(self):
        # Arrange
        data = {"bio": "No name provided"}

        # Act
        response = self.client.post("/cms-api/reciters/create/", data=data, format="json")

        # Assert
        self.assertIn(response.status_code, [400, 422], response.content)

    # ── LIST ────────────────────────────────────────────────────────

    def test_list_reciters_should_return_200(self):
        # Arrange
        baker.make(Reciter, name="Reciter A", is_active=True)
        baker.make(Reciter, name="Reciter B", is_active=True)

        # Act
        response = self.client.get("/cms-api/reciters/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    # ── DETAIL (via reciter_profile.py endpoint) ────────────────────

    def test_get_reciter_detail_should_return_200(self):
        # Arrange
        reciter = baker.make(Reciter, name="Detail Reciter", bio="Test bio", is_active=True)

        # Act
        response = self.client.get(f"/cms-api/reciters/{reciter.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Detail Reciter", body["name"])
        self.assertEqual("Test bio", body["bio"])

    def test_get_reciter_detail_with_non_existent_id_should_return_404(self):
        # Act
        response = self.client.get("/cms-api/reciters/99999/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    # ── UPDATE ──────────────────────────────────────────────────────

    def test_update_reciter_should_return_200_with_updated_data(self):
        # Arrange
        reciter = baker.make(Reciter, name="Original Name", bio="Original bio")
        data = {"name": "Updated Name", "bio": "Updated bio"}

        # Act
        response = self.client.put(f"/cms-api/reciters/{reciter.id}/update/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Updated Name", body["name"])
        self.assertEqual("Updated bio", body["bio"])

    def test_partial_update_reciter_should_return_200_with_partial_data(self):
        # Arrange
        reciter = baker.make(Reciter, name="Original Name", bio="Original bio")
        data = {"bio": "Partially updated bio"}

        # Act
        response = self.client.patch(f"/cms-api/reciters/{reciter.id}/update/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Original Name", body["name"])  # Unchanged
        self.assertEqual("Partially updated bio", body["bio"])

    def test_update_reciter_with_non_existent_id_should_return_404(self):
        # Act
        data = {"name": "Ghost"}
        response = self.client.put("/cms-api/reciters/99999/update/", data=data, format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_update_reciter_is_active_should_toggle_status(self):
        # Arrange
        reciter = baker.make(Reciter, name="Active Reciter", is_active=True)
        data = {"is_active": False}

        # Act
        response = self.client.patch(f"/cms-api/reciters/{reciter.id}/update/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertFalse(body["is_active"])

    # ── DELETE ──────────────────────────────────────────────────────

    def test_delete_reciter_should_return_200_and_remove_reciter(self):
        # Arrange
        reciter = baker.make(Reciter, name="To Delete")

        # Act
        response = self.client.delete(f"/cms-api/reciters/{reciter.id}/delete/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(Reciter.objects.filter(id=reciter.id).exists())

    def test_delete_reciter_with_non_existent_id_should_return_404(self):
        # Act
        response = self.client.delete("/cms-api/reciters/99999/delete/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)


class ReciterModelTest(BaseTestCase):
    def test_reciter_str_should_return_name(self):
        reciter = baker.make(Reciter, name="Test Reciter")
        self.assertEqual(str(reciter), "Reciter(name=Test Reciter)")

    def test_reciter_slug_auto_generated_on_save(self):
        reciter = Reciter(name="Abu Bakr Al Shatiri")
        reciter.save()
        self.assertTrue(reciter.slug)
        self.assertIn("abu-bakr", reciter.slug)

    def test_reciter_slug_unicode_arabic_name(self):
        reciter = Reciter(name="عبد الرحمن السديس")
        reciter.save()
        self.assertTrue(reciter.slug)

    def test_reciter_created_at_updated_at_auto_set(self):
        reciter = baker.make(Reciter, name="Timestamps Test")
        self.assertIsNotNone(reciter.created_at)
        self.assertIsNotNone(reciter.updated_at)
