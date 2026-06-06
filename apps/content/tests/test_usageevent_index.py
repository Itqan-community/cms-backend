"""
TDD test for TD-001: content_usageevent.asset_id index.

This test must FAIL before migration 0042 is applied and PASS after.
"""

from django.test import TestCase

from apps.content.models import UsageEvent


class UsageEventAssetIdIndexTest(TestCase):
    """Assert that UsageEvent.Meta declares an index on asset_id.

    Django derives the DB-level index from Meta.indexes, so this test
    is the authoritative pre-migration gate: if the model doesn't declare
    it, no migration will create it in the DB either.
    """

    def test_asset_id_index_declared_in_model_meta(self):
        index_field_sets = [frozenset(idx.fields) for idx in UsageEvent._meta.indexes]
        self.assertIn(
            frozenset(["asset_id"]),
            index_field_sets,
            "UsageEvent.Meta.indexes must include an index on ['asset_id']. "
            "Add models.Index(fields=['asset_id']) to the Meta class and run "
            "makemigrations to create migration 0042.",
        )
