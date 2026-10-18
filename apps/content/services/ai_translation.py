"""Arabic → English translation of asset metadata for portal create forms.

``translate`` mode: one Gemini JSON call. With ``slug_for`` the same call also
returns the words of the new asset's package slug (one call per click).
``web`` mode: the same call, plus the intro of the matching Arabic / English
Wikipedia articles as reference notes (free; Google Search grounding is not on
the Gemini free tier for new projects). Nothing found → plain translation.
"""

from dataclasses import dataclass, field
import logging

from django.utils.translation import gettext_lazy as _

from apps.content.services.asset_slug import AssetSlugService
from apps.core.gemini import GeminiClient, GeminiError, GeminiQuotaExceeded, GeminiRateLimited
from apps.core.ninja_utils.errors import ItqanError
from apps.core.wikipedia import WikiArticle, WikipediaClient

logger = logging.getLogger(__name__)

WEB_FIELDS = {"description", "long_description", "bio"}
# A reciter is not an asset: it has no package slug.
SLUG_CATEGORIES = {"mushaf", "tafsir", "translation", "font", "recitation"}
FIELD_HINTS = {
    "name": "the asset or person name: transliterate proper names, translate generic words",
    "description": "a short description (1-3 sentences)",
    "long_description": "a detailed description (1-4 paragraphs)",
    "bio": "a short factual biography of the reciter",
    "version_name": "a short version label",
    "version_summary": "a one-line version summary",
}
SYSTEM_PROMPT = (
    "You translate Arabic metadata of Quranic digital assets (mushafs, tafsirs, Quran translations, "
    "fonts, recitations, reciters) into clear English for a developer catalog. Transliterate names of "
    "people, books, riwayahs and qiraahs using their common English spelling (e.g. 'Mishary Rashid "
    "Alafasy', 'Hafs an Asim', 'Tafsir Ibn Kathir', 'Al-Muyassar'), never translate them literally. "
    "Keep standard Islamic terms transliterated (tafsir, riwayah, qiraah, mushaf). Do not invent facts."
)


@dataclass(frozen=True)
class TranslationResult:
    fields: dict[str, str]
    sources: list[str] = field(default_factory=list)
    slug: str | None = None


class AiTranslationService:
    def __init__(
        self,
        client: GeminiClient | None = None,
        wikipedia: WikipediaClient | None = None,
        slugs: AssetSlugService | None = None,
    ) -> None:
        self.client = client or GeminiClient()
        self.wikipedia = wikipedia or WikipediaClient()
        self.slugs = slugs or AssetSlugService()

    def translate(
        self,
        *,
        mode: str,
        category: str,
        fields: dict[str, str],
        context: dict[str, str],
        slug_for: dict | None = None,
    ) -> TranslationResult:
        source = {k: (v or "").strip() for k, v in fields.items() if k in FIELD_HINTS and (v or "").strip()}
        slug_for = slug_for if category in SLUG_CATEGORIES else None
        wants_slug = bool(
            slug_for
            and (
                (slug_for.get("name_ar") or "").strip()
                or (slug_for.get("name_en") or "").strip()
                or slug_for.get("reciter_id")
            )
        )
        if not source and not wants_slug:
            raise ItqanError(
                error_name="ai_translate_empty",
                message=_("Fill in at least one Arabic field to translate."),
                status_code=400,
            )
        # Web mode also writes description-like fields the admin left empty in Arabic.
        targets = set(source) | ({k for k in fields if k in WEB_FIELDS} if mode == "web" else set())
        described = "\n".join(f"{k} (Arabic): {v}" for k, v in source.items())
        extra = "\n".join(f"{k}: {v.strip()}" for k, v in context.items() if (v or "").strip())
        # A recitation's own title is generic ("تلاوة ..."): the reciter is what Wikipedia knows.
        subject = (context.get("reciter") or "").strip() if category == "recitation" else ""
        articles = self.wikipedia.lookup(subject or source.get("name", "")) if mode == "web" else []
        properties: dict[str, dict] = {k: {"type": "STRING", "description": FIELD_HINTS[k]} for k in sorted(targets)}
        slug_hint = ""
        if wants_slug and slug_for:
            properties["slug_words"] = {"type": "ARRAY", "items": {"type": "STRING"}}
            slug_hint = self.slugs.slug_prompt(
                category=category,
                name_ar=slug_for.get("name_ar") or "",
                name_en=slug_for.get("name_en") or "",
                reciter_id=slug_for.get("reciter_id"),
                riwayah_id=slug_for.get("riwayah_id"),
            )
        try:
            result = self.client.generate_json(
                system=SYSTEM_PROMPT,
                prompt=self._prompt(category, described, extra, targets, articles, slug_hint),
                schema={"type": "OBJECT", "properties": properties, "required": list(properties)},
            )
        except GeminiQuotaExceeded:
            raise ItqanError(
                error_name="ai_quota_exceeded",
                message=_("The free daily AI limit has been reached. Try again tomorrow."),
                status_code=429,
            ) from None
        except GeminiRateLimited:
            raise ItqanError(
                error_name="ai_rate_limited",
                message=_("Too many AI requests right now. Wait a minute and try again."),
                status_code=429,
            ) from None
        except GeminiError as exc:
            logger.warning("ai_translation: failed [mode=%s, category=%s, error=%s]", mode, category, exc)
            raise ItqanError(
                error_name="ai_unavailable",
                message=_("The AI service is unavailable right now. Try again later."),
                status_code=503,
            ) from None
        translated = {k: str(v).strip() for k, v in result.items() if k in targets and v is not None and str(v).strip()}
        slug = (
            self.slugs.slug_from_words(
                category=category,
                words=result.get("slug_words"),
                language=slug_for.get("language") or "",
                year=slug_for.get("year"),
            )
            if wants_slug and slug_for
            else None
        )
        logger.info(
            "ai_translation: done [mode=%s, category=%s, fields=%s, slug=%s]", mode, category, sorted(translated), slug
        )
        return TranslationResult(fields=translated, sources=[article.url for article in articles], slug=slug)

    @staticmethod
    def _prompt(
        category: str, described: str, extra: str, targets: set[str], articles: list[WikiArticle], slug_hint: str
    ) -> str:
        lines = [f"Category: {category}", described] if described else [f"Category: {category}"]
        if extra:
            lines.append(f"Context:\n{extra}")
        if articles:
            notes = "\n\n".join(article.extract for article in articles)
            lines.append(
                "Reference notes from Wikipedia (write description, long_description and bio from these, in your "
                "own words; use only facts they state, and ignore them if they are about something else):\n" + notes
            )
        if targets:
            lines.append(f"Return English values for: {', '.join(sorted(targets))}.")
        if slug_hint:
            lines.append(slug_hint)
        return "\n\n".join(lines)
