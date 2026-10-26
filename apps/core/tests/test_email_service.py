from unittest import skipUnless

from django.core import mail
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from model_bakery import baker

from apps.core.services.email import EmailService
from apps.core.tests.base import BaseTestCase
from apps.core.tests.test_email_templates import arabic_catalog_is_compiled
from apps.users.models import LanguageChoice, User

ASSET_UPDATE_CONTEXT = {"asset_name": "Hafs Mushaf", "version": "1.2.0", "summary": ""}


def asset_update_subject() -> str:
    return format_lazy(_("New Update for {asset_name}"), asset_name="Hafs Mushaf")


@skipUnless(arabic_catalog_is_compiled(), "run compilemessages first: django.mo is gitignored")
class EmailServiceLanguageTestCase(BaseTestCase):
    def test_send_email_where_recipients_prefer_different_languages_should_send_each_in_their_language(self):
        # Arrange
        baker.make(User, email="arabic@example.com", preferred_language=LanguageChoice.ARABIC)
        baker.make(User, email="english@example.com", preferred_language=LanguageChoice.ENGLISH)

        # Act
        EmailService().send_email(
            subject=asset_update_subject(),
            recipients=["arabic@example.com", "english@example.com"],
            template="emails/asset_update.html",
            context=ASSET_UPDATE_CONTEXT,
        )

        # Assert
        sent = {message.to[0]: message for message in mail.outbox}
        self.assertEqual({"arabic@example.com", "english@example.com"}, set(sent))
        self.assertEqual("تحديث جديد لـ Hafs Mushaf", sent["arabic@example.com"].subject)
        self.assertIn('lang="ar"', sent["arabic@example.com"].alternatives[0][0])
        self.assertEqual("New Update for Hafs Mushaf", sent["english@example.com"].subject)
        self.assertIn('lang="en"', sent["english@example.com"].alternatives[0][0])

    def test_send_email_where_recipient_email_differs_in_case_should_use_their_language(self):
        # Arrange
        baker.make(User, email="english@example.com", preferred_language=LanguageChoice.ENGLISH)

        # Act
        EmailService().send_email(
            subject=asset_update_subject(),
            recipients=["English@Example.com"],
            template="emails/asset_update.html",
            context=ASSET_UPDATE_CONTEXT,
            language=LanguageChoice.ARABIC,
        )

        # Assert
        self.assertEqual(1, len(mail.outbox))
        self.assertEqual("New Update for Hafs Mushaf", mail.outbox[0].subject)

    def test_send_email_where_recipient_has_no_account_should_use_given_language(self):
        # Arrange
        recipient = "invitee@example.com"

        # Act
        EmailService().send_email(
            subject=asset_update_subject(),
            recipients=[recipient],
            template="emails/asset_update.html",
            context=ASSET_UPDATE_CONTEXT,
            language=LanguageChoice.ARABIC,
        )

        # Assert
        self.assertEqual(1, len(mail.outbox))
        self.assertEqual("تحديث جديد لـ Hafs Mushaf", mail.outbox[0].subject)
