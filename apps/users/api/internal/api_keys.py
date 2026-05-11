from typing import Literal

from django.conf import settings
from ninja import Schema
from pydantic import AwareDatetime

from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.users.services.api_key import ApiKeyService

router = ItqanRouter(tags=[NinjaTag.AUTH])

_service = ApiKeyService()


class ApiKeyOutSchema(Schema):
    id: str
    name: str
    revoked: bool
    expiry_date: AwareDatetime | None = None
    created: AwareDatetime


class ApiKeyCreatedOutSchema(ApiKeyOutSchema):
    key: str  # plaintext — returned once only, never stored in plaintext


class ApiKeyCreateInSchema(Schema):
    name: str
    expiry_date: AwareDatetime | None = None


class ApiKeyPatchInSchema(Schema):
    name: str | None = None
    expiry_date: AwareDatetime | None = None
    revoked: bool | None = None


if settings.ENABLE_API_KEY_AUTH:

    @router.post(
        "api-keys/",
        response={
            201: ApiKeyCreatedOutSchema,
            400: NinjaErrorResponse[Literal["invalid_api_key_name"]]
            | NinjaErrorResponse[Literal["api_key_name_taken"]],
        },
        summary="Create API Key",
        description="Create a new API key. The raw key is returned once and cannot be retrieved again.",
    )
    def create_api_key(request: Request, data: ApiKeyCreateInSchema):
        api_key, raw_key = _service.create(request.user, data.name, expiry_date=data.expiry_date)
        return 201, ApiKeyCreatedOutSchema(
            id=api_key.id,
            name=api_key.name,
            revoked=api_key.revoked,
            expiry_date=api_key.expiry_date,
            created=api_key.created,
            key=raw_key,
        )

    @router.get(
        "api-keys/",
        response=list[ApiKeyOutSchema],
        summary="List API Keys",
    )
    def list_api_keys(request: Request):
        return _service.list(request.user)

    @router.get(
        "api-keys/{key_id}/",
        response={
            200: ApiKeyOutSchema,
            404: NinjaErrorResponse[Literal["api_key_not_found"]],
        },
        summary="Get API Key",
    )
    def get_api_key(request: Request, key_id: str):
        return _service.get(request.user, key_id)

    @router.patch(
        "api-keys/{key_id}/",
        response={
            200: ApiKeyOutSchema,
            400: NinjaErrorResponse[Literal["invalid_api_key_name"]]
            | NinjaErrorResponse[Literal["api_key_name_taken"]]
            | NinjaErrorResponse[Literal["api_key_revoke_irreversible"]],
            404: NinjaErrorResponse[Literal["api_key_not_found"]],
        },
        summary="Update API Key",
    )
    def update_api_key(request: Request, key_id: str, data: ApiKeyPatchInSchema):
        fields = data.model_dump(exclude_unset=True)
        return _service.update(request.user, key_id, fields)

    @router.delete(
        "api-keys/{key_id}/",
        response={
            204: None,
            404: NinjaErrorResponse[Literal["api_key_not_found"]],
        },
        summary="Delete API Key",
    )
    def delete_api_key(request: Request, key_id: str):
        _service.delete(request.user, key_id)
        return 204, None
