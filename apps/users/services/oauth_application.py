from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.translation import gettext_lazy as _
from oauth2_provider.models import Application

from apps.core.ninja_utils.errors import ItqanError
from apps.users.repositories.oauth_application import OAuthApplicationRepository

if TYPE_CHECKING:
    from django.db.models import QuerySet


_NAME_MAX_LENGTH = 120


class OAuthApplicationService:
    def __init__(self, repo: OAuthApplicationRepository | None = None) -> None:
        self.repo = repo or OAuthApplicationRepository()

    def list(self, user) -> QuerySet[Application]:
        return self.repo.list_for_user(user)

    def get(self, user, app_id: int) -> Application:
        app = self.repo.get_for_user(user, app_id)
        if app is None:
            raise ItqanError("application_not_found", _("Application not found."), status_code=404)
        return app

    def create(self, user, name: str) -> tuple[Application, str]:
        name = self._validate_name(name)
        if self.repo.name_exists_for_user(user, name):
            raise ItqanError("application_name_taken", _("An application with this name already exists."))
        return self.repo.create_for_user(user, name)

    def rename(self, user, app_id: int, name: str) -> Application:
        name = self._validate_name(name)
        app = self.get(user, app_id)
        if self.repo.name_exists_for_user(user, name, exclude_id=app_id):
            raise ItqanError("application_name_taken", _("An application with this name already exists."))
        app.name = name
        app.save(update_fields=["name"])
        return app

    def delete(self, user, app_id: int) -> None:
        app = self.get(user, app_id)
        app.delete()

    @staticmethod
    def _validate_name(name: str) -> str:
        name = name.strip()
        if not name:
            raise ItqanError("invalid_application_name", _("Application name must not be empty."))
        if len(name) > _NAME_MAX_LENGTH:
            raise ItqanError(
                "invalid_application_name",
                _("Application name must not exceed %(max)d characters.") % {"max": _NAME_MAX_LENGTH},
            )
        return name
