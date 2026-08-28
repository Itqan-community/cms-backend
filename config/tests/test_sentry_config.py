"""Tests for Sentry tracing configuration."""

from django.test import SimpleTestCase

from config.helpers.sentry import traces_sampler


def wsgi_context(path: str) -> dict:
    return {
        "transaction_context": {"name": "generic WSGI request", "op": "http.server"},
        "wsgi_environ": {"PATH_INFO": path},
    }


def asgi_context(path: str) -> dict:
    return {
        "transaction_context": {"name": "generic ASGI request", "op": "http.server"},
        "asgi_scope": {"path": path},
    }


class TestTracesSampler(SimpleTestCase):
    """Reciter endpoints must be excluded from performance monitoring."""

    def test_traces_sampler_where_path_is_public_reciters_should_return_zero(self):
        # Arrange
        context = wsgi_context("/reciters/")

        # Act
        rate = traces_sampler(context)

        # Assert
        self.assertEqual(rate, 0.0)

    def test_traces_sampler_where_path_is_mounted_reciters_should_return_zero(self):
        # Arrange
        paths = [
            "/cms-api/reciters/",
            "/tenant/reciters/",
            "/portal/reciters/",
            "/portal/reciters/42/",
            "/reciters/mishary-alafasy/",
        ]

        for path in paths:
            with self.subTest(path=path):
                # Act
                rate = traces_sampler(wsgi_context(path))

                # Assert
                self.assertEqual(rate, 0.0)

    def test_traces_sampler_where_asgi_path_is_reciters_should_return_zero(self):
        # Arrange
        context = asgi_context("/tenant/reciters/")

        # Act
        rate = traces_sampler(context)

        # Assert
        self.assertEqual(rate, 0.0)

    def test_traces_sampler_where_transaction_name_is_reciters_path_should_return_zero(self):
        # Arrange: no wsgi/asgi keys, transaction already named after the URL
        context = {"transaction_context": {"name": "/reciters/", "op": "http.server"}}

        # Act
        rate = traces_sampler(context)

        # Assert
        self.assertEqual(rate, 0.0)

    def test_traces_sampler_where_path_is_other_endpoint_should_return_default_rate(self):
        # Arrange
        paths = ["/recitations/", "/portal/mushafs/", "/cms-api/auth/login/"]

        for path in paths:
            with self.subTest(path=path):
                # Act
                rate = traces_sampler(wsgi_context(path))

                # Assert
                self.assertEqual(rate, 1.0)

    def test_traces_sampler_where_path_merely_contains_reciters_word_should_return_default_rate(
        self,
    ):
        # Arrange: "reciters" must be a full path segment followed by a slash
        paths = ["/reciters", "/top-reciters/", "/portal/reciters-export/"]

        for path in paths:
            with self.subTest(path=path):
                # Act
                rate = traces_sampler(wsgi_context(path))

                # Assert
                self.assertEqual(rate, 1.0)

    def test_traces_sampler_where_transaction_is_celery_task_should_return_default_rate(self):
        # Arrange: Celery sampling contexts carry no request path
        context = {"transaction_context": {"name": "apps.content.tasks.sync", "op": "queue.task"}}

        # Act
        rate = traces_sampler(context)

        # Assert
        self.assertEqual(rate, 1.0)
