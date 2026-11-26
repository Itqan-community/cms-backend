from __future__ import annotations

import logging
from typing import TypedDict

from django.conf import settings
from django.db import transaction
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from apps.core.services.email import EmailService, email_service
from apps.publishers.models import PublisherInquiry
from apps.publishers.repositories.publisher_inquiry import PublisherInquiryRepository

logger = logging.getLogger(__name__)


class PublisherInquiryData(TypedDict):
    name: str
    organization: str
    email: str
    content_kind: str
    message: str
    language: str


class PublisherInquiryService:
    """A prospective publisher's "contact us to join" request: stored, then emailed to the Fanar team."""

    def __init__(self, repo: PublisherInquiryRepository | None = None, mailer: EmailService | None = None) -> None:
        self.repo = repo or PublisherInquiryRepository()
        self.mailer = mailer or email_service

    def submit(self, data: PublisherInquiryData) -> PublisherInquiry:
        from apps.publishers.tasks import send_publisher_inquiry_email

        inquiry = self.repo.create(**data)
        transaction.on_commit(lambda: send_publisher_inquiry_email.delay(inquiry.id))
        logger.info(f"Publisher inquiry saved [inquiry_id={inquiry.id}]")
        return inquiry

    def send_email(self, inquiry_id: int) -> None:
        inquiry = self.repo.get(inquiry_id)
        if inquiry is None:
            logger.warning(f"Publisher inquiry not found, skipping email [inquiry_id={inquiry_id}]")
            return
        self.mailer.send_email(
            subject=format_lazy(_("Publisher inquiry: {organization}"), organization=inquiry.organization),
            recipients=[settings.PUBLISHER_INQUIRY_EMAIL],
            template="emails/publisher_inquiry.html",
            context={
                "name": inquiry.name,
                "organization": inquiry.organization,
                "email": inquiry.email,
                "content_kind": inquiry.get_content_kind_display(),
                "message": inquiry.message,
                "language": inquiry.language,
            },
            reply_to=[inquiry.email],
        )
        self.repo.mark_emailed(inquiry)
