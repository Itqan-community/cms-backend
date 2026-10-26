"""Rebuild usage rollups from the retained traffic events (e.g. after adding a rollup column)."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.usage_tracking.services.traffic_maintenance import rebuild_rollups


class Command(BaseCommand):
    help = "Rebuild hourly and daily traffic rollups for every hour since --since that still has events."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--since", type=date.fromisoformat, required=True, help="First UTC day (YYYY-MM-DD).")

    def handle(self, *args, **options) -> None:
        rebuilt = rebuild_rollups(options["since"])
        if rebuilt is None:
            raise CommandError("The Logpush import is running; try again when it finishes.")
        self.stdout.write(f"Rebuilt {rebuilt} hour(s).")
