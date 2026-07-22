from __future__ import annotations

from dataclasses import dataclass

from apps.content.models import Asset


@dataclass(frozen=True, slots=True)
class RecitationInfo:
    name: str
    publisher_id: int | None
    publisher_name: str | None
    reciter: str | None
    riwayah: str | None
    qiraah: str | None


class RecitationUsageRepository:
    def get_info_by_ids(self, asset_ids: set[int]) -> dict[int, RecitationInfo]:
        if not asset_ids:
            return {}

        rows = (
            Asset.objects.filter(id__in=asset_ids)
            .select_related("publisher", "reciter", "riwayah", "qiraah")
            .values(
                "id",
                "name",
                "publisher_id",
                "publisher__name",
                "reciter__name",
                "riwayah__name",
                "qiraah__name",
            )
        )

        return {
            row["id"]: RecitationInfo(
                name=row["name"],
                publisher_id=row["publisher_id"],
                publisher_name=row["publisher__name"],
                reciter=row["reciter__name"],
                riwayah=row["riwayah__name"],
                qiraah=row["qiraah__name"],
            )
            for row in rows
        }
