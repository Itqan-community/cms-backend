from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.utils import translation
from django.utils.html import strip_tags


def arabic_catalog_is_compiled() -> bool:
    """Whether locale/ar/LC_MESSAGES/django.mo exists.

    .mo files are gitignored, so a fresh checkout has none until compilemessages
    runs. Without it gettext silently falls back to English, which would make the
    assertions below fail with a confusing diff rather than a clear cause.
    """
    return any(Path(path, "ar", "LC_MESSAGES", "django.mo").exists() for path in settings.LOCALE_PATHS)


# Every app email extends emails/base_message.html. Most callers are tested with
# send_email mocked, so nothing else renders these templates -- a broken
# {% extends %} or a malformed {% blocktrans %} would only surface in production.
# Each entry is a template plus a context matching what its caller actually passes.
EMAIL_TEMPLATES = {
    "emails/publisher_member_invitation.html": {
        "publisher_name": "Tafsir Center",
        "invited_by_name": "Boss",
        "group_name": "Publisher Member Admin",
        "accept_url": "https://example.com/accept?token=tok",
        "expires_at": "2026-08-20",
    },
    "emails/publisher_member_activated.html": {
        "publisher_name": "Tafsir Center",
        "password": "TempPass123",
        "login_url": "https://example.com/login",
    },
    "emails/access_request_accepted.html": {"asset_name": "Hafs Mushaf"},
    "emails/access_request_rejected.html": {
        "asset_name": "Hafs Mushaf",
        "rejection_reason": "Incomplete information",
    },
    "emails/access_request_new.html": {
        "developer_name": "Dev One",
        "asset_name": "Hafs Mushaf",
        "auto_accepted": False,
        "access_requests_url": "https://example.com/requests",
    },
    "emails/asset_update.html": {
        "asset_name": "Hafs Mushaf",
        "version": "1.2.0",
        "summary": "Fixed typos",
    },
    "emails/issue_status_update.html": {
        "report_id": 7,
        "asset_name": "Hafs Mushaf",
        "old_status": "Pending",
        "new_status": "Resolved",
        "issue_url": "https://example.com/issues/7",
    },
    "emails/pending_access_requests_notification.html": {
        "count": 2,
        "access_requests_url": "https://example.com/requests",
        "requests": [
            {
                "developer_name": "Dev One",
                "asset_name": "Hafs Mushaf",
                "intended_use": "Commercial",
                "developer_access_reason": "Research",
                "created_at": "2026-08-01",
            },
            {
                "developer_name": "Dev Two",
                "asset_name": "Warsh Mushaf",
                "intended_use": "View",
                "developer_access_reason": "Study",
                "created_at": "2026-08-02",
            },
        ],
    },
    "emails/test.html": {},
}


class EmailTemplateRenderTest(SimpleTestCase):
    def test_render_where_any_app_email_should_use_shared_branding(self):
        # Arrange / Act / Assert: each template renders and inherits the shared shell.
        for template, context in EMAIL_TEMPLATES.items():
            with self.subTest(template=template):
                html = render_to_string(template, context)

                self.assertIn("background-color:#f4f8f6", html)
                self.assertIn("Thank you for using Itqan!", html)
                self.assertIn('<html lang="en" dir="ltr">', html)
                # The old bare markup had no shell; make sure it is really gone.
                self.assertNotIn("Best regards,", html)

    def test_render_where_arabic_should_flip_to_rtl_and_translate(self):
        # Arrange
        if not arabic_catalog_is_compiled():
            self.skipTest("Arabic catalog not compiled; run: manage.py compilemessages --locale ar")
        with translation.override("ar"):
            for template, context in EMAIL_TEMPLATES.items():
                with self.subTest(template=template):
                    # Act
                    html = render_to_string(template, context)

                    # Assert
                    self.assertIn('<html lang="ar" dir="rtl">', html)
                    self.assertIn("text-align:right", html)
                    self.assertIn("شكرًا لاستخدامك إتقان!", html)

    def test_render_where_stripped_to_plain_text_should_not_leak_markup(self):
        # The email service derives the plain-text part with strip_tags, so any raw
        # HTML entity or unclosed template tag shows up verbatim to the reader.
        for template, context in EMAIL_TEMPLATES.items():
            with self.subTest(template=template):
                # Act
                text = strip_tags(render_to_string(template, context))

                # Assert
                for leaked in ("&rarr;", "&nbsp;", "{%", "{{"):
                    self.assertNotIn(leaked, text)

    def test_render_pending_requests_where_count_varies_should_use_arabic_plural_forms(self):
        # Arabic has six plural forms; |pluralize could not express them.
        if not arabic_catalog_is_compiled():
            self.skipTest("Arabic catalog not compiled; run: manage.py compilemessages --locale ar")
        template = "emails/pending_access_requests_notification.html"
        base = EMAIL_TEMPLATES[template]
        expected = {
            0: "ليس لديك طلبات وصول معلقة",
            1: "لديك طلب وصول معلق واحد",
            2: "لديك طلبا وصول معلقان",
            5: "لديك 5 طلبات وصول معلقة",
            11: "لديك 11 طلب وصول معلق",
        }

        with translation.override("ar"):
            for count, phrase in expected.items():
                with self.subTest(count=count):
                    # Act
                    html = render_to_string(template, {**base, "count": count})

                    # Assert
                    self.assertIn(phrase, " ".join(strip_tags(html).split()))
