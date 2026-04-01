from django.core.cache import cache
from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.models import Domain, Publisher
from apps.users.models import User


class PublisherStatsEndpointTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.url = "/portal/publishers/stats/"

        self.publisher = baker.make(Publisher)
        self.domain = baker.make(Domain, publisher=self.publisher, domain="example.com")

        # Create staff user
        self.user = baker.make(
            User,
            is_active=True,
            is_staff=True,
        )

        cache.clear()

    def test_stats_endpoint_where_unauthenticated_should_return_401(self):

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(401, response.status_code)

    def test_stats_endpoint_where_cache_populated_should_return_cached_data(self):
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)
        cache.set("publisher_stats", {"total_publishers": 99})

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertEqual(99, response.json()["total_publishers"])

    def test_stats_endpoint_where_cache_empty_should_compute_and_return(self):
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)
        baker.make(Publisher)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code)

        data = response.json()
        self.assertIn("total_publishers", data)
        self.assertEqual(2, data["total_publishers"])
