"""Tests for django-simple-history configuration on tracked models (ITQ-33 / Issue #431).

Verifies:
1. All 28 mutable domain models across users, publishers, and content have
   HistoricalRecords configured.
2. Historical models are registered under app_label="simple_history" to allow
   AuditRouter to route them to the audit database.
3. AuditRouter routes all historical models to "audit" for reads and writes,
   and restricts migrations to the "audit" database.
4. The history_user_id field on all historical models is a scalar BigIntegerField
   (null=True) with no relational/foreign key constraints across databases.
5. Explicitly excluded models (UsageEvent, Sura, Ayah, Word) do not have history enabled.
6. MIGRATION_MODULES points "simple_history" to "apps.core.audit_migrations".
"""

from django.conf import settings
from django.db import models
from django.test import SimpleTestCase

from apps.content.models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    AssetLanguage,
    AssetPreview,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    AssetVersionEntry,
    ContentIssueReport,
    Distribution,
    EditorialRecommendation,
    EditorialRecommendationAsset,
    MushafLayout,
    Qiraah,
    RecitationAyahTiming,
    RecitationFolder,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
    UsageEvent,
)
from apps.core.db_routers import AuditRouter
from apps.publishers.models import (
    Domain,
    MemberLanguage,
    Publisher,
    PublisherMember,
    PublisherMemberInvitation,
)
from apps.quran.models import Ayah, Sura, Word
from apps.users.models import APIKey, Developer, User

TRACKED_MODELS = [
    # apps.users (3 models)
    User,
    APIKey,
    Developer,
    # apps.publishers (5 models)
    Publisher,
    PublisherMember,
    Domain,
    PublisherMemberInvitation,
    MemberLanguage,
    # apps.content (20 models)
    Asset,
    AssetLanguage,
    AssetVersion,
    AssetVersionEntry,
    AssetVersionChange,
    AssetVersionChangeReview,
    AssetPreview,
    AssetAccessRequest,
    AssetAccess,
    Distribution,
    Reciter,
    Qiraah,
    Riwayah,
    MushafLayout,
    RecitationFolder,
    RecitationSurahTrack,
    RecitationAyahTiming,
    ContentIssueReport,
    EditorialRecommendation,
    EditorialRecommendationAsset,
]

EXCLUDED_MODELS = [
    UsageEvent,
    Sura,
    Ayah,
    Word,
]


class TrackedModelsHistoryConfigurationTests(SimpleTestCase):
    def test_tracked_models_count_where_inspected_should_equal_twenty_eight(self):
        """Verify that exactly 28 models are included in the tracked models list."""
        # Arrange
        expected_count = 28

        # Act
        actual_count = len(TRACKED_MODELS)

        # Assert
        self.assertEqual(
            actual_count,
            expected_count,
            f"Expected {expected_count} tracked models, found {actual_count}.",
        )

    def test_tracked_models_where_inspected_should_have_historical_records_descriptor(self):
        """Each tracked model must define a history attribute using HistoricalRecords."""
        for model in TRACKED_MODELS:
            # Arrange
            model_name = model._meta.label

            # Act
            has_history = hasattr(model, "history")
            history_attr = getattr(model, "history", None)

            # Assert
            with self.subTest(model=model_name):
                self.assertTrue(
                    has_history,
                    f"Model {model_name} is missing 'history' attribute.",
                )
                self.assertIsInstance(
                    history_attr,
                    models.Manager,
                    f"Model {model_name}.history is not an instance of models.Manager.",
                )
                self.assertTrue(
                    hasattr(history_attr, "model"),
                    f"Model {model_name}.history does not reference a historical model.",
                )

    def test_historical_models_where_app_label_inspected_should_belong_to_simple_history(self):
        """Historical models must have app_label='simple_history' for routing."""
        for model in TRACKED_MODELS:
            # Arrange
            model_name = model._meta.label
            historical_model = model.history.model

            # Act
            app_label = historical_model._meta.app_label

            # Assert
            with self.subTest(model=model_name):
                self.assertEqual(
                    app_label,
                    "simple_history",
                    f"Historical model for {model_name} has app_label='{app_label}', expected 'simple_history'.",
                )

    def test_audit_router_where_historical_models_routed_should_return_audit_db(self):
        """AuditRouter must route both read and write queries for historical models to 'audit'."""
        # Arrange
        router = AuditRouter()

        for model in TRACKED_MODELS:
            # Arrange
            historical_model = model.history.model
            model_name = model._meta.label

            # Act
            read_db = router.db_for_read(historical_model)
            write_db = router.db_for_write(historical_model)

            # Assert
            with self.subTest(model=model_name):
                self.assertEqual(
                    read_db,
                    "audit",
                    f"AuditRouter.db_for_read({model_name}.history.model) did not return 'audit'.",
                )
                self.assertEqual(
                    write_db,
                    "audit",
                    f"AuditRouter.db_for_write({model_name}.history.model) did not return 'audit'.",
                )

    def test_audit_router_where_migration_allowed_should_allow_audit_and_deny_default(self):
        """AuditRouter must only allow simple_history migrations on the 'audit' database."""
        # Arrange
        router = AuditRouter()

        # Act
        allow_audit = router.allow_migrate("audit", "simple_history")
        allow_default = router.allow_migrate("default", "simple_history")

        # Assert
        self.assertTrue(
            allow_audit,
            "AuditRouter.allow_migrate('audit', 'simple_history') should be True.",
        )
        self.assertFalse(
            allow_default,
            "AuditRouter.allow_migrate('default', 'simple_history') should be False.",
        )

    def test_history_user_id_where_historical_field_inspected_should_be_bigint_without_relation(self):
        """history_user_id must be a scalar BigIntegerField(null=True) with no relational constraint."""
        for model in TRACKED_MODELS:
            # Arrange
            model_name = model._meta.label
            historical_model = model.history.model

            # Act
            user_field = historical_model._meta.get_field("history_user_id")

            # Assert
            with self.subTest(model=model_name):
                self.assertIsInstance(
                    user_field,
                    models.BigIntegerField,
                    f"Field history_user_id on {model_name}.history.model is not BigIntegerField.",
                )
                self.assertTrue(
                    user_field.null,
                    f"Field history_user_id on {model_name}.history.model must allow null.",
                )
                self.assertFalse(
                    user_field.is_relation,
                    f"Field history_user_id on {model_name}.history.model must not be a relational field.",
                )

    def test_excluded_models_where_inspected_should_not_have_history_descriptor(self):
        """Excluded models (UsageEvent, Sura, Ayah, Word) must not have history configured."""
        for model in EXCLUDED_MODELS:
            # Arrange
            model_name = model._meta.label

            # Act
            has_history = hasattr(model, "history")

            # Assert
            with self.subTest(model=model_name):
                self.assertFalse(
                    has_history,
                    f"Excluded model {model_name} should not have 'history' attribute.",
                )

    def test_migration_modules_setting_where_inspected_should_point_simple_history_to_audit_migrations(self):
        """settings.MIGRATION_MODULES must map 'simple_history' to 'apps.core.audit_migrations'."""
        # Arrange & Act
        migration_modules = getattr(settings, "MIGRATION_MODULES", {})

        # Assert
        self.assertEqual(
            migration_modules.get("simple_history"),
            "apps.core.audit_migrations",
            "settings.MIGRATION_MODULES['simple_history'] is not mapped to 'apps.core.audit_migrations'.",
        )
