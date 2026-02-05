from django.test import override_settings
from model_bakery import baker

from apps.content.models import Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Domain, Publisher
from apps.users.models import User


@override_settings(ALLOWED_HOSTS=["*"])
class ResourceDomainFilteringTest(BaseTestCase):
    def setUp(self):
        self.user = baker.make(User, email="user@example.com", is_active=True)

        # Publisher 1
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.domain1 = baker.make(Domain, domain="publisher1.com", publisher=self.publisher1, is_primary=True)

        # Publisher 2
        self.publisher2 = baker.make(Publisher, name="Publisher Two")
        self.domain2 = baker.make(Domain, domain="publisher2.com", publisher=self.publisher2, is_primary=True)

        # Resources
        self.resource1 = baker.make(Resource, publisher=self.publisher1, name="P1 Resource")
        self.resource2 = baker.make(Resource, publisher=self.publisher2, name="P2 Resource")

    def test_list_resources_via_domain_should_return_only_publisher_resources(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act - Request to Publisher 1's domain
        response = self.client.get("/cms-api/resources/", headers={"origin": "publisher1.com"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.resource1.id)
        self.assertEqual(results[0]["name"], "P1 Resource")

    def test_list_resources_via_domain_should_return_correct_resources_for_different_domain(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act - Request to Publisher 2's domain
        response = self.client.get("/cms-api/resources/", headers={"origin": "publisher2.com"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.resource2.id)
        self.assertEqual(results[0]["name"], "P2 Resource")

    def test_list_resources_via_unknown_domain_should_return_all_resources(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get("/cms-api/resources/", headers={"origin": "unknown.com"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        results = response.json()["results"]
        # Should see all resources because Q() filters nothing
        self.assertEqual(len(results), 2)

    def test_create_resource_via_domain_should_force_domain_publisher(self):
        # Arrange
        self.authenticate_user(self.user)
        data = {
            "name": "New Resource via Domain",
            "description": "Test",
            "category": Resource.CategoryChoice.TAFSIR,
            "publisher_id": self.publisher2.id,  # Trying to spoof publisher2
        }

        # Act
        response = self.client.post(
            "/cms-api/resources/", data=data, format="json", headers={"origin": "publisher1.com"}
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Verify the resource was created
        resource_id = body["id"]
        resource = Resource.objects.get(id=resource_id)

        self.assertEqual(resource.publisher, self.publisher1)
        self.assertNotEqual(resource.publisher, self.publisher2)

    def test_detail_resource_via_wrong_domain_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act - Try to access Publisher 2's resource via Publisher 1's domain
        response = self.client.get(f"/cms-api/resources/{self.resource2.id}/", headers={"origin": "publisher1.com"})

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_update_resource_via_wrong_domain_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        data = {"name": "Hacked Update"}

        # Act - Try to update Publisher 2's resource via Publisher 1's domain
        response = self.client.put(
            f"/cms-api/resources/{self.resource2.id}/",
            data=data,
            format="json",
            headers={"origin": "publisher1.com"},
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.resource2.refresh_from_db()
        self.assertNotEqual(self.resource2.name, "Hacked Update")
