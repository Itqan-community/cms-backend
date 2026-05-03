from django.conf import settings
from ninja import Schema

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.users.services.oauth_application import OAuthApplicationService

router = ItqanRouter(tags=[NinjaTag.AUTH])

_service = OAuthApplicationService()


class ApplicationInSchema(Schema):
    name: str


class ApplicationOutSchema(Schema):
    id: int
    name: str
    client_id: str


class ApplicationCreatedOutSchema(ApplicationOutSchema):
    client_secret: str  # plaintext — returned once only, never persisted in plaintext


if settings.ENABLE_OAUTH2:

    @router.post(
        "applications/",
        response=ApplicationCreatedOutSchema,
        summary="Create OAuth2 Application",
        description="Register a new OAuth2 application. The client_secret is returned once and cannot be retrieved again.",
    )
    def create_application(request: Request, data: ApplicationInSchema):
        app, plain_secret = _service.create(request.user, data.name)
        return {
            "id": app.id,
            "name": app.name,
            "client_id": app.client_id,
            "client_secret": plain_secret,
        }

    @router.get("applications/", response=list[ApplicationOutSchema], summary="List OAuth2 Applications")
    def list_applications(request: Request):
        return _service.list(request.user)

    @router.get("applications/{app_id}/", response=ApplicationOutSchema, summary="Get OAuth2 Application")
    def get_application(request: Request, app_id: int):
        return _service.get(request.user, app_id)

    @router.patch("applications/{app_id}/", response=ApplicationOutSchema, summary="Rename OAuth2 Application")
    def rename_application(request: Request, app_id: int, data: ApplicationInSchema):
        return _service.rename(request.user, app_id, data.name)

    @router.delete("applications/{app_id}/", response={204: None}, summary="Delete OAuth2 Application")
    def delete_application(request: Request, app_id: int):
        _service.delete(request.user, app_id)
        return 204, None
