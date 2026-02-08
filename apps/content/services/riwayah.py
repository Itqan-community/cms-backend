from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models import Q, QuerySet

    from apps.content.models import Riwayah
    from apps.content.repositories.base import BaseRecitationRepository


class RiwayahService:
    def __init__(self, repo: BaseRecitationRepository) -> None:
        self.repo = repo

    def get_all_riwayahs(self, publisher_q: Q, filters: Any = None) -> QuerySet[Riwayah]:
        """
        Business Logic: Retrieve all riwayahs that have READY recitations.
        """
        # Convert filter object to dictionary for the repository
        filters_dict = filters.dict(exclude_none=True) if filters and hasattr(filters, "dict") else {}

        return self.repo.list_riwayahs_qs(publisher_q=publisher_q, filters_dict=filters_dict)
