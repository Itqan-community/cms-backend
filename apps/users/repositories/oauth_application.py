from __future__ import annotations

from typing import TYPE_CHECKING

from oauth2_provider.models import Application

if TYPE_CHECKING:
    from django.db.models import QuerySet


class OAuthApplicationRepository:
    def list_for_user(self, user) -> QuerySet[Application]:
        return Application.objects.filter(user=user)

    def get_for_user(self, user, app_id: int) -> Application | None:
        return Application.objects.filter(id=app_id, user=user).first()

    def name_exists_for_user(self, user, name: str, *, exclude_id: int | None = None) -> bool:
        qs = Application.objects.filter(user=user, name=name)
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return qs.exists()

    def create_for_user(self, user, name: str) -> tuple[Application, str]:
        app = Application(
            user=user,
            name=name,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )
        plain_secret = app.client_secret
        app.save()
        return app, plain_secret
