from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import Asset, CategoryChoice, Reciter, StatusChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.adapters import User


class RecitersListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)

        self.active_reciter = baker.make(Reciter, is_active=True, name="Active Reciter")

        riwayah = baker.make("content.Riwayah", name="Test Riwayah")
        self.valid_asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            reciter=self.active_reciter,
            publisher=self.publisher,
            status=StatusChoice.READY,
            riwayah=riwayah,
        )

        # Inactive reciter should NOT appear
        self.inactive_reciter = baker.make(Reciter, is_active=False, name="Inactive Reciter")
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            reciter=self.inactive_reciter,
            publisher=self.publisher,
            status=StatusChoice.READY,
            riwayah=riwayah,
        )

        # Asset with non-RECITATION category should NOT be counted
        self.other_category_asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
        )

        # Asset with DRAFT status should NOT be counted
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            reciter=self.active_reciter,
            publisher=self.publisher,
            status=StatusChoice.DRAFT,
            riwayah=riwayah,
        )

        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )

        self.riwayah = baker.make("content.Riwayah")

    def _make_reciter_with_recitation(self, asset_status=StatusChoice.READY, **kwargs):
        """Create a reciter with a recitation asset of the given status."""
        reciter = baker.make(Reciter, **kwargs)
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            reciter=reciter,
            publisher=self.publisher,
            status=asset_status,
            riwayah=self.riwayah,
        )
        return reciter

    def test_list_reciters_should_return_only_active_reciters_with_ready_recitations(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/reciters/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        reciter_names = {item["name"] for item in items}

        self.assertIn("Active Reciter", reciter_names)
        self.assertNotIn("Inactive Reciter", reciter_names)

        # There should be exactly one reciter (the active one with at least one valid asset)
        self.assertEqual(1, len(items))

        reciter_item = items[0]
        self.assertEqual(self.active_reciter.id, reciter_item["id"])
        # Only the valid RECITATION asset with READY status should be counted
        self.assertEqual(1, reciter_item["recitations_count"])

    def test_list_reciters_ordering_by_name_en(self):
        # Arrange – another active reciter so we can test ordering
        other_reciter = baker.make(Reciter, is_active=True, name="A Reciter")
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            reciter=other_reciter,
            publisher=self.publisher,
            status=StatusChoice.READY,
            riwayah=baker.make("content.Riwayah", name="Test Riwayah1"),
        )
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/reciters/?ordering=name_en")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)  # ascending by name

    def test_reciters_where_no_ordering_parameter_provided_api_should_fallback_to_ordering_by_name_ar(self):
        for name_ar in ["ياسر الدوسري", "أحمد العجمي", "سعد الغامدي"]:
            self._make_reciter_with_recitation(name_ar=name_ar, is_active=True)

        # Use Accept-Language: ar so that `name` in the response maps to name_ar
        self.authenticate_user(self.user, language="ar")
        response = self.client.get("/cms-api/reciters/")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)

    def test_reciters_listing_where_search_paramter_is_provided_api_should_return_matched_reciters(self):
        self._make_reciter_with_recitation(name="Mishary Rashid", name_ar="مشاري راشد العفاسي", is_active=True)
        self._make_reciter_with_recitation(name="Saad Al-Ghamidi", name_ar="سعد الغامدي", is_active=True)
        self.authenticate_user(self.user, language="ar")

        response = self.client.get("/cms-api/reciters/", data={"search": "مشاري"})

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertEqual("مشاري راشد العفاسي", body["results"][0]["name"])
