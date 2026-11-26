from __future__ import annotations

import logging
from typing import TypedDict

from django.conf import settings
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from apps.core.services.email import EmailService, email_service

logger = logging.getLogger(__name__)


class PublisherInquiry(TypedDict):
    name: str
    organization: str
    email: str
    content_kind: str
    message: str
    language: str


class PublisherInquiryService:
    """A prospective publisher's "contact us to join" request from the landing page, emailed to the Fanar team."""

    def __init__(self, mailer: EmailService | None = None) -> None:
        self.mailer = mailer or email_service

    def submit(self, inquiry: PublisherInquiry) -> None:
        from apps.publishers.tasks import send_publisher_inquiry_email

        send_publisher_inquiry_email.delay(dict(inquiry))
        logger.info(f"Publisher inquiry queued [organization={inquiry['organization']!r}]")

    def send_email(self, inquiry: PublisherInquiry) -> None:
        self.mailer.send_email(
            subject=format_lazy(_("Publisher inquiry: {organization}"), organization=inquiry["organization"]),
            recipients=[settings.PUBLISHER_INQUIRY_EMAIL],
            template="emails/publisher_inquiry.html",
            context=dict(inquiry),
            reply_to=[inquiry["email"]],
        )
