"""Gallery search terms: normalisation, recording and the search-terms report.

Terms are normalised so spelling variants count together, and matched to reciters, riwayat and
qira'at at report time (so a term recorded before an entity existed still gets matched).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any
import uuid

from django.http import HttpRequest

from apps.content.models import Qiraah, Reciter, Riwayah
from apps.core.utils.client_ip import client_ip
from apps.usage_tracking.models import SearchEvent
from apps.usage_tracking.repositories.search_events import SearchEventRepository
from apps.usage_tracking.services.traffic_classify import is_bot_user_agent
from apps.usage_tracking.services.traffic_identity import listener_id_for

logger = logging.getLogger(__name__)

MAX_TERM_LENGTH = 100
# A search replaces the same searcher's searches for a prefix of it within this window
# (search-as-you-type sends "ع", "عب", "عبد" ...).
TYPING_WINDOW = timedelta(seconds=30)
# Containment matches need this many characters, so "ا" does not match every name.
MIN_CONTAINED_MATCH = 3

_DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")  # tashkeel, Quranic marks, tatweel
_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي"})
_SPACES = re.compile(r"\s+")


def normalize_term(raw: str) -> str:
    text = _DIACRITICS.sub("", raw).translate(_LETTERS).casefold()
    return _SPACES.sub(" ", text).strip()[:MAX_TERM_LENGTH]


def record_search(request: HttpRequest, surface: str, raw_term: str, results: int) -> None:
    """Store one gallery search, folding away the searcher's earlier keystrokes of it."""
    term = normalize_term(raw_term)
    user_agent = request.headers.get("user-agent", "")
    if not term or is_bot_user_agent(user_agent):
        return
    now = datetime.now(UTC)
    SearchEventRepository().record(
        SearchEvent(
            occurred_at=now,
            surface=surface,
            term=term,
            results=results,
            listener_id=listener_id_for(client_ip(request) or "", user_agent, uuid.uuid4().hex),
        ),
        replaces_since=now - TYPING_WINDOW,
    )


# -- entity matching -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Entity:
    type: str  # "reciter" | "riwayah" | "qiraah"
    id: int
    label: str
    names: frozenset[str]  # normalised


def load_entities() -> list[Entity]:
    entities = []
    for type_, model in (("reciter", Reciter), ("riwayah", Riwayah), ("qiraah", Qiraah)):
        for pk, name, name_ar, name_en in model.objects.values_list("id", "name", "name_ar", "name_en"):
            names = frozenset(normalize_term(value) for value in (name, name_ar, name_en) if value)
            entities.append(Entity(type_, pk, name or name_ar or name_en or "", names - {""}))
    return entities


def match_entity(term: str, entities: list[Entity]) -> Entity | None:
    """The one entity the term names exactly, else the one whose name contains it; None if ambiguous."""
    exact = [entity for entity in entities if term in entity.names]
    if exact:
        return exact[0] if len(exact) == 1 else None
    if len(term) < MIN_CONTAINED_MATCH:
        return None
    contained = [entity for entity in entities if any(term in name for name in entity.names)]
    return contained[0] if len(contained) == 1 else None


def match_out(entity: Entity | None) -> dict[str, Any] | None:
    return None if entity is None else {"type": entity.type, "id": entity.id, "label": entity.label}
