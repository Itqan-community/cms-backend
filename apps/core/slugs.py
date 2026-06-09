from django.utils.text import slugify as django_slugify
from unidecode import unidecode


def slugify_text(text: str | None, max_length: int = 50) -> str:
    """
    Build an English-based (ASCII) slug from arbitrary text.

    Arabic (or any non-Latin) input is transliterated to Latin characters
    first, so the resulting slug is always English-based. English input is
    passed through unchanged. Returns "" when no slug-able characters remain.
    """
    if not text:
        return ""
    transliterated = unidecode(text[:max_length])
    return django_slugify(transliterated)


def slugify_name(name_en: str | None, name_ar: str | None, max_length: int = 50) -> str:
    """
    Build an English-based (ASCII) slug from a bilingual name.

    Prefers the English name when it is provided, and falls back to the
    Arabic name (transliterated to Latin) otherwise. This is the single
    entry point that should be used everywhere a slug is derived from a
    name so the selection + transliteration logic stays consistent.
    """
    name = (name_en or "").strip() or (name_ar or "").strip()
    return slugify_text(name, max_length=max_length)
