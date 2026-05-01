from apps.content.models import Reciter
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.users.models import User


class ReciterListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")
        self.reciter1 = Reciter.objects.create(
            name="Ahmad",
            name_en="Ahmad",
            slug="ahmad",
            nationality="SA",
        )
        self.reciter2 = Reciter.objects.create(
            name="Zaid",
            name_en="Zaid",
            slug="zaid",
            nationality="EG",
        )

    def test_list_reciters_where_valid_request_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_RECITER)

        # Act
        response = self.client.get("/portal/reciters/")

        # Assert
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertIn("results", body)
        self.assertEqual(2, len(body["results"]))

        # Check fields match ReciterListOut
        item = body["results"][0]
        self.assertIn("id", item)
        self.assertIn("name", item)
        self.assertIn("bio", item)
        self.assertIn("recitations_count", item)
        self.assertIn("nationality", item)
        self.assertIn("slug", item)

    def test_list_reciters_where_search_query_should_filter_correctly(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_RECITER)

        # Act
        response = self.client.get("/portal/reciters/?search=ahma")

        # Assert
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(1, len(body["results"]))
        self.assertEqual(self.reciter1.id, body["results"][0]["id"])

    def test_list_reciters_where_ordering_query_should_sort_correctly(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_RECITER)

        # Act
        response_desc = self.client.get("/portal/reciters/?ordering=-name")

        # Assert
        self.assertEqual(200, response_desc.status_code)
        body_desc = response_desc.json()
        self.assertEqual(self.reciter2.id, body_desc["results"][0]["id"])
        self.assertEqual(self.reciter1.id, body_desc["results"][1]["id"])

        # Act 2
        response_asc = self.client.get("/portal/reciters/?ordering=name")

        # Assert 2
        body_asc = response_asc.json()
        self.assertEqual(self.reciter1.id, body_asc["results"][0]["id"])
        self.assertEqual(self.reciter2.id, body_asc["results"][1]["id"])

    def test_list_reciters_where_unauthenticated_should_return_401(self):
        # Arrange
        # No authentication

        # Act
        response = self.client.get("/portal/reciters/")

        # Assert
        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_error", response.json().get("error_name"))

    def test_list_reciters_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(email="noperm@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.get("/portal/reciters/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
