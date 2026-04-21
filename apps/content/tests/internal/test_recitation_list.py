from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, Qiraah, Riwayah, StatusChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationsListTest(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)
        self.publisher = baker.make(Publisher, name="Publisher One")

        self.qiraah_asim = baker.make(Qiraah, name="Asim", name_ar="عاصم", is_active=True)
        self.qiraah_nafi = baker.make(Qiraah, name="Nafi", name_ar="نافع", is_active=True)

        self.riwayah_hafs = baker.make(
            Riwayah, qiraah=self.qiraah_asim, name="Hafs", name_ar="حفص عن عاصم", is_active=True
        )
        self.riwayah_warsh = baker.make(
            Riwayah, qiraah=self.qiraah_nafi, name="Warsh", name_ar="ورش عن نافع", is_active=True
        )

        self.reciter1 = baker.make("content.Reciter", name="Mishary Alafasy", name_ar="مشاري العفاسي")
        self.reciter2 = baker.make("content.Reciter", name="Saad Al-Ghamidi", name_ar="سعد الغامدي")

        self.asset1 = baker.make(
            Asset,
            name="Alafasy Hafs Recitation",
            description="Beautiful recitation by Alafasy",
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter1,
            riwayah=self.riwayah_hafs,
            qiraah=self.qiraah_asim,
        )
        self.asset2 = baker.make(
            Asset,
            name="Ghamidi Warsh Recitation",
            description="Calm recitation by Ghamidi",
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=self.reciter2,
            riwayah=self.riwayah_warsh,
            qiraah=self.qiraah_nafi,
        )

        # Draft asset - should NOT be returned
        baker.make(
            Asset,
            name="Draft Recitation",
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.DRAFT,
            reciter=self.reciter1,
            riwayah=self.riwayah_hafs,
            qiraah=self.qiraah_asim,
        )

    # ── Baseline ──────────────────────────────────────────────

    def test_list_recitations_where_no_filters_should_return_only_ready_recitations(self):
        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/recitations/")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(2, len(items))
        returned_ids = {item["id"] for item in items}
        self.assertIn(self.asset1.id, returned_ids)
        self.assertIn(self.asset2.id, returned_ids)

    def test_list_recitations_where_no_filters_should_return_all(self):
        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/recitations/")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(2, len(items))

    # ── Search by English name ────────────────────────────────

    def test_list_recitations_where_search_by_english_reciter_name_should_return_matching_recitation(self):
        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/recitations/?search=Alafasy")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

    # ── Search by Arabic name ─────────────────────────────────

    def test_list_recitations_where_search_by_arabic_reciter_name_should_return_matching_recitation(self):
        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/recitations/?search=مشاري")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

    def test_list_recitations_where_search_by_riwayah_name_arabic_should_return_matching_recitation(self):
        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/recitations/?search=حفص")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

    def test_list_recitations_where_search_by_qiraah_name_arabic_should_return_matching_recitation(self):
        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/recitations/?search=عاصم")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

    # ── Filter by Riwayah ─────────────────────────────────────

    def test_list_recitations_where_filter_by_riwayah_should_return_matching_recitation(self):
        self.authenticate_user(self.user)
        response = self.client.get(f"/cms-api/recitations/?riwayah_id={self.riwayah_hafs.id}")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

    # ── Filter by Qiraah ──────────────────────────────────────

    def test_list_recitations_where_filter_by_qiraah_should_return_matching_recitation(self):
        self.authenticate_user(self.user)
        response = self.client.get(f"/cms-api/recitations/?qiraah_id={self.qiraah_nafi.id}")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset2.id, items[0]["id"])

    # ── Combined filters ──────────────────────────────────────

    def test_list_recitations_where_filter_by_riwayah_and_reciter_should_return_matching_recitation(self):
        self.authenticate_user(self.user)
        response = self.client.get(
            f"/cms-api/recitations/?riwayah_id={self.riwayah_hafs.id}&reciter_id={self.reciter1.id}"
        )
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

    def test_list_recitations_where_filter_by_riwayah_and_reciter_should_return_no_results(self):
        self.authenticate_user(self.user)
        response = self.client.get(
            f"/cms-api/recitations/?riwayah_id={self.riwayah_hafs.id}&reciter_id={self.reciter2.id}"
        )
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(0, len(items))

    # ── Pagination ────────────────────────────────────────────

    def test_list_recitations_where_pagination_requested_should_return_paginated_response_structure(self):
        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/recitations/?page=1&page_size=1")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIn("results", body)
        self.assertIn("count", body)
        self.assertEqual(2, body["count"])
        self.assertEqual(1, len(body["results"]))

    # ── Response shape ────────────────────────────────────────

    def test_list_recitations_where_fetching_recitations_should_return_response_with_expected_fields(self):
        self.authenticate_user(self.user)
        response = self.client.get("/cms-api/recitations/")
        self.assertEqual(200, response.status_code, response.content)
        item = response.json()["results"][0]
        for field in ("id", "name", "description", "reciter", "riwayah", "qiraah"):
            self.assertIn(field, item, f"Missing field: {field}")
        self.assertIsInstance(item["reciter"], dict)
        self.assertSetEqual(set(item["reciter"].keys()), {"id", "name"})

    # ── Query count ────────────────────────────────────────────

    def test_list_recitations_should_use_constant_number_of_queries(self):
        baker.make(
            Asset,
            _quantity=20,
            category=Resource.CategoryChoice.RECITATION,
            resource=self.ready_resource,
            reciter=self.reciter1,
            riwayah=self.riwayah_hafs,
            qiraah=self.qiraah_asim,
        )
        recitations_count = Asset.objects.filter(category="recitation").count()

        self.authenticate_user(self.user)
        from django.db import connection

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/cms-api/recitations/")

        self.assertEqual(200, response.status_code, response.content)
        self.assertLess(
            len(ctx),
            recitations_count,
            f"Expected < {recitations_count} queries, got {len(ctx)}: {[q['sql'] for q in ctx]}",
        )
