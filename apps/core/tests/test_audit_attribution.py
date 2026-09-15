"""
Contract tests for django-simple-history user attribution.

Middleware reference semantics tests verify that HistoryRequestMiddleware
stores a live reference to the request object via HistoricalRecords.context,
and that mutations to request.user (as Ninja auth performs inside the view)
are visible through that reference.

Ninja auth behavioral tests verify that each auth class mutates request.user
on the provided request object.

All tests are DB-free SimpleTestCase.
"""

from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from simple_history.models import HistoricalRecords

# ---------------------------------------------------------------------------
# Middleware reference semantics
# ---------------------------------------------------------------------------


class MiddlewareReferenceSemanticTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_context_holds_live_request_reference(self):
        """
        HistoryRequestMiddleware sets HistoricalRecords.context.request to the
        live request object. Inside get_response (where the view runs), that
        reference must be the exact same object — not a copy.
        """
        request = self.factory.get("/")
        captured = {}

        def fake_get_response(req):
            captured["ctx_request"] = HistoricalRecords.context.request
            return HttpResponse()

        from simple_history.middleware import HistoryRequestMiddleware

        middleware = HistoryRequestMiddleware(fake_get_response)
        middleware(request)

        self.assertIs(captured["ctx_request"], request)

    def test_user_mutation_visible_through_context(self):
        """
        Simulates the Ninja auth timeline:
        1. Middleware captures request (user is unset / AnonymousUser).
        2. Inside get_response, Ninja auth sets request.user = real_user.
        3. Any code reading HistoricalRecords.context.request.user after that
           point (e.g. simple_history's post_save handler) sees the real user.
        """
        request = self.factory.get("/")
        fake_user = MagicMock(pk=42)
        captured = {}

        def fake_get_response(req):
            # Simulate Ninja auth mutating request.user inside the view
            req.user = fake_user
            # Now read through the context — same reference, same mutation
            captured["ctx_user"] = HistoricalRecords.context.request.user
            return HttpResponse()

        from simple_history.middleware import HistoryRequestMiddleware

        middleware = HistoryRequestMiddleware(fake_get_response)
        middleware(request)

        self.assertIs(captured["ctx_user"], fake_user)
        self.assertEqual(captured["ctx_user"].pk, 42)


# ---------------------------------------------------------------------------
# Ninja auth behavioral tests
# ---------------------------------------------------------------------------


class NinjaAuthBehavioralTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_session_token_populates_request_user(self):
        from apps.core.ninja_utils.auth import SessionToken

        request = self.factory.get("/")
        fake_user = MagicMock()

        with patch(
            "apps.core.ninja_utils.auth.XSessionTokenAuth.__call__",
            return_value=fake_user,
        ):
            SessionToken()(request)

        self.assertIs(request.user, fake_user)

    def test_oauth2_auth_populates_request_user(self):
        from apps.core.ninja_utils.auth import OAuth2Auth

        request = self.factory.get("/")
        fake_user = MagicMock()

        with patch.object(
            OAuth2Auth,
            "authenticate",
            return_value=(fake_user, "mock_token"),
        ):
            OAuth2Auth()(request)

        self.assertIs(request.user, fake_user)

    def test_api_key_auth_populates_request_user(self):
        from apps.core.ninja_utils.auth import ApiKeyAuth

        request = self.factory.get("/")
        fake_user = MagicMock()
        fake_api_key = MagicMock(has_expired=False, user=fake_user)

        auth = ApiKeyAuth()
        with patch.object(
            auth.model.objects,
            "get_from_key",
            return_value=fake_api_key,
        ):
            auth.authenticate(request, "test-key")

        self.assertIs(request.user, fake_user)
