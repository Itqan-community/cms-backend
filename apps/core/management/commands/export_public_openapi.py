import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Export the developers_api OpenAPI schema to a JSON file."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--out", required=True, type=str)

    def handle(self, *args: Any, out: str, **kwargs: Any) -> None:
        from config.developers_api import developers_api

        schema = developers_api.get_openapi_schema()
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(schema, indent=2, ensure_ascii=False))
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))
