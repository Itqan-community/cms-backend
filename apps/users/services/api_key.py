from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.ninja_utils.errors import ItqanError
from apps.users.repositories.api_key import ApiKeyRepository

if TYPE_CHECKING:
    from apps.users.models import APIKey

_NAME_MAX_LENGTH = 50


class ApiKeyService:
    def __init__(self, repo: ApiKeyRepository | None = None) -> None:
        self.repo = repo or ApiKeyRepository()

    def list(self, user) -> list[APIKey]:
        return list(self.repo.list_for_user(user))

    def get(self, user, key_id: str) -> APIKey:
        api_key = self.repo.get_for_user(user, key_id)
        if api_key is None:
            raise ItqanError("api_key_not_found", _("API key not found."), status_code=404)
        return api_key

    def create(self, user, name: str, expiry_date: datetime | None = None) -> tuple[APIKey, str]:
        name = self._validate_name(name)
        if self.repo.name_exists_for_user(user, name):
            raise ItqanError("api_key_name_taken", _("An API key with this name already exists."), status_code=400)
        return self.repo.create_for_user(user, name, expiry_date=expiry_date)

    def update(self, user, key_id: str, fields: dict) -> APIKey:
        api_key = self.get(user, key_id)
        if "name" in fields:
            fields["name"] = self._validate_name(fields["name"])
            if self.repo.name_exists_for_user(user, fields["name"], exclude_id=key_id):
                raise ItqanError("api_key_name_taken", _("An API key with this name already exists."), status_code=400)
        try:
            return self.repo.update(api_key, fields)
        except ValidationError as exc:
            raise ItqanError(
                "api_key_revoke_irreversible", _("A revoked API key cannot be un-revoked."), status_code=400
            ) from exc

    def delete(self, user, key_id: str) -> None:
        api_key = self.get(user, key_id)
        self.repo.delete(api_key)

    @staticmethod
    def _validate_name(name: str) -> str:
        name = name.strip()
        if not name:
            raise ItqanError("invalid_api_key_name", _("API key name must not be empty."), status_code=400)
        if len(name) > _NAME_MAX_LENGTH:
            raise ItqanError(
                "invalid_api_key_name",
                _("API key name must not exceed %(max)d characters.") % {"max": _NAME_MAX_LENGTH},
                status_code=400,
            )
        return name
