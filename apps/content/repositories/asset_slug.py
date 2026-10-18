from apps.content.models import Asset, Reciter, Riwayah


class AssetSlugRepository:
    def slug_exists(self, slug: str) -> bool:
        return Asset.objects.filter(slug=slug).exists()

    def get_reciter_names(self, reciter_id: int) -> tuple[str, str]:
        """Return ``(name_en, name_ar)`` of the reciter, or empty strings when it does not exist."""
        row = Reciter.objects.filter(pk=reciter_id).values_list("name_en", "name_ar").first()
        return (row[0] or "", row[1] or "") if row else ("", "")

    def get_riwayah_names(self, riwayah_id: int) -> tuple[str, str]:
        """Return ``(name_en, name_ar)`` of the riwayah, or empty strings when it does not exist."""
        row = Riwayah.objects.filter(pk=riwayah_id).values_list("name_en", "name_ar").first()
        return (row[0] or "", row[1] or "") if row else ("", "")
