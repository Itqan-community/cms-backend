from __future__ import annotations

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.content.models import AssetVersion


@dataclass(frozen=True)
class VersionText:
    """A tafsir/translation version's bilingual name (``label``) and summary.

    Written field by field so neither language is lost: assigning the plain
    ``label`` / ``summary`` would only set the active language (modeltranslation).
    """

    label_en: str = ""
    label_ar: str = ""
    summary_en: str = ""
    summary_ar: str = ""

    @classmethod
    def field_names(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    @classmethod
    def of(cls, version: AssetVersion | None) -> VersionText:
        """The text of ``version`` (empty when there is none)."""
        if version is None:
            return cls()
        return cls(**{name: getattr(version, name) or "" for name in cls.field_names()})

    @classmethod
    def from_data(cls, data: Any, prefix: str = "") -> VersionText:
        """Read ``<prefix>label_en`` … ``<prefix>summary_ar`` off a request schema."""
        return cls(**{name: getattr(data, f"{prefix}{name}", None) or "" for name in cls.field_names()})

    def as_fields(self) -> dict[str, str]:
        """Model field values, whitespace-trimmed."""
        return {name: getattr(self, name).strip() for name in self.field_names()}

    @property
    def has_summary(self) -> bool:
        return bool(self.summary_en.strip() or self.summary_ar.strip())
