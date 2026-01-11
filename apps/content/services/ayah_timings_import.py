from __future__ import annotations

from dataclasses import dataclass
import json


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


def parse_json_bytes(data: bytes) -> tuple[int, list[AyahRow]]:
    """
    Parse an uploaded JSON payload into (surah_number, [AyahRow]).
    Expected schema:
      {
        "surah_id": 1..114,
        "ayahs": [
          {"ayah_number": int, "start": float_seconds, "end": float_seconds},
          ...
        ]
      }
    """
    payload = json.loads(data.decode("utf-8"))
    if "surah_id" not in payload:
        raise ValueError("Missing surah_id in uploaded JSON")

    surah_number = int(payload["surah_id"])
    ayahs = payload.get("ayahs") or []
    rows: list[AyahRow] = []

    for item in ayahs:
        ayah_number = int(item["ayah_number"])
        start_ms = sec_to_ms(item["start"])
        end_ms = sec_to_ms(item["end"])
        if end_ms < start_ms:
            raise ValueError(f"Invalid timing for ayah {ayah_number}: end < start")
        rows.append(
            AyahRow(
                surah_number=surah_number,
                ayah_number=ayah_number,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )

    return surah_number, rows
