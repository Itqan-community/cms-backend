"""Portal: the mushaf text of a range, shown while a publisher picks a group's range."""

from typing import Literal

from ninja import Schema

from apps.content.models import AssetTemplateChoice
from apps.content.services.asset_templates import QuranPosition, unit_spec_for_template
from apps.content.unit_keys import decode_group_key
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission
from apps.core.permissions import PermissionChoice
from apps.quran.models import Ayah, Word

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])

# Units returned for one range; a longer range is cut here and flagged `truncated`.
QURAN_RANGE_LIMIT = 1000


class QuranRangeUnitOut(Schema):
    surah: int
    ayah: int
    word: int | None = None
    text: str


class QuranRangeOut(Schema):
    units: list[QuranRangeUnitOut]
    truncated: bool


@router.get(
    "content/quran-range/",
    response={200: QuranRangeOut, 400: NinjaErrorResponse[Literal["group_range_invalid"]]},
)
def quran_range(
    request: Request,
    from_surah: int,
    from_ayah: int,
    to_surah: int,
    to_ayah: int,
    from_word: int | None = None,
    to_word: int | None = None,
):
    """The ayahs (or, with both word params, the words) of a range, in mushaf order."""
    check_permission(request.user, PermissionChoice.PORTAL_READ_TAFSIR, raise_exception=True)
    words = from_word is not None or to_word is not None
    spec = unit_spec_for_template(AssetTemplateChoice.WORD_GROUP if words else AssetTemplateChoice.AYAH_GROUP)
    key = spec.key_for_range(
        QuranPosition(surah=from_surah, ayah=from_ayah, word=from_word),
        QuranPosition(surah=to_surah, ayah=to_ayah, word=to_word),
    )
    start, end = decode_group_key(key)
    if words:
        rows = Word.objects.filter(id__range=(start, end)).order_by("id")
        units = [
            {"surah": sura, "ayah": aya, "word": position, "text": text}
            for sura, aya, position, text in rows.values_list(
                "sura_id", "ayah__number_in_sura", "position_in_ayah", "text"
            )[: QURAN_RANGE_LIMIT + 1]
        ]
    else:
        rows = Ayah.objects.filter(id__range=(start, end)).order_by("id")
        units = [
            {"surah": sura, "ayah": aya, "word": None, "text": text}
            for sura, aya, text in rows.values_list("sura_id", "number_in_sura", "text")[: QURAN_RANGE_LIMIT + 1]
        ]
    return {"units": units[:QURAN_RANGE_LIMIT], "truncated": len(units) > QURAN_RANGE_LIMIT}
