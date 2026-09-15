"""Unit tests for AuditRouter."""

from django.test import SimpleTestCase
from simple_history.models import HistoricalChanges

from config.routers import AuditRouter


class _Meta:
    def __init__(self, app_label, model_name):
        self.app_label = app_label
        self.model_name = model_name


class _StubHistorical(HistoricalChanges):
    _meta = _Meta("users", "historicaluser")


class _StubRegular:
    _meta = _Meta("users", "user")


class AuditRouterReadWriteTests(SimpleTestCase):
    def setUp(self):
        self.router = AuditRouter()

    def test_historical_model_routes_to_audit(self):
        self.assertEqual(self.router.db_for_read(_StubHistorical), "audit")
        self.assertEqual(self.router.db_for_write(_StubHistorical), "audit")

    def test_regular_model_defers(self):
        self.assertIsNone(self.router.db_for_read(_StubRegular))
        self.assertIsNone(self.router.db_for_write(_StubRegular))


class AuditRouterAllowMigrateTests(SimpleTestCase):
    def setUp(self):
        self.router = AuditRouter()

    def test_historical_model_allowed_on_audit(self):
        self.assertTrue(
            self.router.allow_migrate(
                "audit",
                "users",
                model_name="historicaluser",
                model=_StubHistorical,
            )
        )

    def test_historical_model_blocked_on_default(self):
        self.assertFalse(
            self.router.allow_migrate(
                "default",
                "users",
                model_name="historicaluser",
                model=_StubHistorical,
            )
        )

    def test_regular_model_blocked_on_audit(self):
        self.assertFalse(
            self.router.allow_migrate(
                "audit",
                "users",
                model_name="user",
                model=_StubRegular,
            )
        )

    def test_regular_model_defers_on_default(self):
        self.assertIsNone(
            self.router.allow_migrate(
                "default",
                "users",
                model_name="user",
                model=_StubRegular,
            )
        )

    def test_fallback_historical_name_routes_to_audit(self):
        self.assertTrue(self.router.allow_migrate("audit", "users", model_name="historicaluser"))

    def test_fallback_regular_name_blocked_on_audit(self):
        self.assertFalse(self.router.allow_migrate("audit", "users", model_name="user"))


class AuditRouterAllowRelationTests(SimpleTestCase):
    def test_always_defers(self):
        self.assertIsNone(AuditRouter().allow_relation(object(), object()))
