"""End-to-end checks that a public API consumer's self-reported client headers go through
the client-version middleware: valid values pass silently, malformed ones raise a warning
header without failing the request."""

from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.middlewares.client_version import WARNING_HEADER
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher


class ClientVersionIntegrationTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher A")
        self.reciter = baker.make("content.Reciter", name="Reciter X", is_active=True)
        self.riwayah = baker.make("content.Riwayah", name="Riwayah Y", is_active=True)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=True,
            reciter=self.reciter,
            riwayah=self.riwayah,
        )

    def test_recitations_list_where_client_headers_valid_should_not_warn(self):
        headers = {"X-Client-Name": "quran-companion", "X-Client-Version": "2.4.1"}

        response = self.client.get("/recitations/", headers=headers)

        self.assertEqual(200, response.status_code, response.content)
        self.assertNotIn(WARNING_HEADER, response)

    def test_recitations_list_where_no_client_headers_sent_should_not_warn(self):
        response = self.client.get("/recitations/")

        self.assertEqual(200, response.status_code, response.content)
        self.assertNotIn(WARNING_HEADER, response)

    def test_recitations_list_where_client_version_is_malformed_should_succeed_and_warn(self):
        headers = {"X-Client-Name": "quran-companion", "X-Client-Version": "2.4.1 (nightly build)"}

        response = self.client.get("/recitations/", headers=headers)

        self.assertEqual(200, response.status_code, response.content)
        self.assertIn("X-Client-Version", response[WARNING_HEADER])

    def test_error_response_where_client_headers_sent_should_still_carry_the_warning(self):
        headers = {"X-Client-Version": "not a version"}

        response = self.client.get("/recitations/999999/", headers=headers)

        self.assertEqual(404, response.status_code, response.content)
        self.assertIn("X-Client-Version", response[WARNING_HEADER])
