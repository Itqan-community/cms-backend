from typing import Literal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from ninja import Field, Schema
from pydantic import field_validator

from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.schemas import OkSchema
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.throttle import PublisherInquiryAnonRateThrottle
from apps.publishers.services.publisher_inquiry import PublisherInquiryService

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])

inquiry_throttle = PublisherInquiryAnonRateThrottle()

ContentKind = Literal["recitations", "mushafs", "text", "fonts", "several"]


class PublisherInquiryIn(Schema):
    name: str = Field(..., min_length=1, max_length=200)
    organization: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., max_length=254)
    content_kind: ContentKind
    message: str = Field("", max_length=5000)
    # Honeypot: hidden from people on the form, so a filled value means a bot.
    website: str = Field("", max_length=500)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        value = value.strip()
        try:
            validate_email(value)
        except DjangoValidationError as exc:
            raise ValueError("Enter a valid email address.") from exc
        return value

    @field_validator("name", "organization")
    @classmethod
    def check_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("This field is required.")
        return value.strip()


@router.post(
    "publisher-inquiries/",
    response={
        200: OkSchema,
        400: NinjaErrorResponse[Literal["validation_error"]],
        429: NinjaErrorResponse[Literal["throttled"]],
    },
    auth=None,
    throttle=[inquiry_throttle],
)
def create_publisher_inquiry(request: Request, data: PublisherInquiryIn):
    """A prospective publisher's "contact us to join" request; emailed to the Fanar team (PUBLISHER_INQUIRY_EMAIL)."""
    if not data.website:
        PublisherInquiryService().submit(
            {
                "name": data.name,
                "organization": data.organization,
                "email": data.email,
                "content_kind": data.content_kind,
                "message": data.message.strip(),
                "language": translation.get_language() or "",
            }
        )
    return OkSchema(message=str(_("Thank you. We will get back to you soon.")))
