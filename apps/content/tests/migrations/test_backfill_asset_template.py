import importlib

from apps.core.tests.base import BaseTestCase

# The module name starts with a digit, so a plain `from ... import` is illegal.
backfill = importlib.import_module("apps.content.migrations.0064_backfill_asset_template")


class FakeQuerySet:
    def __init__(self, rows):
        self.rows = rows
        self.updated_with = None

    def filter(self, **kwargs):
        return self

    def update(self, **kwargs):
        self.updated_with = kwargs
        return len(self.rows)


class FakeModel:
    def __init__(self, rows):
        self.objects = FakeQuerySet(rows)


class FakeApps:
    def __init__(self, model):
        self.model = model

    def get_model(self, app_label, model_name):
        return self.model


class BackfillAssetTemplateTests(BaseTestCase):
    def test_backfill_template_where_run_should_set_ayah(self):
        # Arrange
        model = FakeModel(rows=[1, 2, 3])
        apps_registry = FakeApps(model)

        # Act
        backfill.backfill_template(apps_registry, None)

        # Assert
        self.assertEqual(model.objects.updated_with, {"template": "ayah"})

    def test_clear_template_where_reversed_should_set_none(self):
        # Arrange
        model = FakeModel(rows=[1])
        apps_registry = FakeApps(model)

        # Act
        backfill.clear_template(apps_registry, None)

        # Assert
        self.assertEqual(model.objects.updated_with, {"template": None})
