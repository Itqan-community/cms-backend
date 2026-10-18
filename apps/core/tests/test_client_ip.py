from django.test import RequestFactory

from apps.core.utils.client_ip import client_ip


class TestClientIp:
    def test_client_ip_where_forwarded_should_take_first_hop(self):
        # Arrange
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="203.0.113.7, 10.0.0.2", REMOTE_ADDR="10.0.0.2")

        # Act / Assert
        assert client_ip(request) == "203.0.113.7"

    def test_client_ip_where_not_forwarded_should_use_remote_addr(self):
        # Act / Assert
        assert client_ip(RequestFactory().get("/", REMOTE_ADDR="10.0.0.2")) == "10.0.0.2"
