from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.functional import Promise
from django.utils.html import strip_tags

from apps.users.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class EmailService:
    """
    Sends HTML emails via Django's email backend.

    Delivery behaviour is environment-driven through settings.EMAIL_BACKEND:
      - development / staging  →  console backend: output to stdout, no real delivery
      - production             →  SMTP backend: delivered via Mailjet

    Each recipient gets the email in their preferred language (User.preferred_language).
    Addresses that do not belong to a user get `language`, or the active language if omitted.
    Pass the subject as a lazy string (gettext_lazy / format_lazy) so it is translated too.

    Note: this service is intentionally decoupled from any specific mail provider.
    Django's backend abstraction ensures that switching providers remains a future configuration change, not a code change.
    """

    def __init__(self, fail_silently: bool = False, user_repo: UserRepository | None = None) -> None:
        self._fail_silently = fail_silently
        self._user_repo = user_repo or UserRepository()

    def send_email(
        self,
        subject: str | Promise,
        recipients: list[str],
        template: str,
        context: dict[str, Any],
        language: str | None = None,
    ) -> None:
        recipients = [addr for addr in recipients if addr]
        if not recipients:
            return

        fallback_language = language or translation.get_language() or settings.LANGUAGE_CODE
        preferred_languages = self._user_repo.get_preferred_languages(recipients)
        recipients_by_language: dict[str, list[str]] = {}
        for addr in recipients:
            recipients_by_language.setdefault(preferred_languages.get(addr.lower(), fallback_language), []).append(addr)

        connection = get_connection(fail_silently=self._fail_silently)
        messages = []
        for lang, addresses in recipients_by_language.items():
            with translation.override(lang):
                localized_subject = str(subject)
                html_body = render_to_string(template, context)
            plain_body = strip_tags(html_body)
            for addr in addresses:
                msg = EmailMultiAlternatives(
                    localized_subject, plain_body, settings.DEFAULT_FROM_EMAIL, [addr], connection=connection
                )
                msg.attach_alternative(html_body, "text/html")
                messages.append(msg)

        try:
            connection.open()
            connection.send_messages(messages)
            logger.info(f"Email sent [template={template!r}, recipients={len(recipients)}]")
        except Exception as e:
            logger.exception(f"Failed to send {len(recipients)} email(s) [template={template!r}]: {e}")
            if not self._fail_silently:
                raise
        finally:
            connection.close()


email_service = EmailService()
