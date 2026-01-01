from typing import Literal

from django.conf import settings
from django.shortcuts import get_object_or_404
from ninja import Schema
from oauth2_provider.models import Application

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.AUTH])


class ApplicationResponseSchema(Schema):
    id: int
    name: str
    client_id: str
    client_secret: str
    client_type: str
    authorization_grant_type: str
    redirect_uris: str


class ApplicationCreateSchema(Schema):
    name: str
    client_type: Literal["confidential", "public"] = "confidential"
    authorization_grant_type: Literal["password", "client-credentials", "authorization-code"] = "password"
    redirect_uris: str = ""


class ApplicationUpdateSchema(Schema):
    name: str | None = None
    client_type: Literal["confidential", "public"] | None = None
    authorization_grant_type: Literal["password", "client-credentials", "authorization-code"] | None = None
    redirect_uris: str | None = None


if settings.ENABLE_OAUTH2:

    @router.post(
        "applications/",
        response=ApplicationResponseSchema,
        summary="Create OAuth2 Application",
        description="Register a new OAuth2 application to get client_id and client_secret",
    )
    def create_application(request: Request, data: ApplicationCreateSchema):
        """Create a new OAuth2 application for the authenticated user"""
        user = request.user

        app = Application(
            user=user,
            name=data.name,
            client_type=data.client_type,
            authorization_grant_type=data.authorization_grant_type,
            redirect_uris=data.redirect_uris,
        )
        # Generate and capture plain text secret before hashing on save
        plain_text_secret = app.client_secret
        app.save()

        return {
            "id": app.id,
            "name": app.name,
            "client_id": app.client_id,
            "client_secret": plain_text_secret,
            "client_type": app.client_type,
            "authorization_grant_type": app.authorization_grant_type,
            "redirect_uris": app.redirect_uris,
        }

    @router.get("applications/", response=list[ApplicationResponseSchema], summary="List OAuth2 Applications")
    def list_applications(request: Request):
        """List all OAuth2 applications owned by the user"""
        return Application.objects.filter(user=request.user)

    @router.get("applications/{app_id}/", response=ApplicationResponseSchema, summary="Get OAuth2 Application")
    def get_application(request: Request, app_id: int):
        """Get details of a specific OAuth2 application"""
        return get_object_or_404(Application, id=app_id, user=request.user)

    @router.put("applications/{app_id}/", response=ApplicationResponseSchema, summary="Update OAuth2 Application")
    def update_application(request: Request, app_id: int, data: ApplicationUpdateSchema):
        """Update an existing OAuth2 application"""
        app = get_object_or_404(Application, id=app_id, user=request.user)

        for attr, value in data.dict(exclude_unset=True).items():
            setattr(app, attr, value)

        app.save()
        return app

    @router.delete("applications/{app_id}/", response={204: None}, summary="Delete OAuth2 Application")
    def delete_application(request: Request, app_id: int):
        """Delete an OAuth2 application"""
        app = get_object_or_404(Application, id=app_id, user=request.user)
        app.delete()
        return 204, None
