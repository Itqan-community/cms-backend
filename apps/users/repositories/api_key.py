from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from apps.users.models import UserAPIKey

if TYPE_CHECKING:
    from django.db.models import QuerySet


class ApiKeyRepository:
    def list_for_user(self, user) -> QuerySet[UserAPIKey]:
        return UserAPIKey.objects.filter(user=user)

    def get_for_user(self, user, key_id: str) -> UserAPIKey | None:
        return UserAPIKey.objects.filter(id=key_id, user=user).first()

    def name_exists_for_user(self, user, name: str, *, exclude_id: str | None = None) -> bool:
        qs = UserAPIKey.objects.filter(user=user, name=name)
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return qs.exists()

    def create_for_user(self, user, name: str, expiry_date: datetime | None = None) -> tuple[UserAPIKey, str]:
        api_key, raw_key = UserAPIKey.objects.create_key(name=name, user=user, expiry_date=expiry_date)
        return api_key, raw_key

    def update(self, api_key: UserAPIKey, fields: dict) -> UserAPIKey:
        for attr, value in fields.items():
            setattr(api_key, attr, value)
        api_key.save(update_fields=list(fields.keys()))
        return api_key

    def delete(self, api_key: UserAPIKey) -> None:
        api_key.delete()
