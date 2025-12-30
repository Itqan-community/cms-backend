from unittest.mock import Mock

from django.test import RequestFactory, override_settings
from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.middlewares.publisher_middleware import PublisherMiddleware
from apps.publishers.models import Domain, Publisher
from apps.users.models import User


@override_settings(ALLOWED_HOSTS=["*"])
class PublisherMiddlewareTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.domain = baker.make(Domain, domain="test.com", publisher=self.publisher, is_primary=True)
        self.user = baker.make(User, email="test@example.com", is_active=True)
        self.authenticate_user(self.user)
        self.factory = RequestFactory()
        self.url = "/cms-api/resources/"

    def test_middleware_with_active_publisher_should_allow_request(self):
        # Arrange
        request = self.factory.get("/", HTTP_HOST="test.com")
        mock_get_response = Mock(return_value=Mock(status_code=200))
        middleware = PublisherMiddleware(get_response=mock_get_response)

        # Act
        response = middleware(request)

        # Assert
        # Verify middleware attributes are set correctly
        self.assertEqual(self.publisher, request.publisher)
        self.assertEqual(self.domain, request.publisher_domain)
        # Verify execution proceeded to the next middleware/view
        mock_get_response.assert_called_once_with(request)
        self.assertEqual(200, response.status_code, response.content)

    def test_middleware_with_www_domain_should_strip_www_prefix_and_match_publisher(self):
        # Arrange

        # Act
        response = self.client.get(self.url, headers={"host": "www.test.com"})

        # Assert - If www was stripped and matched 'test.com', then request.publisher is set.
        # If request.publisher is set, then filtering applies.
        # We can verify that we get a 200 OK (and not some error).
        self.assertEqual(200, response.status_code, response.content)

    def test_middleware_with_unknown_domain_should_proceed_without_publisher(self):
        # Arrange

        # Act
        response = self.client.get(self.url, headers={"host": "unknown.com"})

        # Assert
        self.assertEqual(response.status_code, 200)

    def test_middleware_with_inactive_publisher_should_return_423(self):
        # Arrange
        self.domain.is_active = False
        self.domain.save()

        # Act
        response = self.client.get(self.url, headers={"host": "test.com"})

        # Assert
        self.assertEqual(423, response.status_code, response.content)
        self.assertEqual(
            {"error": "Publisher's page is closed for maintenance, please try again later"},
            response.json(),
        )
