"""Unit tests for apps.core.db_routers.AuditRouter."""

from django.test import SimpleTestCase

from apps.core.db_routers import AUDIT_APP_LABEL, AuditRouter


class _Meta:
    def __init__(self, app_label, model_name=""):
        self.app_label = app_label
        self.model_name = model_name


class _StubHistorical:
    _meta = _Meta(AUDIT_APP_LABEL, "historicaluser")


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

    def test_historical_app_allowed_on_audit_db(self):
        self.assertTrue(self.router.allow_migrate("audit", AUDIT_APP_LABEL))

    def test_historical_app_blocked_on_default_db(self):
        self.assertFalse(self.router.allow_migrate("default", AUDIT_APP_LABEL))

    def test_regular_app_allowed_on_default_db(self):
        self.assertTrue(self.router.allow_migrate("default", "users"))

    def test_regular_app_blocked_on_audit_db(self):
        self.assertFalse(self.router.allow_migrate("audit", "users"))


class AuditRouterAllowRelationTests(SimpleTestCase):
    def setUp(self):
        self.router = AuditRouter()

    def test_allow_relation_between_historical_models(self):
        self.assertTrue(self.router.allow_relation(_StubHistorical, _StubHistorical))

    def test_cross_database_relation_defers(self):
        self.assertIsNone(self.router.allow_relation(_StubHistorical, _StubRegular))

    def test_regular_models_relation_defers(self):
        self.assertIsNone(self.router.allow_relation(_StubRegular, _StubRegular))
