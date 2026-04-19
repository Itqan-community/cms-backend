from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailService:
    """
    Sends HTML emails via Django's email backend.

    Delivery behaviour is environment-driven through settings.EMAIL_BACKEND:
      - development / staging  →  console backend: output to stdout, no real delivery
      - production             →  SMTP backend: delivered via Mailjet

    Note: this service is intentionally decoupled from any specific mail provider.
    Django's backend abstraction ensures that switching providers remains a future configuration change, not a code change.
    """

    def __init__(self, fail_silently: bool = False) -> None:
        self._fail_silently = fail_silently

    def send_email(
        self,
        subject: str,
        recipients: list[str],
        template: str,
        context: dict[str, Any],
    ) -> None:
        recipients = [addr for addr in recipients if addr]
        if not recipients:
            return

        html_body = render_to_string(template, context)
        plain_body = strip_tags(html_body)

        connection = get_connection(fail_silently=self._fail_silently)
        messages = [
            EmailMultiAlternatives(subject, plain_body, settings.DEFAULT_FROM_EMAIL, [addr], connection=connection)
            for addr in recipients
        ]
        for msg in messages:
            msg.attach_alternative(html_body, "text/html")

        try:
            connection.open()
            connection.send_messages(messages)
            connection.close()

        except Exception as e:
            logger.exception("Failed to send %d email(s) [subject=%r]: %s", len(recipients), subject, e)
            if not self._fail_silently:
                raise


email_service = EmailService()
