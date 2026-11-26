from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import override_settings

from apps.core.tests.base import BaseTestCase
from apps.publishers import tasks
from apps.publishers.api.internal.publisher_inquiries import inquiry_throttle
from apps.publishers.services.publisher_inquiry import PublisherInquiryService
from apps.publishers.tasks import send_publisher_inquiry_email

URL = "/cms-api/publisher-inquiries/"


def _payload(**overrides: str) -> dict[str, str]:
    payload = {
        "name": "Ahmad",
        "organization": "Tafsir Center",
        "email": "ahmad@example.org",
        "content_kind": "text",
        "message": "We publish tafsirs.",
    }
    payload.update(overrides)
    return payload


class PublisherInquiryEndpointTest(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()  # the endpoint is throttled per IP

    def test_create_publisher_inquiry_where_valid_should_queue_email_with_cleaned_fields(self):
        # Arrange
        payload = _payload(name="  Ahmad  ", email=" ahmad@example.org ")

        # Act
        with patch.object(send_publisher_inquiry_email, send_publisher_inquiry_email.delay.__name__) as delay:
            response = self.client.post(URL, payload, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(response.json()["message"])
        delay.assert_called_once()
        inquiry = delay.call_args.args[0]
        self.assertEqual("Ahmad", inquiry["name"])
        self.assertEqual("ahmad@example.org", inquiry["email"])
        self.assertEqual("Tafsir Center", inquiry["organization"])
        self.assertEqual("text", inquiry["content_kind"])

    def test_create_publisher_inquiry_where_honeypot_filled_should_answer_ok_without_sending(self):
        # Arrange
        payload = _payload(website="https://spam.example")

        # Act
        with patch.object(send_publisher_inquiry_email, send_publisher_inquiry_email.delay.__name__) as delay:
            response = self.client.post(URL, payload, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        delay.assert_not_called()

    def test_create_publisher_inquiry_where_email_invalid_should_return_validation_error(self):
        # Arrange
        payload = _payload(email="not-an-email")

        # Act
        with patch.object(send_publisher_inquiry_email, send_publisher_inquiry_email.delay.__name__) as delay:
            response = self.client.post(URL, payload, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])
        delay.assert_not_called()

    def test_create_publisher_inquiry_where_organization_blank_should_return_validation_error(self):
        # Arrange
        payload = _payload(organization="   ")

        # Act
        with patch.object(send_publisher_inquiry_email, send_publisher_inquiry_email.delay.__name__) as delay:
            response = self.client.post(URL, payload, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])
        delay.assert_not_called()

    def test_create_publisher_inquiry_where_content_kind_unknown_should_return_validation_error(self):
        # Arrange
        payload = _payload(content_kind="videos")

        # Act
        response = self.client.post(URL, payload, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_create_publisher_inquiry_where_rate_exceeded_should_return_429(self):
        # Arrange
        # Act
        with (
            patch.object(inquiry_throttle, "num_requests", 1),
            patch.object(send_publisher_inquiry_email, send_publisher_inquiry_email.delay.__name__),
        ):
            first = self.client.post(URL, _payload(), format="json")
            second = self.client.post(URL, _payload(), format="json")

        # Assert
        self.assertEqual(200, first.status_code, first.content)
        self.assertEqual(429, second.status_code, second.content)
        self.assertEqual("throttled", second.json()["error_name"])


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", PUBLISHER_INQUIRY_EMAIL="team@example.org"
)
class PublisherInquiryEmailTest(BaseTestCase):
    def test_send_email_where_inquiry_given_should_mail_team_with_reply_to_sender(self):
        # Arrange
        inquiry = {**_payload(), "language": "ar"}

        # Act
        PublisherInquiryService().send_email(inquiry)  # type: ignore[arg-type]

        # Assert
        self.assertEqual(1, len(mail.outbox))
        message = mail.outbox[0]
        self.assertEqual(["team@example.org"], message.to)
        self.assertEqual(["ahmad@example.org"], message.reply_to)
        self.assertIn("Tafsir Center", message.subject)
        self.assertIn("We publish tafsirs.", message.body)

    def test_send_publisher_inquiry_email_where_task_runs_should_call_service(self):
        # Arrange
        inquiry = {**_payload(), "language": "en"}

        # Act
        with patch.object(PublisherInquiryService, PublisherInquiryService.send_email.__name__) as send:
            tasks.send_publisher_inquiry_email.apply(args=[inquiry])

        # Assert
        send.assert_called_once_with(inquiry)
