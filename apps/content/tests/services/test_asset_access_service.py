from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from model_bakery import baker

from apps.content.models import Asset, AssetAccess, AssetAccessRequest, CategoryChoice, LicenseChoice, StatusChoice
from apps.content.repositories.access_request import AssetAccessRequestRepository
from apps.content.services.asset_access import (
    AssetAccessRequestService,
    get_access_status,
    guard_channel_changes,
    user_has_access,
)
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.tests.group_helpers import admin_group
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
            group=admin_group(),
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

    def test_accept_where_grant_creation_fails_should_roll_back_approval(self) -> None:
        # Arrange
        asset = _make_asset(self.publisher, auto_accept=False)
        request = self._make_request(asset)

        # Act
        with patch.object(
            AssetAccess.objects,
            AssetAccess.objects.update_or_create.__name__,
            side_effect=RuntimeError("grant failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "grant failure"):
                self.service.accept(self.member, request.pk)

        # Assert
        request.refresh_from_db()
        self.assertEqual(AssetAccessRequest.StatusChoice.PENDING, request.status)
        self.assertIsNone(request.approved_at)
        self.assertIsNone(request.approved_by)
        self.assertFalse(AssetAccess.objects.filter(asset=asset).exists())

    def test_request_access_where_grant_creation_fails_should_roll_back_new_request(self) -> None:
        # Arrange
        asset = _make_asset(self.publisher, auto_accept=True)

        # Act
        with patch.object(
            AssetAccess.objects,
            AssetAccess.objects.update_or_create.__name__,
            side_effect=RuntimeError("grant failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "grant failure"):
                self.service.request_access(
                    user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
                )

        # Assert
        self.assertFalse(AssetAccessRequest.objects.filter(asset=asset).exists())
        self.assertFalse(AssetAccess.objects.filter(asset=asset).exists())

    def test_accept_where_existing_grant_is_stale_should_refresh_it_for_new_request(self) -> None:
        # Arrange
        asset = _make_asset(self.publisher, auto_accept=False)
        original = self.service.accept(self.member, self._make_request(asset).pk)
        grant = original.access_grant
        grant.expires_at = timezone.now() - timedelta(days=1)
        grant.save(update_fields=["expires_at"])
        asset.license = LicenseChoice.CC_BY
        asset.save(update_fields=["license"])
        resubmitted = self._make_request(asset)

        # Act
        self.service.accept(self.member, resubmitted.pk)

        # Assert
        grant.refresh_from_db()
        self.assertEqual(resubmitted.pk, grant.asset_access_request_id)
        self.assertEqual(LicenseChoice.CC_BY, grant.effective_license)
        self.assertIsNone(grant.expires_at)
        self.assertTrue(user_has_access(self.developer, asset))
        self.assertEqual(1, AssetAccess.objects.filter(asset=asset).count())

    def test_accept_where_legacy_duplicate_exists_should_reuse_grant_on_resubmission(self) -> None:
        # Arrange
        asset = _make_asset(self.publisher, auto_accept=False)
        original = self.service.accept(self.member, self._make_request(asset).pk)
        original_grant = original.access_grant
        duplicate = self._make_request(asset)

        # Act
        self.service.accept(self.member, duplicate.pk)
        request, grant = self.service.request_access(
            user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
        )

        # Assert
        self.assertEqual(duplicate.pk, request.pk)
        self.assertEqual(original_grant.pk, grant.pk)
        self.assertEqual(duplicate.pk, grant.asset_access_request_id)
        self.assertEqual(1, AssetAccess.objects.filter(asset=asset).count())

    def test_request_access_where_rejected_should_allow_a_new_request(self) -> None:
        # Arrange
        asset = _make_asset(self.publisher, auto_accept=False)
        rejected = self._make_request(asset)
        self.service.reject(self.member, rejected.pk, "Try again with more detail")

        # Act
        request, grant = self.service.request_access(
            user=self.developer, asset=asset, purpose="new purpose", intended_use="non-commercial"
        )

        # Assert
        self.assertNotEqual(rejected.pk, request.pk)
        self.assertEqual(AssetAccessRequest.StatusChoice.PENDING, request.status)
        self.assertIsNone(grant)
        rejected.refresh_from_db()
        self.assertEqual(AssetAccessRequest.StatusChoice.REJECTED, rejected.status)

    def test_get_existing_returns_newest_request(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        older = self._make_request(asset)
        newer = self._make_request(asset)
        # Force a deterministic created_at ordering regardless of insert timing.
        AssetAccessRequest.objects.filter(pk=older.pk).update(created_at="2020-01-01T00:00:00Z")
        AssetAccessRequest.objects.filter(pk=newer.pk).update(created_at="2024-01-01T00:00:00Z")

        result = self.service.repo.get_existing(developer_user=self.developer, asset=asset)
        self.assertEqual(newer.id, result.id)


class GetAccessStatusTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.user = baker.make(User)

    def _asset(self):
        asset = _make_asset(self.publisher)
        asset.is_open_access = False
        asset.save(update_fields=["is_open_access"])
        return asset

    def _make_request(self, asset, status):
        return AssetAccessRequest.objects.create(
            developer_user=self.user,
            asset=asset,
            status=status,
            developer_access_reason="reason",
            intended_use=AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL,
        )

    def test_open_access_returns_none(self):
        asset = self._asset()
        asset.is_open_access = True
        asset.save(update_fields=["is_open_access"])

        self.assertIsNone(get_access_status(self.user, asset))

    def test_anonymous_returns_none(self):
        self.assertIsNone(get_access_status(user=None, asset=self._asset()))

    def test_no_request_returns_not_requested(self):
        self.assertEqual("not_requested", get_access_status(self.user, self._asset()))

    def test_pending_returns_pending(self):
        asset = self._asset()
        self._make_request(asset, AssetAccessRequest.StatusChoice.PENDING)
        self.assertEqual("pending", get_access_status(self.user, asset))

    def test_rejected_returns_rejected(self):
        asset = self._asset()
        self._make_request(asset, AssetAccessRequest.StatusChoice.REJECTED)
        self.assertEqual("rejected", get_access_status(self.user, asset))

    def test_active_grant_returns_approved(self):
        asset = self._asset()
        req = self._make_request(asset, AssetAccessRequest.StatusChoice.APPROVED)
        AssetAccess.objects.create(
            asset_access_request=req,
            user=self.user,
            asset=asset,
            effective_license=asset.license,
            expires_at=None,
        )
        self.assertEqual("approved", get_access_status(self.user, asset))


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


class GuardChannelChangesTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.developer = baker.make(User)

    def _make_request(self, asset, status, developer=None):
        return AssetAccessRequest.objects.create(
            developer_user=developer or self.developer,
            asset=asset,
            status=status,
            developer_access_reason="reason",
            intended_use=AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL,
        )

    def test_guard_channel_changes_where_no_requests_should_pass(self):
        # Arrange
        asset = _make_asset(self.publisher)
        fields = {"in_cli": False}
        # Act / Assert
        guard_channel_changes(asset, fields)  # does not raise

    def test_guard_channel_changes_where_pending_request_should_raise_with_counts(self):
        # Arrange
        asset = _make_asset(self.publisher)
        self._make_request(asset, AssetAccessRequest.StatusChoice.PENDING)
        # Act
        with self.assertRaises(ItqanError) as ctx:
            guard_channel_changes(asset, {"in_cli": False, "in_gallery": False, "in_tenants": True})
        # Assert
        self.assertEqual("channel_has_active_consumers", ctx.exception.error_name)
        self.assertEqual(409, ctx.exception.status_code)
        self.assertEqual(
            {"approved_count": 0, "pending_count": 1, "channels": ["in_gallery", "in_cli"]},
            ctx.exception.extra,
        )

    def test_guard_channel_changes_where_approved_and_pending_requests_should_count_both(self):
        # Arrange
        asset = _make_asset(self.publisher)
        self._make_request(asset, AssetAccessRequest.StatusChoice.APPROVED)
        self._make_request(asset, AssetAccessRequest.StatusChoice.PENDING, developer=baker.make(User))
        # Act
        with self.assertRaises(ItqanError) as ctx:
            guard_channel_changes(asset, {"in_public_api": False})
        # Assert
        self.assertEqual(1, ctx.exception.extra["approved_count"])
        self.assertEqual(1, ctx.exception.extra["pending_count"])
        self.assertEqual(["in_public_api"], ctx.exception.extra["channels"])

    def test_guard_channel_changes_where_confirmed_should_allow_and_strip_flag(self):
        # Arrange
        asset = _make_asset(self.publisher)
        self._make_request(asset, AssetAccessRequest.StatusChoice.APPROVED)
        fields = {"in_cli": False, "confirm_channel_change": True}
        # Act
        guard_channel_changes(asset, fields)
        # Assert
        self.assertNotIn("confirm_channel_change", fields)
        self.assertEqual({"in_cli": False}, fields)

    def test_guard_channel_changes_where_turning_flag_on_should_not_need_confirm(self):
        # Arrange
        asset = _make_asset(self.publisher)
        Asset.objects.filter(pk=asset.pk).update(in_cli=False)
        asset.refresh_from_db()
        self._make_request(asset, AssetAccessRequest.StatusChoice.APPROVED)
        # Act / Assert
        guard_channel_changes(asset, {"in_cli": True})  # does not raise

    def test_guard_channel_changes_where_flag_already_off_should_not_raise(self):
        # Arrange
        asset = _make_asset(self.publisher)
        Asset.objects.filter(pk=asset.pk).update(in_cli=False)
        asset.refresh_from_db()
        self._make_request(asset, AssetAccessRequest.StatusChoice.APPROVED)
        # Act / Assert
        guard_channel_changes(asset, {"in_cli": False})  # unchanged, does not raise

    def test_guard_channel_changes_where_request_rejected_should_pass(self):
        # Arrange
        asset = _make_asset(self.publisher)
        self._make_request(asset, AssetAccessRequest.StatusChoice.REJECTED)
        # Act / Assert
        guard_channel_changes(asset, {"in_gallery": False})  # does not raise

    def test_guard_channel_changes_where_null_flag_sent_should_drop_it_from_fields(self):
        # Arrange
        asset = _make_asset(self.publisher)
        fields = {"in_gallery": None}
        # Act
        guard_channel_changes(asset, fields)
        # Assert
        self.assertEqual({}, fields)


_OUTCOME_TASK = "apps.content.tasks.send_access_request_outcome_email"


class AssetAccessRequestServiceNotificationsTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = AssetAccessRequestService(AssetAccessRequestRepository())
        self.publisher = baker.make(Publisher)
        self.developer = baker.make(User)
        self.member = baker.make(User, is_staff=False)
        PublisherMember.objects.create(
            user=self.member,
            publisher=self.publisher,
            group=admin_group(),
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

        with patch(_OUTCOME_TASK) as mock_task, self.captureOnCommitCallbacks(execute=True):
            self.service.accept(self.member, req.id)

        mock_task.delay.assert_called_once_with(req.id)

    def test_reject_enqueues_outcome_email(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        req = self._make_request(asset)

        with patch(_OUTCOME_TASK) as mock_task, self.captureOnCommitCallbacks(execute=True):
            self.service.reject(self.member, req.id, "no")

        mock_task.delay.assert_called_once_with(req.id)

    def test_request_access_where_new_request_should_not_send_immediate_publisher_email(self):
        asset = _make_asset(self.publisher, auto_accept=False)

        with patch(_OUTCOME_TASK) as mock_outcome:
            request, _access = self.service.request_access(
                user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
            )

        mock_outcome.delay.assert_not_called()

    def test_request_access_auto_accept_enqueues_outcome_email(self):
        asset = _make_asset(self.publisher, auto_accept=True)

        with patch(_OUTCOME_TASK) as mock_outcome, self.captureOnCommitCallbacks(execute=True):
            request, _access = self.service.request_access(
                user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
            )

        mock_outcome.delay.assert_called_once_with(request.id)

    def test_request_access_existing_pending_does_not_send_outcome_email(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        existing = self._make_request(asset)

        with patch(_OUTCOME_TASK) as mock_outcome, self.captureOnCommitCallbacks(execute=True):
            request, _access = self.service.request_access(
                user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
            )

        self.assertEqual(existing.id, request.id)
        mock_outcome.delay.assert_not_called()

    def test_request_access_existing_pending_auto_accept_enqueues_outcome_email(self):
        asset = _make_asset(self.publisher, auto_accept=False)
        existing = self._make_request(asset)
        self.publisher.auto_accept_access_requests = True
        self.publisher.save(update_fields=["auto_accept_access_requests"])

        with patch(_OUTCOME_TASK) as mock_outcome, self.captureOnCommitCallbacks(execute=True):
            request, _access = self.service.request_access(
                user=self.developer, asset=asset, purpose="purpose", intended_use="non-commercial"
            )

        self.assertEqual(existing.id, request.id)
        mock_outcome.delay.assert_called_once_with(request.id)
