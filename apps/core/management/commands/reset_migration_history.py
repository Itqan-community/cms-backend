from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

# Each project app's last migration before the migrations were reset to fresh initials.
#
# The old chains (content 0001-0074, publishers 0001-0016, ...) were replaced by a minimal set of
# initial migrations that build the same schema. A database migrated with the old chain already
# has that schema, so its history is rewritten to mark the new files as applied (the equivalent
# of `migrate --fake`) instead of running them. This is only safe for a database that reached the
# old leaf; anything short of it is refused rather than faked over a missing schema change.
#
# Once every environment has run this, the command and this map can be deleted.
PRE_RESET_LEAVES: dict[str, str] = {
    "content": "0074_split_version_label_summary_by_script",
    "publishers": "0016_grant_edit_content_to_editors",
    "users": "0004_apikey",
    "dependabot": "0003_webhookdelivery",
    "quran": "0002_fix_word_positions",
    "simple_history": "0005_historicalassetversion_bilingual_label_summary",
}


class Command(BaseCommand):
    help = (
        "Rewrite django_migrations rows left by the pre-reset migration chains so the new "
        "initial migrations count as applied. Idempotent; a no-op on fresh or already-reset "
        "databases. Run before `migrate`."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS)

    def handle(self, *args: Any, database: str, **kwargs: Any) -> None:
        recorder = MigrationRecorder(connections[database])
        if not recorder.has_table():
            self.stdout.write("No django_migrations table; nothing to reset.")
            return

        on_disk: dict[str, list[str]] = {}
        for app, name in sorted(MigrationLoader(None, ignore_no_migrations=True).disk_migrations):
            on_disk.setdefault(app, []).append(name)

        rows = recorder.migration_qs
        stale_apps = []
        for app, leaf in PRE_RESET_LEAVES.items():
            recorded = set(rows.filter(app=app).values_list("name", flat=True))
            # Nothing recorded: a fresh database. Only current names: already reset.
            if not recorded or recorded <= set(on_disk.get(app, [])):
                continue
            if leaf not in recorded:
                raise CommandError(
                    f"{app}: database has old migration history but never reached {leaf}. "
                    "Deploy the last release before the migration reset and migrate first."
                )
            stale_apps.append(app)

        with transaction.atomic(using=database):
            for app in stale_apps:
                rows.filter(app=app).delete()
                for name in on_disk.get(app, []):
                    recorder.record_applied(app, name)
                self.stdout.write(f"Reset {app} history to {', '.join(on_disk.get(app, []))}.")
