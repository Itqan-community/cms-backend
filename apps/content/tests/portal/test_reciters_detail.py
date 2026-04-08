from apps.content.models import Reciter
from apps.core.tests import BaseTestCase
from apps.users.models import User


class ReciterDetailTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")
        self.reciter = Reciter.objects.create(
            name="Test Reciter",
            name_en="Test Reciter",
            name_ar="مقرئ تجريبي",
            slug="test-reciter",
            bio_en="Test Bio",
            nationality="SA",
        )

    def test_get_reciter_where_exists_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"/portal/reciters/{self.reciter.slug}/")

        # Assert
        self.assertEqual(200, response.status_code)
        body = response.json()

        self.assertEqual(body["id"], self.reciter.id)
        self.assertEqual(body["name_en"], "Test Reciter")
        self.assertEqual(body["name_ar"], "مقرئ تجريبي")
        self.assertEqual(body["slug"], "test-reciter")
        self.assertEqual(body["bio_en"], "Test Bio")
        self.assertEqual(body["nationality"], "SA")

    def test_get_reciter_where_non_existent_slug_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get("/portal/reciters/invalid-slug/")

        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("reciter_not_found", response.json()["error_name"])
