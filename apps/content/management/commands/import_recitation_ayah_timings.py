from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...models import RecitationAyahTiming, RecitationSurahTrack


@dataclass(frozen=True)
class AyahRow:
    surah_number: int
    ayah_number: int
    start_ms: int
    end_ms: int

    @property
    def ayah_key(self) -> str:
        return f"{self.surah_number}:{self.ayah_number}"

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


def sec_to_ms(time_in_sec: float) -> int:
    return int(round(float(time_in_sec) * 1000))


def parse_json_file(path: Path) -> tuple[int, list[AyahRow]]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if "surah_id" not in payload:
        raise ValueError(f"Missing surah_id in {path.name}")

    surah_number = int(payload["surah_id"])
    ayahs = payload.get("ayahs") or []
    rows: list[AyahRow] = []

    for item in ayahs:
        ayah_number = int(item["ayah_number"])
        start_ms = sec_to_ms(item["start"])
        end_ms = sec_to_ms(item["end"])
        if end_ms < start_ms:
            raise ValueError(f"Invalid timing in {path.name} ayah {ayah_number}: end < start")
        rows.append(
            AyahRow(
                surah_number=surah_number,
                ayah_number=ayah_number,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )

    return surah_number, rows


class Command(BaseCommand):
    help = "Import per-ayah timings from JSON files and upsert RecitationAyahTiming rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--asset-id",
            type=int,
            required=True,
            help="Asset ID that owns the RecitationSurahTrack rows.",
        )
        parser.add_argument(
            "--path",
            type=str,
            required=True,
            help="Directory containing 1..114 JSON files (one per surah).",
        )
        parser.add_argument(
            "--pattern",
            type=str,
            default="*.json",
            help='Glob pattern for JSON files (default "*.json").',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and print summary without writing to DB.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="If timing exists, overwrite start/end values (otherwise keep existing).",
        )

    def handle(self, *args, **opts):
        asset_id: int = opts["asset_id"]
        base_path = Path(opts["path"])
        pattern: str = opts["pattern"]
        dry_run: bool = opts["dry_run"]
        overwrite: bool = opts["overwrite"]

        if not base_path.exists() or not base_path.is_dir():
            raise CommandError(f"--path must be an existing directory: {base_path}")

        files = sorted(base_path.glob(pattern))
        if not files:
            raise CommandError(f"No files matched {pattern} under {base_path}")

        # Preload all tracks for this asset for fast lookup
        tracks = RecitationSurahTrack.objects.filter(asset_id=asset_id).only("id", "surah_number")
        track_by_surah = {t.surah_number: t for t in tracks}

        created_total = 0
        updated_total = 0
        skipped_total = 0
        missing_tracks: list[int] = []

        with transaction.atomic():
            for f in files:
                try:
                    surah_number, rows = parse_json_file(f)
                except Exception as e:
                    raise CommandError(str(e)) from e

                track = track_by_surah.get(surah_number)
                if not track:
                    missing_tracks.append(surah_number)
                    continue

                # Fetch existing timings for this track, keyed by ayah_key
                existing = {
                    t.ayah_key: t
                    for t in RecitationAyahTiming.objects.filter(track=track).only(
                        "id", "ayah_key", "start_ms", "end_ms", "duration_ms"
                    )
                }

                to_create: list[RecitationAyahTiming] = []
                to_update: list[RecitationAyahTiming] = []

                for row in rows:
                    obj: RecitationAyahTiming = existing.get(row.ayah_key)
                    if not obj:
                        to_create.append(
                            RecitationAyahTiming(
                                track=track,
                                ayah_key=row.ayah_key,
                                start_ms=row.start_ms,
                                end_ms=row.end_ms,
                                duration_ms=row.duration_ms,
                            )
                        )
                        continue

                    if not overwrite:
                        skipped_total += 1
                        continue

                    changed = (
                        obj.start_ms != row.start_ms or obj.end_ms != row.end_ms or obj.duration_ms != row.duration_ms
                    )
                    if changed:
                        obj.start_ms = row.start_ms
                        obj.end_ms = row.end_ms
                        obj.duration_ms = row.duration_ms
                        to_update.append(obj)
                    else:
                        skipped_total += 1

                if to_create and not dry_run:
                    RecitationAyahTiming.objects.bulk_create(to_create, batch_size=2000)
                if to_update and not dry_run:
                    RecitationAyahTiming.objects.bulk_update(
                        to_update,
                        fields=["start_ms", "end_ms", "duration_ms"],
                        batch_size=2000,
                    )

                created_total += len(to_create)
                updated_total += len(to_update)

            if dry_run:
                # Ensure transaction doesn't commit anything
                transaction.set_rollback(True)

        if missing_tracks:
            missing_tracks = sorted(set(missing_tracks))
            self.stdout.write(
                self.style.WARNING(
                    f"Missing RecitationSurahTrack for surah(s): {missing_tracks} " f"(asset_id={asset_id})"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created_total}, updated={updated_total}, skipped={skipped_total}, "
                f"files={len(files)}, asset_id={asset_id}, dry_run={dry_run}, overwrite={overwrite}"
            )
        )
