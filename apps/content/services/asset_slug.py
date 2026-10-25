"""Human-friendly asset slugs: a fixed template per category, words chosen by AI.

The slug is the itqan CLI identifier (``itqan add <slug>``) and is used in file
names, so it is set once when the asset is created and never regenerated.

Templates:
    recitation   recitation-<reciter>-<riwayah>
    translation  translation-<language>-<words>
    others       <category>-<words>

This service never calls AI. The words come from the same Gemini call that
translates the create form (``POST /portal/ai/translate/`` with ``slug_for``):
:meth:`slug_prompt` describes them and :meth:`slug_from_words` turns them into
the slug the form sends back on create, where :meth:`resolve_slug` validates
it. :meth:`build_slug` is the plain-names fallback for callers that send none.
"""

from collections.abc import Callable
import logging
import re

from django.utils.translation import gettext_lazy as _

from apps.content.models import CategoryChoice
from apps.content.repositories.asset_slug import AssetSlugRepository
from apps.core.ninja_utils.errors import ItqanError
from apps.core.slugs import slugify_text

logger = logging.getLogger(__name__)

MAX_SLUG_LENGTH = 50
# Room kept for a collision suffix such as "-2005" or "-12".
SUFFIX_ROOM = 5
MAX_WORDS = 4
# Reciter (up to 4 words) plus riwayah.
MAX_RECITATION_WORDS = 6
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SLUG_WORDS_HINT = (
    "slug_words: 1 to 4 lowercase ASCII words that identify the work for a package name: transliterate "
    "Arabic proper names with their common English spelling (e.g. 'ibn kathir', 'saadi', 'madinah', 'hafs', "
    "'warsh'), keep distinguishing years or editions, and drop generic words such as 'the', 'noble', "
    "'quran', 'holy', 'printing', 'complex', 'version', 'for developers'."
)
RECITATION_SLUG_WORDS_HINT = (
    "slug_words: the reciter's name (1 to 4 words) followed by the riwayah (1 word), lowercase ASCII, "
    "transliterated with their common English spelling (e.g. 'mishary alafasy hafs')."
)


class AssetSlugService:
    def __init__(self, repo: AssetSlugRepository | None = None) -> None:
        self.repo = repo or AssetSlugRepository()

    def slug_prompt(
        self,
        *,
        category: str,
        name_ar: str,
        name_en: str,
        reciter_id: int | None = None,
        riwayah_id: int | None = None,
    ) -> str:
        """Prompt section asking the translate call for ``slug_words``."""
        if category == CategoryChoice.RECITATION:
            lines = [RECITATION_SLUG_WORDS_HINT]
            for label, loader, entity_id in (
                ("Reciter", self.repo.get_reciter_names, reciter_id),
                ("Riwayah", self.repo.get_riwayah_names, riwayah_id),
            ):
                if entity_id is not None:
                    english, arabic = loader(entity_id)
                    lines.append(f"{label}: {english or '-'} / {arabic or '-'}")
            return "\n".join(lines)
        return f"{SLUG_WORDS_HINT}\nName for the slug: {name_en.strip() or '-'} / {name_ar.strip() or '-'}"

    def slug_from_words(
        self, *, category: str, words: object, language: str = "", year: int | None = None
    ) -> str | None:
        """Unique template slug from AI ``slug_words``; ``None`` when no usable word is left."""
        if not isinstance(words, list):
            return None
        limit = MAX_RECITATION_WORDS if category == CategoryChoice.RECITATION else MAX_WORDS
        cleaned = [w for w in "-".join(slugify_text(str(w), max_length=30) for w in words).split("-") if w]
        cleaned = [w for w in cleaned if w != category][:limit]
        if not cleaned:
            return None
        slug = self._template(category, cleaned, language, year)
        logger.info("asset_slug: suggested [category=%s, slug=%s]", category, slug)
        return slug

    def build_slug(
        self,
        *,
        category: str,
        name_en: str | None,
        name_ar: str | None,
        language: str = "",
        reciter_id: int | None = None,
        riwayah_id: int | None = None,
        year: int | None = None,
    ) -> str:
        """Plain-names fallback (no AI) for creates that send no slug."""
        if category == CategoryChoice.RECITATION:
            words = self._recitation_words(reciter_id, riwayah_id)
        else:
            words = self._name_words(name_en, name_ar)
        words = [w for w in words if w != category]
        return self._template(category, words, language, year)

    def resolve_slug(
        self,
        *,
        category: str,
        requested: str | None,
        name_en: str | None,
        name_ar: str | None,
        language: str = "",
        reciter_id: int | None = None,
        riwayah_id: int | None = None,
        year: int | None = None,
    ) -> str:
        """Slug for a new asset: the validated ``requested`` one (made unique), else the plain-names template."""
        if not requested:
            return self.build_slug(
                category=category,
                name_en=name_en,
                name_ar=name_ar,
                language=language,
                reciter_id=reciter_id,
                riwayah_id=riwayah_id,
                year=year,
            )
        requested = requested.strip()
        if (
            len(requested) > MAX_SLUG_LENGTH
            or not SLUG_PATTERN.match(requested)
            or not (requested == category or requested.startswith(f"{category}-"))
        ):
            raise ItqanError(
                error_name="asset_slug_invalid",
                message=_("The package name (slug) is not valid for this asset."),
                status_code=400,
            )
        if not self.repo.slug_exists(requested):
            return requested
        # Taken since it was suggested: trim so a suffix still fits the field.
        return self._unique(self._join(requested.split("-")), year if category == CategoryChoice.RECITATION else None)

    def _template(self, category: str, words: list[str], language: str, year: int | None) -> str:
        if category == CategoryChoice.TRANSLATION and slugify_text(language):
            words = [slugify_text(language), *words]
        base = self._join([category, *words])
        return self._unique(base, year if category == CategoryChoice.RECITATION else None)

    def _recitation_words(self, reciter_id: int | None, riwayah_id: int | None) -> list[str]:
        lookups: list[tuple[Callable[[int], tuple[str, str]], int | None]] = [
            (self.repo.get_reciter_names, reciter_id),
            (self.repo.get_riwayah_names, riwayah_id),
        ]
        words: list[str] = []
        for loader, entity_id in lookups:
            if entity_id is not None:
                words.extend(self._name_words(*loader(entity_id)))
        return words

    @staticmethod
    def _name_words(name_en: str | None, name_ar: str | None) -> list[str]:
        name = (name_en or "").strip() or (name_ar or "").strip()
        return [w for w in slugify_text(name, max_length=200).split("-") if w][:MAX_WORDS]

    @staticmethod
    def _join(words: list[str]) -> str:
        """Join with '-', dropping trailing words so the slug plus a collision suffix fits the field."""
        limit = MAX_SLUG_LENGTH - SUFFIX_ROOM
        words = [w for w in words if w]
        while len(words) > 1 and len("-".join(words)) > limit:
            words.pop()
        return "-".join(words)[:limit].strip("-")

    def _unique(self, base: str, year: int | None) -> str:
        if not self.repo.slug_exists(base):
            return base
        with_year = f"{base}-{year}" if year is not None else ""
        # The year is unbounded user input: use it only when it still fits the field.
        if with_year and len(with_year) <= MAX_SLUG_LENGTH and not self.repo.slug_exists(with_year):
            return with_year
        counter = 2
        while self.repo.slug_exists(f"{base}-{counter}"):
            counter += 1
        return f"{base}-{counter}"
