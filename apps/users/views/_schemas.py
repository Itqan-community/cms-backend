
from typing import Any

from ninja import Schema
from pydantic import AwareDatetime


class LoginSchema(Schema):
    email: str
    password: str


class TokenResponseSchema(Schema):
    access: str
    refresh: str
    user: dict[str, Any]


class RefreshTokenSchema(Schema):
    refresh: str


class UserProfileSchema(Schema):
    id: str
    email: str
    name: str
    phone: str | None= None
    is_active: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime
    
    class Config:
        from_attributes = True


class UserUpdateSchema(Schema):
    name: str|None = None
    phone: str|None = None


class RegisterSchema(Schema):
    email: str
    password: str
    name: str = ""


class OAuth2AuthorizeResponseSchema(Schema):
    authorization_url: str
    state: str
