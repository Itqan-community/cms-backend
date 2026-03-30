from django.core.cache import cache
from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.models import Domain, Publisher
from apps.publishers.tasks import compute_publisher_stats_task


class ComputePublisherStatsTaskTest(BaseTestCase):

    def test_should_count_active_publishers_correctly(self):
        # Arrange
        active_pub = baker.make(Publisher)
        baker.make(Domain, publisher=active_pub, is_active=True)

        inactive_pub = baker.make(Publisher)
        baker.make(Domain, publisher=inactive_pub, is_active=False)

        # Act
        result = compute_publisher_stats_task()

        # Assert
        self.assertEqual(2, result["total_publishers"])
        self.assertEqual(1, result["active_publishers"])

    def test_should_count_distinct_countries(self):
        # Arrange
        baker.make(Publisher, country="US")
        baker.make(Publisher, country="US")
        baker.make(Publisher, country="FR")

        # Act
        result = compute_publisher_stats_task()

        # Assert
        self.assertEqual(2, result["total_countries"])

    def test_should_store_correct_values_in_cache(self):
        # Arrange
        baker.make(Publisher)

        # Act
        result = compute_publisher_stats_task()

        # Assert
        cached = cache.get("publisher_stats")
        self.assertEqual(result, cached)
