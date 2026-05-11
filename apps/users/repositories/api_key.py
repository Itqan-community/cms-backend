from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from apps.users.models import APIKey

if TYPE_CHECKING:
    from django.db.models import QuerySet


class ApiKeyRepository:
    def list_for_user(self, user) -> QuerySet[APIKey]:
        return APIKey.objects.filter(user=user)

    def get_for_user(self, user, key_id: str) -> APIKey | None:
        return APIKey.objects.filter(id=key_id, user=user).first()

    def name_exists_for_user(self, user, name: str, *, exclude_id: str | None = None) -> bool:
        qs = APIKey.objects.filter(user=user, name=name)
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return qs.exists()

    def create_for_user(self, user, name: str, expiry_date: datetime | None = None) -> tuple[APIKey, str]:
        api_key, raw_key = APIKey.objects.create_key(name=name, user=user, expiry_date=expiry_date)
        return api_key, raw_key

    def update(self, api_key: APIKey, fields: dict) -> APIKey:
        for attr, value in fields.items():
            setattr(api_key, attr, value)
        api_key.save(update_fields=list(fields.keys()))
        return api_key

    def delete(self, api_key: APIKey) -> None:
        api_key.delete()
