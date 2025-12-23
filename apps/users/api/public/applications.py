from typing import Literal

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
    authorization_grant_type: Literal["password", "client-credentials", "authorization-code", "implicit"] = "password"
    redirect_uris: str = ""


@router.post(
    "applications/",
    response=ApplicationResponseSchema,
    summary="Create OAuth2 Application",
    description="Register a new OAuth2 application to get client_id and client_secret",
)
def create_application(request: Request, data: ApplicationCreateSchema):
    """Create a new OAuth2 application for the authenticated user"""
    user = request.user

    # Use the grant type provided by the user (validated via schema)
    grant_type = data.authorization_grant_type

    app = Application(
        user=user,
        name=data.name,
        client_type=data.client_type,
        authorization_grant_type=grant_type,
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
