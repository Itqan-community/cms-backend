from model_bakery import baker

from apps.content.models import Asset, Reciter, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class ReciterSortedListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="admin@example.com", is_active=True, is_staff=True)
        self.publisher = baker.make(Publisher)
        self.recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.draft_recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        self.riwayah = baker.make("content.Riwayah")

    def _make_reciter_with_recitation(self, resource_status=Resource.StatusChoice.READY, **kwargs):
        """Create a reciter with a recitation asset linked to a resource of the given status."""
        resource = (
            self.recitation_resource
            if resource_status == Resource.StatusChoice.READY
            else self.draft_recitation_resource
        )
        reciter = baker.make(Reciter, **kwargs)
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            reciter=reciter,
            resource=resource,
            riwayah=self.riwayah,
        )
        return reciter

    def test_list_reciters_returns_only_active_reciters_with_ready_recitations(self):
        self._make_reciter_with_recitation(Resource.StatusChoice.READY, name_ar="قارئ نشط", is_active=True)             # Active + READY → appears
        self._make_reciter_with_recitation(Resource.StatusChoice.READY, name_ar="قارئ غير نشط ١", is_active=False)      # Inactive + READY → does NOT appear
        self._make_reciter_with_recitation(Resource.StatusChoice.DRAFT, name_ar="قارئ غير نشط ٢", is_active=False)      # Inactive + DRAFT → does NOT appear
        self._make_reciter_with_recitation(Resource.StatusChoice.DRAFT, name_ar="قارئ نشط ٢", is_active=True)           # ACTIVE + DRAFT → does NOT appear
        baker.make(Reciter, name_ar="قارئ بدون تسجيل", is_active=True)                                                  # Active + no asset → does NOT appear

        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/reciters/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIn("results", body)
        self.assertEqual(1, body["count"])

    def test_list_reciters_returns_detailed_fields(self):
        self._make_reciter_with_recitation(
            name="Test Reciter",
            slug="test-reciter",
            is_active=True,
        )
        self.authenticate_user(self.user)

        response = self.client.get("/cms-api/reciters/")

        self.assertEqual(200, response.status_code, response.content)
        item = response.json()["results"][0]
        self.assertIn("name", item)
        self.assertIn("slug", item)
        self.assertIn("bio", item)
        self.assertIn("is_active", item)
        self.assertIn("image_url", item)
        self.assertIn("created_at", item)
        self.assertIn("updated_at", item)

    def test_list_reciters_default_ordering_by_name_ar(self):
        for name_ar in ["ياسر الدوسري", "أحمد العجمي", "سعد الغامدي"]:
            self._make_reciter_with_recitation(name_ar=name_ar, is_active=True)

        # Use Accept-Language: ar so that `name` in the response maps to name_ar
        self.authenticate_user(self.user, language="ar")
        response = self.client.get("/cms-api/reciters/")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)


    def test_list_reciters_search_by_name_ar(self):
        self._make_reciter_with_recitation(
            name="Mishary Rashid", name_ar="مشاري راشد العفاسي", is_active=True
        )
        self._make_reciter_with_recitation(
            name="Saad Al-Ghamidi", name_ar="سعد الغامدي", is_active=True
        )
        self.authenticate_user(self.user, language="ar")

        response = self.client.get("/cms-api/reciters/", data={"search": "مشاري"})

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertEqual("مشاري راشد العفاسي", body["results"][0]["name"])
