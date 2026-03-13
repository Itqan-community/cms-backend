from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class DeletePublisherTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)

    def test_delete_publisher_where_exists_should_return_204(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        publisher = baker.make(Publisher, name="To Delete", slug="to-delete")

        # Act
        response = self.client.delete(f"/portal/publishers/{publisher.id}/")

        # Assert
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(Publisher.objects.filter(id=publisher.id).exists())

    def test_delete_publisher_where_not_found_should_return_404(self) -> None:
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.delete("/portal/publishers/99999/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_not_found", body["error_name"])

    def test_delete_publisher_where_unauthenticated_should_return_401(self) -> None:
        # Arrange
        publisher = baker.make(Publisher, name="Test", slug="test")

        # Act
        response = self.client.delete(f"/portal/publishers/{publisher.id}/")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
