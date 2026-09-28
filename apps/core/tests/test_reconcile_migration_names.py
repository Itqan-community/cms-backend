from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

from apps.core.management.commands.reconcile_migration_names import RENAMED_MIGRATIONS
from apps.core.tests.base import BaseTestCase

OLD_IS_VISIBLE = "0053_recitationfolder_is_visible"
NEW_IS_VISIBLE = "0054_recitationfolder_is_visible"


class TestReconcileMigrationNames(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.rows = MigrationRecorder(connection).migration_qs

    def _names(self):
        return set(self.rows.filter(app="content").values_list("name", flat=True))

    def test_map_whenCompared_shouldPointFromMissingFilesToExistingFiles(self):
        # Arrange
        on_disk = MigrationLoader(None, ignore_no_migrations=True).disk_migrations

        # Act / Assert
        for app, renames in RENAMED_MIGRATIONS.items():
            assert not set(renames) & set(renames.values())
            for old, new in renames.items():
                assert (app, old) not in on_disk
                assert (app, new) in on_disk

    def test_reconcile_whenOnlyOldNameRecorded_shouldRenameRow(self):
        # Arrange
        self.rows.filter(app="content", name=NEW_IS_VISIBLE).delete()
        self.rows.create(app="content", name=OLD_IS_VISIBLE)

        # Act
        call_command("reconcile_migration_names")

        # Assert
        names = self._names()
        assert NEW_IS_VISIBLE in names
        assert OLD_IS_VISIBLE not in names

    def test_reconcile_whenBothNamesRecorded_shouldDropOldRow(self):
        # Arrange
        self.rows.create(app="content", name=OLD_IS_VISIBLE)

        # Act
        call_command("reconcile_migration_names")

        # Assert
        assert self.rows.filter(app="content", name=NEW_IS_VISIBLE).count() == 1
        assert OLD_IS_VISIBLE not in self._names()

    def test_reconcile_whenOnlyNewNamesRecorded_shouldChangeNothing(self):
        # Arrange
        before = list(self.rows.order_by("id").values_list("id", "app", "name"))

        # Act
        call_command("reconcile_migration_names")

        # Assert
        assert list(self.rows.order_by("id").values_list("id", "app", "name")) == before

    def test_reconcile_whenStagingShaped_shouldLeaveNoUnappliedAncestors(self):
        # Arrange: staging recorded every renamed migration under its old name.
        renames = RENAMED_MIGRATIONS["content"]
        self.rows.filter(app="content", name__in=renames.values()).delete()
        for old in renames:
            self.rows.create(app="content", name=old)

        # Act
        call_command("reconcile_migration_names")

        # Assert
        loader = MigrationLoader(connection)
        loader.check_consistent_history(connection)
        assert set(renames.values()) <= self._names()
