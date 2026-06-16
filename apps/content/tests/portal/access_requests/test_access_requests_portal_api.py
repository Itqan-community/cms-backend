from model_bakery import baker

from apps.content.models import Asset, AssetAccess, AssetAccessRequest, CategoryChoice, LicenseChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


class AccessRequestsPortalApiTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.other_publisher = baker.make(Publisher)

        self.asset = self._make_asset(self.publisher)
        self.other_asset = self._make_asset(self.other_publisher)

        self.member = baker.make(User, is_staff=False)
        PublisherMember.objects.create(
            user=self.member,
            publisher=self.publisher,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )

        self.staff_user = baker.make(User, is_staff=True)
        self.developer = baker.make(User)

    @staticmethod
    def _make_asset(publisher: Publisher) -> Asset:
        return Asset.objects.create(
            name="Test Asset",
            publisher=publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.MUSHAF,
            license=LicenseChoice.CC0,
            file_size="1 MB",
            format="pdf",
            description="desc",
            language="en",
        )

    def _make_request(self, asset=None, developer=None, status=AssetAccessRequest.StatusChoice.PENDING):
        return AssetAccessRequest.objects.create(
            developer_user=developer or self.developer,
            asset=asset or self.asset,
            developer_access_reason="I need this for research",
            intended_use=AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL,
            status=status,
        )

    # --- List ---

    def test_member_lists_only_own_publisher_requests(self):
        own_request = self._make_request()
        self._make_request(asset=self.other_asset)
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.get("/portal/access-requests/")

        self.assertEqual(200, resp.status_code, resp.content)
        ids = {r["id"] for r in resp.json()["results"]}
        self.assertEqual({own_request.id}, ids)

    def test_staff_lists_all_requests(self):
        r1 = self._make_request()
        r2 = self._make_request(asset=self.other_asset)
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.get("/portal/access-requests/")

        self.assertEqual(200, resp.status_code, resp.content)
        ids = {r["id"] for r in resp.json()["results"]}
        self.assertEqual({r1.id, r2.id}, ids)

    def test_list_filter_by_status(self):
        self._make_request(status=AssetAccessRequest.StatusChoice.PENDING)
        self._make_request(developer=baker.make(User), status=AssetAccessRequest.StatusChoice.REJECTED)
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.get("/portal/access-requests/?status=rejected")

        self.assertEqual(200, resp.status_code, resp.content)
        statuses = {r["status"] for r in resp.json()["results"]}
        self.assertEqual({"rejected"}, statuses)

    def test_list_without_permission_returns_403(self):
        self._make_request()
        self.authenticate_user(self.member)

        resp = self.client.get("/portal/access-requests/")

        self.assertEqual(403, resp.status_code)

    def test_list_search_by_developer_email(self):
        self.developer.email = "searchable@example.com"
        self.developer.save()
        self._make_request()
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.get("/portal/access-requests/?search=searchable")

        self.assertEqual(200, resp.status_code, resp.content)
        self.assertEqual(1, len(resp.json()["results"]))

    # --- Detail ---

    def test_detail_returns_decision_fields(self):
        req = self._make_request()
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.get(f"/portal/access-requests/{req.id}/")

        self.assertEqual(200, resp.status_code, resp.content)
        data = resp.json()
        self.assertEqual(req.id, data["id"])
        self.assertIsNone(data["approved_by"])
        self.assertIsNone(data["rejected_by"])

    def test_detail_out_of_scope_returns_404(self):
        req = self._make_request(asset=self.other_asset)
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.get(f"/portal/access-requests/{req.id}/")

        self.assertEqual(404, resp.status_code)

    # --- Accept ---

    def test_accept_pending_request_grants_access(self):
        req = self._make_request()
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)
        self.give_permission(self.member, PermissionChoice.PORTAL_ACCEPT_OR_REJECT_ACCESS_REQUESTS)

        resp = self.client.post(f"/portal/access-requests/{req.id}/accept/")

        self.assertEqual(200, resp.status_code, resp.content)
        req.refresh_from_db()
        self.assertEqual(AssetAccessRequest.StatusChoice.APPROVED, req.status)
        self.assertEqual(self.member.id, req.approved_by_id)
        self.assertTrue(AssetAccess.objects.filter(asset_access_request=req).exists())

    def test_accept_already_decided_request_returns_409(self):
        req = self._make_request(status=AssetAccessRequest.StatusChoice.APPROVED)
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)
        self.give_permission(self.member, PermissionChoice.PORTAL_ACCEPT_OR_REJECT_ACCESS_REQUESTS)

        resp = self.client.post(f"/portal/access-requests/{req.id}/accept/")

        self.assertEqual(409, resp.status_code)
        self.assertEqual("invalid_status", resp.json()["error_name"])

    def test_accept_without_permission_returns_403(self):
        req = self._make_request()
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.post(f"/portal/access-requests/{req.id}/accept/")

        self.assertEqual(403, resp.status_code)

    # --- Reject ---

    def test_reject_pending_request_with_reason(self):
        req = self._make_request()
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)
        self.give_permission(self.member, PermissionChoice.PORTAL_ACCEPT_OR_REJECT_ACCESS_REQUESTS)

        resp = self.client.post(
            f"/portal/access-requests/{req.id}/reject/", {"rejection_reason": "Not eligible"}, format="json"
        )

        self.assertEqual(200, resp.status_code, resp.content)
        req.refresh_from_db()
        self.assertEqual(AssetAccessRequest.StatusChoice.REJECTED, req.status)
        self.assertEqual("Not eligible", req.rejection_reason)
        self.assertEqual(self.member.id, req.rejected_by_id)

    def test_reject_with_empty_reason_returns_422(self):
        req = self._make_request()
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)
        self.give_permission(self.member, PermissionChoice.PORTAL_ACCEPT_OR_REJECT_ACCESS_REQUESTS)

        resp = self.client.post(f"/portal/access-requests/{req.id}/reject/", {"rejection_reason": "  "}, format="json")

        self.assertEqual(422, resp.status_code)
        self.assertEqual("validation_error", resp.json()["error_name"])

    def test_reject_already_decided_request_returns_409(self):
        req = self._make_request(status=AssetAccessRequest.StatusChoice.REJECTED)
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)
        self.give_permission(self.member, PermissionChoice.PORTAL_ACCEPT_OR_REJECT_ACCESS_REQUESTS)

        resp = self.client.post(
            f"/portal/access-requests/{req.id}/reject/", {"rejection_reason": "again"}, format="json"
        )

        self.assertEqual(409, resp.status_code)
