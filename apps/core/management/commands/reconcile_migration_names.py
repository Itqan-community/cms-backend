from typing import Any

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

# Applied-migration rows recorded under a name that was later renamed on disk.
#
# The content 0050-0053 files were renumbered on main (release/2026-09-02) after staging
# had already applied them under their old names; production applied them under the new
# names. Without renaming staging's rows, `migrate` sees 0054_recitationfolder_is_visible as
# unapplied and fails re-adding a column that already exists.
#
# Old and new names must stay disjoint so a rename can never collide with another pair.
RENAMED_MIGRATIONS: dict[str, dict[str, str]] = {
    "content": {
        "0050_assetversionentry_assetversion_created_by_and_more": "0051_assetversionentry_assetversion_created_by_and_more",
        "0051_assetversion_content_edited": "0052_assetversion_content_edited",
        "0052_merge_20260826_1701": "0053_merge_20260826_1701",
        "0053_recitationfolder_is_visible": "0054_recitationfolder_is_visible",
    },
}


class Command(BaseCommand):
    help = (
        "Rename django_migrations rows recorded under a migration's pre-rename name. "
        "Idempotent; a no-op on databases that already use the current names. "
        "Run before `migrate`."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS)

    def handle(self, *args: Any, database: str, **kwargs: Any) -> None:
        connection = connections[database]
        recorder = MigrationRecorder(connection)
        if not recorder.has_table():
            self.stdout.write("No django_migrations table; nothing to reconcile.")
            return

        on_disk = MigrationLoader(None, ignore_no_migrations=True).disk_migrations
        rows = recorder.migration_qs
        with transaction.atomic(using=database):
            for app, renames in RENAMED_MIGRATIONS.items():
                for old, new in renames.items():
                    # Never touch a row whose old name is still a real migration, or whose
                    # new name isn't one: that would mean this map is stale.
                    if (app, old) in on_disk or (app, new) not in on_disk:
                        self.stdout.write(
                            self.style.WARNING(f"Skipping {app}.{old}: map does not match migration files.")
                        )
                        continue
                    old_rows = rows.filter(app=app, name=old)
                    if not old_rows.exists():
                        continue
                    if rows.filter(app=app, name=new).exists():
                        old_rows.delete()
                        self.stdout.write(f"Dropped duplicate {app}.{old} (already recorded as {new}).")
                    else:
                        old_rows.update(name=new)
                        self.stdout.write(f"Renamed {app}.{old} -> {new}.")
