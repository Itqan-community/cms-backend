from model_bakery import baker

from apps.content.models import Asset, AssetAccessRequest, CategoryChoice, LicenseChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


class AccessRequestsSettingsPortalApiTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, auto_accept_access_requests=True)
        self.member = baker.make(User, is_staff=False)
        PublisherMember.objects.create(
            user=self.member,
            publisher=self.publisher,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.staff_user = baker.make(User, is_staff=True)
        self.non_member = baker.make(User, is_staff=False)

    # --- GET ---

    def test_get_settings_happy_path(self):
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.get(f"/portal/publishers/{self.publisher.id}/access-requests-settings/")

        self.assertEqual(200, resp.status_code, resp.content)
        data = resp.json()
        self.assertEqual(self.publisher.id, data["publisher_id"])
        self.assertTrue(data["auto_accept_access_requests"])

    def test_get_settings_non_member_returns_403(self):
        self.authenticate_user(self.non_member)
        self.give_permission(self.non_member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.get(f"/portal/publishers/{self.publisher.id}/access-requests-settings/")

        self.assertEqual(403, resp.status_code)

    def test_get_settings_unknown_publisher_returns_404(self):
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.get("/portal/publishers/999999/access-requests-settings/")

        self.assertEqual(404, resp.status_code)

    def test_get_settings_staff_can_access_any_publisher(self):
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.get(f"/portal/publishers/{self.publisher.id}/access-requests-settings/")

        self.assertEqual(200, resp.status_code, resp.content)

    # --- PUT ---

    def test_put_settings_happy_path(self):
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)
        self.give_permission(self.member, PermissionChoice.PORTAL_MANAGE_ACCESS_REQUESTS_SETTINGS)

        resp = self.client.put(
            f"/portal/publishers/{self.publisher.id}/access-requests-settings/",
            {"auto_accept_access_requests": False},
            format="json",
        )

        self.assertEqual(200, resp.status_code, resp.content)
        self.assertFalse(resp.json()["auto_accept_access_requests"])
        self.publisher.refresh_from_db()
        self.assertFalse(self.publisher.auto_accept_access_requests)

    def test_put_settings_without_manage_permission_returns_403(self):
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)

        resp = self.client.put(
            f"/portal/publishers/{self.publisher.id}/access-requests-settings/",
            {"auto_accept_access_requests": False},
            format="json",
        )

        self.assertEqual(403, resp.status_code)

    def test_put_settings_non_member_publisher_returns_403(self):
        self.authenticate_user(self.non_member)
        self.give_permission(self.non_member, PermissionChoice.PORTAL_MANAGE_ACCESS_REQUESTS_SETTINGS)

        resp = self.client.put(
            f"/portal/publishers/{self.publisher.id}/access-requests-settings/",
            {"auto_accept_access_requests": False},
            format="json",
        )

        self.assertEqual(403, resp.status_code)

    def test_put_settings_unknown_publisher_returns_404(self):
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.PORTAL_MANAGE_ACCESS_REQUESTS_SETTINGS)

        resp = self.client.put(
            "/portal/publishers/999999/access-requests-settings/",
            {"auto_accept_access_requests": False},
            format="json",
        )

        self.assertEqual(404, resp.status_code)

    def test_turning_flag_off_does_not_affect_existing_pending_requests(self):
        asset = Asset.objects.create(
            name="Test Asset",
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.MUSHAF,
            license=LicenseChoice.CC0,
            file_size="1 MB",
            format="pdf",
            description="desc",
            language="en",
        )
        developer = baker.make(User)
        AssetAccessRequest.objects.create(
            developer_user=developer,
            asset=asset,
            developer_access_reason="reason",
            intended_use=AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL,
            status=AssetAccessRequest.StatusChoice.PENDING,
        )
        self.authenticate_user(self.member)
        self.give_permission(self.member, PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)
        self.give_permission(self.member, PermissionChoice.PORTAL_MANAGE_ACCESS_REQUESTS_SETTINGS)
        pending_count_before = AssetAccessRequest.objects.filter(status="pending").count()

        resp = self.client.put(
            f"/portal/publishers/{self.publisher.id}/access-requests-settings/",
            {"auto_accept_access_requests": False},
            format="json",
        )

        self.assertEqual(200, resp.status_code, resp.content)
        self.assertEqual(pending_count_before, AssetAccessRequest.objects.filter(status="pending").count())
