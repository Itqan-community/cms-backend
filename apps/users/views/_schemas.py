
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
    is_profile_completed: bool
    bio: str = ""
    project_summary: str = ""
    project_url: str = ""
    job_title: str = ""
    created_at: AwareDatetime
    updated_at: AwareDatetime
    
    class Config:
        from_attributes = True


class UserUpdateSchema(Schema):
    bio: str = ""
    project_summary: str = ""
    project_url: str = ""


class RegisterSchema(Schema):
    email: str
    password: str
    name: str = ""
    phone: str = ""
    job_title: str = ""


class OAuth2AuthorizeResponseSchema(Schema):
    authorization_url: str
    state: str
