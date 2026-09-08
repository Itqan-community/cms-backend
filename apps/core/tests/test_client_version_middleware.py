import logging
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from apps.core.logging_filters import ClientContextFilter
from apps.core.middlewares import client_version as client_version_module
from apps.core.middlewares.client_version import (
    CLIENT_NAME_HEADER,
    CLIENT_VERSION_HEADER,
    WARNING_HEADER,
    ClientVersionMiddleware,
    client_context,
)


def _middleware(get_response=None) -> ClientVersionMiddleware:
    """Build the middleware around a get_response that captures the request it saw."""
    return ClientVersionMiddleware(get_response or (lambda request: HttpResponse("ok")))


# The module-level import binding for the SDK. sentry-sdk lives in the `prod` extra, so
# the real module is absent in CI and local dev and the binding is None there -- the
# tests must stub the binding itself rather than reach through it.
_SENTRY_SDK_ATTR = "sentry_sdk"


def _stub_sentry():
    """Patch in a stand-in sentry_sdk so tagging is asserted in any environment.

    ``patch.object`` does not create missing attributes, so this still fails loudly if
    the binding is ever renamed.
    """
    return patch.object(client_version_module, _SENTRY_SDK_ATTR, MagicMock())


class ClientVersionMiddlewareTest(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_call_where_valid_headers_sent_should_set_them_on_the_request(self):
        # Arrange
        seen = {}
        request = self.factory.get(
            "/recitations/",
            headers={"x-client-name": "quran-companion", "x-client-version": "2.4.1"},
        )

        def get_response(req):
            seen["client_name"] = req.client_name
            seen["client_version"] = req.client_version
            return HttpResponse("ok")

        # Act
        response = _middleware(get_response)(request)

        # Assert
        self.assertEqual("quran-companion", seen["client_name"])
        self.assertEqual("2.4.1", seen["client_version"])
        self.assertNotIn(WARNING_HEADER, response)

    def test_call_where_version_carries_prerelease_and_build_metadata_should_accept_it(self):
        # Arrange
        request = self.factory.get("/recitations/", headers={"x-client-version": "2.4.1-beta.3+build.77"})

        # Act
        response = _middleware()(request)

        # Assert
        self.assertEqual("2.4.1-beta.3+build.77", request.client_version)
        self.assertNotIn(WARNING_HEADER, response)

    def test_call_where_headers_absent_should_set_none_without_warning(self):
        # Arrange
        request = self.factory.get("/recitations/")

        # Act
        response = _middleware()(request)

        # Assert
        self.assertIsNone(request.client_name)
        self.assertIsNone(request.client_version)
        self.assertNotIn(WARNING_HEADER, response)

    def test_call_where_version_is_malformed_should_ignore_it_and_warn(self):
        # Arrange
        request = self.factory.get(
            "/recitations/",
            headers={"x-client-name": "quran-companion", "x-client-version": "2.4.1 (release build)"},
        )

        # Act
        response = _middleware()(request)

        # Assert
        self.assertEqual("quran-companion", request.client_name)
        self.assertIsNone(request.client_version)
        self.assertIn(CLIENT_VERSION_HEADER, response[WARNING_HEADER])
        self.assertNotIn(CLIENT_NAME_HEADER, response[WARNING_HEADER])

    def test_call_where_name_exceeds_max_length_should_ignore_it_and_warn(self):
        # Arrange
        request = self.factory.get("/recitations/", headers={"x-client-name": "a" * 65})

        # Act
        response = _middleware()(request)

        # Assert
        self.assertIsNone(request.client_name)
        self.assertIn(CLIENT_NAME_HEADER, response[WARNING_HEADER])

    def test_call_where_both_headers_are_malformed_should_warn_about_both(self):
        # Arrange
        request = self.factory.get(
            "/recitations/",
            headers={"x-client-name": "my app!", "x-client-version": "v/1"},
        )

        # Act
        response = _middleware()(request)

        # Assert
        warning = response[WARNING_HEADER]
        self.assertIn(CLIENT_NAME_HEADER, warning)
        self.assertIn(CLIENT_VERSION_HEADER, warning)

    def test_call_where_header_is_blank_should_be_treated_as_absent(self):
        # Arrange
        request = self.factory.get("/recitations/", headers={"x-client-version": "   "})

        # Act
        response = _middleware()(request)

        # Assert
        self.assertIsNone(request.client_version)
        self.assertNotIn(WARNING_HEADER, response)

    def test_call_where_valid_headers_sent_should_tag_sentry_with_the_client(self):
        # Arrange
        request = self.factory.get(
            "/recitations/",
            headers={"x-client-name": "quran-companion", "x-client-version": "2.4.1"},
        )

        # Act
        with _stub_sentry() as sentry:
            _middleware()(request)

        # Assert
        set_tag = sentry.set_tag
        self.assertIn(("client.name", "quran-companion"), [call.args for call in set_tag.call_args_list])
        self.assertIn(("client.version", "2.4.1"), [call.args for call in set_tag.call_args_list])

    def test_call_where_sentry_sdk_is_not_installed_should_not_raise(self):
        # Arrange -- sentry-sdk ships only in the `prod` extra, so it is absent in CI
        # and local dev; the middleware must degrade quietly rather than blow up.
        request = self.factory.get(
            "/recitations/",
            headers={"x-client-name": "quran-companion", "x-client-version": "2.4.1"},
        )

        # Act
        with patch.object(client_version_module, _SENTRY_SDK_ATTR, None):
            response = _middleware()(request)

        # Assert -- the client is still captured for logging and usage tracking.
        self.assertEqual(200, response.status_code)
        self.assertEqual("quran-companion", request.client_name)
        self.assertEqual("2.4.1", request.client_version)

    def test_call_where_no_headers_sent_should_not_tag_sentry(self):
        # Arrange
        request = self.factory.get("/recitations/")

        # Act
        with _stub_sentry() as sentry:
            _middleware()(request)
        set_tag = sentry.set_tag

        # Assert
        set_tag.assert_not_called()

    def test_call_where_request_is_being_handled_should_expose_the_client_on_the_context(self):
        # Arrange
        seen = {}
        request = self.factory.get(
            "/recitations/",
            headers={"x-client-name": "quran-companion", "x-client-version": "2.4.1"},
        )

        def get_response(req):
            seen["context"] = client_context.get()
            return HttpResponse("ok")

        # Act
        _middleware(get_response)(request)

        # Assert
        self.assertEqual(("quran-companion", "2.4.1"), seen["context"])

    def test_call_where_response_returned_should_reset_the_context_for_the_next_request(self):
        # Arrange
        request = self.factory.get(
            "/recitations/",
            headers={"x-client-name": "quran-companion", "x-client-version": "2.4.1"},
        )

        # Act
        _middleware()(request)

        # Assert
        self.assertEqual((None, None), client_context.get())

    def test_call_where_the_view_raises_should_still_reset_the_context(self):
        # Arrange
        request = self.factory.get("/recitations/", headers={"x-client-name": "quran-companion"})

        def get_response(req):
            raise ValueError("boom")

        # Act / Assert
        with self.assertRaises(ValueError):
            _middleware(get_response)(request)
        self.assertEqual((None, None), client_context.get())


class ClientContextFilterTest(SimpleTestCase):
    def _record(self) -> logging.LogRecord:
        return logging.LogRecord(
            name="apps.test", level=logging.INFO, pathname=__file__, lineno=1, msg="hi", args=(), exc_info=None
        )

    def test_filter_where_client_is_known_should_annotate_the_record(self):
        # Arrange
        record = self._record()
        token = client_context.set(("quran-companion", "2.4.1"))

        # Act
        try:
            kept = ClientContextFilter().filter(record)
        finally:
            client_context.reset(token)

        # Assert
        self.assertTrue(kept)
        self.assertEqual(" client=quran-companion/2.4.1", record.client)

    def test_filter_where_only_version_is_known_should_annotate_with_an_unknown_name(self):
        # Arrange
        record = self._record()
        token = client_context.set((None, "2.4.1"))

        # Act
        try:
            ClientContextFilter().filter(record)
        finally:
            client_context.reset(token)

        # Assert
        self.assertEqual(" client=unknown/2.4.1", record.client)

    def test_filter_where_no_client_is_known_should_leave_the_record_unannotated(self):
        # Arrange
        record = self._record()

        # Act
        kept = ClientContextFilter().filter(record)

        # Assert
        self.assertTrue(kept)
        self.assertEqual("", record.client)
