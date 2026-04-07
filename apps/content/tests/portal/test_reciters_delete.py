from apps.content.models import Reciter
from apps.core.tests import BaseTestCase
from apps.users.models import User


class ReciterDeleteTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")
        self.reciter = Reciter.objects.create(
            name="Test Reciter",
            slug="test-reciter",
        )

    def test_delete_reciter_where_reciter_exists_should_return_204(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.delete(f"/portal/reciters/{self.reciter.slug}/")

        # Assert
        self.assertEqual(204, response.status_code)
        self.assertFalse(Reciter.objects.filter(id=self.reciter.id).exists())

    def test_delete_reciter_where_unauthenticated_should_return_401(self):
        # Arrange
        # No authentication

        # Act
        response = self.client.delete(f"/portal/reciters/{self.reciter.slug}/")

        # Assert
        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_error", response.json().get("error_name"))

    def test_delete_reciter_where_non_existent_slug_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.delete("/portal/reciters/non-existent/")

        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("reciter_not_found", response.json()["error_name"])
