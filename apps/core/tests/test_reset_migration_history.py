from django.core.management import CommandError, call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
import pytest

from apps.core.management.commands.reset_migration_history import PRE_RESET_LEAVES
from apps.core.tests.base import BaseTestCase

OLD_CONTENT_CHAIN = ["0001_initial", "0073_assetversion_bilingual_label_summary", PRE_RESET_LEAVES["content"]]


class TestResetMigrationHistory(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.rows = MigrationRecorder(connection).migration_qs
        self.on_disk = MigrationLoader(None, ignore_no_migrations=True).disk_migrations

    def _names(self, app: str) -> set[str]:
        return set(self.rows.filter(app=app).values_list("name", flat=True))

    def _disk_names(self, app: str) -> set[str]:
        return {name for disk_app, name in self.on_disk if disk_app == app}

    def _record_old_chain(self, app: str, names: list[str]) -> None:
        self.rows.filter(app=app).delete()
        for name in names:
            self.rows.create(app=app, name=name)

    def test_leaves_where_compared_with_disk_should_all_be_gone(self):
        # Arrange / Act
        stale = [(app, leaf) for app, leaf in PRE_RESET_LEAVES.items() if (app, leaf) in self.on_disk]

        # Assert
        assert stale == []

    def test_reset_migration_history_where_old_chain_reached_leaf_should_record_new_files_only(self):
        # Arrange
        self._record_old_chain("content", OLD_CONTENT_CHAIN)

        # Act
        call_command("reset_migration_history")

        # Assert
        assert self._names("content") == self._disk_names("content")
        MigrationLoader(connection).check_consistent_history(connection)

    def test_reset_migration_history_where_old_chain_short_of_leaf_should_refuse_and_change_nothing(self):
        # Arrange
        self._record_old_chain("content", OLD_CONTENT_CHAIN[:-1])
        before = list(self.rows.order_by("id").values_list("id", "app", "name"))

        # Act / Assert
        with pytest.raises(CommandError, match="never reached"):
            call_command("reset_migration_history")
        assert list(self.rows.order_by("id").values_list("id", "app", "name")) == before

    def test_reset_migration_history_where_already_reset_should_change_nothing(self):
        # Arrange
        before = list(self.rows.order_by("id").values_list("id", "app", "name"))

        # Act
        call_command("reset_migration_history")

        # Assert
        assert list(self.rows.order_by("id").values_list("id", "app", "name")) == before
