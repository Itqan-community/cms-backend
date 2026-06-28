from unittest.mock import patch

from model_bakery import baker

from apps.content.models import Asset, AssetAccessRequest, CategoryChoice, LicenseChoice, StatusChoice
from apps.content.repositories.access_request import AssetAccessRequestRepository
from apps.content.services.asset_access import AssetAccessRequestService, guard_restrict_for_tenant, user_has_access
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


def _make_asset(publisher: Publisher, *, auto_accept: bool | None = None) -> Asset:
    if auto_accept is not None:
        publisher.auto_accept_access_requests = auto_accept
        publisher.save(update_fields=["auto_accept_access_requests"])
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


class AssetAccessRequestServiceTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = AssetAccessRequestService(AssetAccessRequestRepository())
        self.publisher = baker.make(Publisher)
        self.other_publisher = baker.make(Publisher)
        self.developer = baker.make(User)
        self.member = baker.make(User, is_staff=False)
        PublisherMember.objects.create(
            user=self.member,
            publisher=self.publisher,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.staff = baker.make(User, is_staff=True)

    def _make_request(self, asset):
        return AssetAccessRequest.objects.create(
            developer_user=self.developer,
            asset=asset,
            developer_access_reason="reason",
            intended_use=AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL,
        )

    # --- get_for_user scope ---

    def test_get_for_user_out_of_scope_raises_not_found(self):
        asset = _make_asset(self.other_publisher)
        req = self._make_request(asset)

        with self.assertRaises(ItqanError) as ctx:
            self.service.get_for_user(self.member, req.id)
        self.assertEqual("not_found", ctx.exception.error_name)
        self.assertEqual(404, ctx.exception.status_code)

    def test_get_for_user_staff_can_access_any(self):
        asset = _make_asset(self.other_publisher)
        req = self._make_request(asset)

        result = self.service.get_for_user(self.staff, req.id)
        self.assertEqual(req.id, result.id)

    # --- accept/reject status guard ---

    def test_accept_non_pending_raises_invalid_status(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        req = self._make_request(asset)
        self.service.accept(self.member, req.id)

        with self.assertRaises(ItqanError) as ctx:
            self.service.accept(self.member, req.id)
        self.assertEqual("invalid_status", ctx.exception.error_name)
        self.assertEqual(409, ctx.exception.status_code)

    def test_reject_empty_reason_raises_validation_error(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        req = self._make_request(asset)

        with self.assertRaises(ItqanError) as ctx:
            self.service.reject(self.member, req.id, "   ")
        self.assertEqual("validation_error", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)

    def test_reject_non_pending_raises_invalid_status(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        req = self._make_request(asset)
        self.service.reject(self.member, req.id, "no")

        with self.assertRaises(ItqanError) as ctx:
            self.service.reject(self.member, req.id, "no again")
        self.assertEqual("invalid_status", ctx.exception.error_name)

    # --- request_access auto vs pending ---

    def test_request_access_auto_accept_grants_immediately(self):
        asset = _make_asset(self.publisher, auto_accept=True)

        request, access = self.service.request_access(
            user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
        )

        self.assertEqual(AssetAccessRequest.StatusChoice.APPROVED, request.status)
        self.assertIsNone(request.approved_by)
        self.assertIsNotNone(access)

    def test_request_access_no_auto_accept_stays_pending(self):
        asset = _make_asset(self.publisher, auto_accept=False)

        request, access = self.service.request_access(
            user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
        )

        self.assertEqual(AssetAccessRequest.StatusChoice.PENDING, request.status)
        self.assertIsNone(access)


class UserHasAccessPublicAssetTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.user = baker.make(User)

    def test_public_asset_grants_access_without_access_record(self):
        asset = _make_asset(self.publisher)
        asset.is_open_access = True
        asset.save(update_fields=["is_open_access"])

        # No AssetAccess record exists for this user/asset
        self.assertTrue(user_has_access(self.user, asset))


class GuardRestrictForTenantTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.developer = baker.make(User)

    def _make_request(self, asset, status):
        return AssetAccessRequest.objects.create(
            developer_user=self.developer,
            asset=asset,
            status=status,
            developer_access_reason="reason",
            intended_use=AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL,
        )

    def test_no_requests_passes(self):
        asset = _make_asset(self.publisher)
        guard_restrict_for_tenant(asset)  # does not raise

    def test_pending_request_blocks(self):
        asset = _make_asset(self.publisher)
        self._make_request(asset, AssetAccessRequest.StatusChoice.PENDING)

        with self.assertRaises(ItqanError) as ctx:
            guard_restrict_for_tenant(asset)
        self.assertEqual("restricted_for_tenant_conflict", ctx.exception.error_name)
        self.assertEqual(409, ctx.exception.status_code)
        self.assertIn("Itqan team", str(ctx.exception.message))

    def test_approved_request_blocks(self):
        asset = _make_asset(self.publisher)
        self._make_request(asset, AssetAccessRequest.StatusChoice.APPROVED)

        with self.assertRaises(ItqanError) as ctx:
            guard_restrict_for_tenant(asset)
        self.assertEqual("restricted_for_tenant_conflict", ctx.exception.error_name)

    def test_rejected_request_passes(self):
        asset = _make_asset(self.publisher)
        self._make_request(asset, AssetAccessRequest.StatusChoice.REJECTED)
        guard_restrict_for_tenant(asset)  # does not raise


_OUTCOME_TASK = "apps.content.tasks.send_access_request_outcome_email"
_NEW_REQUEST_TASK = "apps.content.tasks.send_access_request_new_request_email"


class AssetAccessRequestServiceNotificationsTests(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.patch_on_commit()

    def setUp(self):
        super().setUp()
        self.service = AssetAccessRequestService(AssetAccessRequestRepository())
        self.publisher = baker.make(Publisher)
        self.developer = baker.make(User)
        self.member = baker.make(User, is_staff=False)
        PublisherMember.objects.create(
            user=self.member,
            publisher=self.publisher,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def _make_request(self, asset):
        return AssetAccessRequest.objects.create(
            developer_user=self.developer,
            asset=asset,
            developer_access_reason="reason",
            intended_use=AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL,
        )

    def test_accept_enqueues_outcome_email(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        req = self._make_request(asset)

        with patch(_OUTCOME_TASK) as mock_task:
            self.service.accept(self.member, req.id)

        mock_task.delay.assert_called_once_with(req.id)

    def test_reject_enqueues_outcome_email(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        req = self._make_request(asset)

        with patch(_OUTCOME_TASK) as mock_task:
            self.service.reject(self.member, req.id, "no")

        mock_task.delay.assert_called_once_with(req.id)

    def test_request_access_pending_enqueues_new_request_email_only(self):
        asset = _make_asset(self.publisher, auto_accept=False)

        with patch(_NEW_REQUEST_TASK) as mock_new, patch(_OUTCOME_TASK) as mock_outcome:
            request, _access = self.service.request_access(
                user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
            )

        mock_new.delay.assert_called_once_with(request.id)
        mock_outcome.delay.assert_not_called()

    def test_request_access_auto_accept_enqueues_both_emails(self):
        asset = _make_asset(self.publisher, auto_accept=True)

        with patch(_NEW_REQUEST_TASK) as mock_new, patch(_OUTCOME_TASK) as mock_outcome:
            request, _access = self.service.request_access(
                user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
            )

        mock_new.delay.assert_called_once_with(request.id)
        mock_outcome.delay.assert_called_once_with(request.id)

    def test_request_access_existing_pending_does_not_double_send_new_request_email(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        existing = self._make_request(asset)

        with patch(_NEW_REQUEST_TASK) as mock_new, patch(_OUTCOME_TASK) as mock_outcome:
            request, _access = self.service.request_access(
                user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
            )

        self.assertEqual(existing.id, request.id)
        mock_new.delay.assert_not_called()
        mock_outcome.delay.assert_not_called()

    def test_request_access_existing_pending_auto_accept_enqueues_outcome_email(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        existing = self._make_request(asset)
        self.publisher.auto_accept_access_requests = True
        self.publisher.save(update_fields=["auto_accept_access_requests"])

        with patch(_NEW_REQUEST_TASK) as mock_new, patch(_OUTCOME_TASK) as mock_outcome:
            request, _access = self.service.request_access(
                user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
            )

        self.assertEqual(existing.id, request.id)
        mock_new.delay.assert_not_called()
        mock_outcome.delay.assert_called_once_with(request.id)
