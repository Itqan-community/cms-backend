from __future__ import annotations

from enum import Enum
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from apps.content.models import Asset, AssetAccess, AssetAccessRequest
from apps.content.repositories.access_request import AssetAccessRequestRepository
from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.repositories.publisher import PublisherRepository
from apps.publishers.services.membership import get_user_member_publisher_ids

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.users.models import User

logger = logging.getLogger(__name__)


class AssetAccessRequestService:
    def __init__(self, repo: AssetAccessRequestRepository, publisher_repo: PublisherRepository | None = None) -> None:
        self.repo = repo
        self.publisher_repo = publisher_repo or PublisherRepository()

    # --- scoping ---
    def list_requests(self, user: User) -> QuerySet[AssetAccessRequest]:
        q_filter = None if user.is_staff else Q(asset__publisher_id__in=get_user_member_publisher_ids(user))
        return self.repo.list_qs(q_filter=q_filter)

    def get_for_user(self, user: User, request_id: int) -> AssetAccessRequest:
        req = self.repo.get_by_id(request_id)
        if req is None or (not user.is_staff and req.asset.publisher_id not in get_user_member_publisher_ids(user)):
            raise ItqanError("not_found", _("Not found."), status_code=404)
        return req

    @staticmethod
    def _guard_pending(req: AssetAccessRequest) -> None:
        if req.status != AssetAccessRequest.StatusChoice.PENDING:
            raise ItqanError(
                "invalid_status",
                _("Cannot act on request with status '{status}'.").format(status=req.status),
                status_code=409,
            )

    # --- publisher actions ---
    def accept(self, user: User, request_id: int) -> AssetAccessRequest:
        req = self.get_for_user(user, request_id)
        self._guard_pending(req)
        self.repo.mark_approved(req, approved_by=user)
        self._enqueue_outcome_email(req.id)
        logger.info(f"Asset access request accepted [request_id={req.pk}, approved_by={user.pk}]")
        return req

    def reject(self, user: User, request_id: int, reason: str) -> AssetAccessRequest:
        if not (reason or "").strip():
            raise ItqanError("validation_error", _("Rejection reason is required."), status_code=422)
        req = self.get_for_user(user, request_id)
        self._guard_pending(req)
        self.repo.mark_rejected(req, rejected_by=user, reason=reason.strip())
        self._enqueue_outcome_email(req.id)
        logger.info(f"Asset access request rejected [request_id={req.pk}, rejected_by={user.pk}]")
        return req

    @staticmethod
    def _enqueue_outcome_email(request_id: int) -> None:
        from apps.content.tasks import send_access_request_outcome_email

        transaction.on_commit(lambda: send_access_request_outcome_email.delay(request_id))

    @staticmethod
    def _enqueue_new_request_email(request_id: int) -> None:
        from apps.content.tasks import send_access_request_new_request_email

        transaction.on_commit(lambda: send_access_request_new_request_email.delay(request_id))

    # --- developer flow ---
    def request_access(
        self, *, user: User, asset: Asset, purpose: str, intended_use: str
    ) -> tuple[AssetAccessRequest, AssetAccess | None]:
        auto_approve = asset.publisher.auto_accept_access_requests
        existing_request = self.repo.get_existing(developer_user=user, asset=asset)

        if existing_request:
            if existing_request.status == AssetAccessRequest.StatusChoice.APPROVED:
                logger.warning(
                    f"Access request already approved — returning existing grant "
                    f"[user_id={user.pk}, asset_id={asset.pk}, request_id={existing_request.pk}]"
                )
                access = getattr(existing_request, "access_grant", None)
                return existing_request, access
            elif existing_request.status == AssetAccessRequest.StatusChoice.PENDING:
                if auto_approve:
                    access = self.repo.mark_approved(existing_request, approved_by=None)
                    self._enqueue_outcome_email(existing_request.id)
                    return existing_request, access
                return existing_request, None

        request = self.repo.create_request(
            developer_user=user,
            asset=asset,
            developer_access_reason=purpose,
            intended_use=intended_use,
        )
        logger.info(f"Asset access requested [request_id={request.pk}, user_id={user.pk}, asset_id={asset.pk}]")
        self._enqueue_new_request_email(request.id)

        access = None
        if auto_approve:
            access = self.repo.mark_approved(request, approved_by=None)
            self._enqueue_outcome_email(request.id)

        return request, access

    # --- settings ---
    def _resolve_publisher_for_user(self, user: User, publisher_id: int):
        from django.shortcuts import get_object_or_404

        from apps.publishers.models import Publisher
        from apps.publishers.services.membership import enforce_publisher_membership

        publisher = get_object_or_404(Publisher, id=publisher_id)
        enforce_publisher_membership(user, publisher_id)
        return publisher

    def get_settings(self, user: User, publisher_id: int) -> dict:
        publisher = self._resolve_publisher_for_user(user, publisher_id)
        return {"publisher_id": publisher.id, "auto_accept_access_requests": publisher.auto_accept_access_requests}

    def set_auto_accept(self, user: User, publisher_id: int, value: bool) -> dict:
        publisher = self._resolve_publisher_for_user(user, publisher_id)
        self.publisher_repo.set_auto_accept(publisher, value)
        return {"publisher_id": publisher.id, "auto_accept_access_requests": value}


def guard_restrict_for_tenant(asset: Asset) -> None:
    """Block restricting an asset to its tenant surface while public consumers rely on it.

    Setting restricted_for_tenant=True removes the asset from public surfaces (the CMS
    assets library and the public developers API). If developers already hold a granted
    grant or have an open request, hiding it would break their integrations, so refuse
    and ask the publisher to coordinate with Itqan team.
    """
    has_active_consumers = AssetAccessRequest.objects.filter(
        asset=asset,
        status__in=[
            AssetAccessRequest.StatusChoice.PENDING,
            AssetAccessRequest.StatusChoice.APPROVED,
        ],
    ).exists()
    if not has_active_consumers:
        return

    logger.warning(f"Blocked restricting asset to tenant — open or granted access requests exist [asset_id={asset.pk}]")
    raise ItqanError(
        "restricted_for_tenant_conflict",
        _(
            "This asset has open or granted access requests from public consumers and "
            "cannot be restricted to your tenant. Please contact Itqan team."
        ),
        status_code=409,
    )


def enforce_asset_access_on_public_api(user: User | None, asset: Asset) -> None:
    """Gate consumption of an asset's content behind an API key + approved access.

    Open-access assets are free to consume by anyone. For assets the publisher keeps
    behind the access-request cycle, the consumer must (1) be authenticated — i.e. pass
    a valid API key — and (2) hold an active access grant (an approved access request).
    A missing/invalid key yields 401; an authenticated consumer without an approved
    grant (not requested, pending, or rejected) yields 403.
    """

    if not settings.ENFORCE_ASSET_ACCESS_ON_PUBLIC_API:
        return

    if asset.is_open_access:
        return

    if not (user and user.is_authenticated):
        raise ItqanError(
            "authentication_required",
            _("An API key is required to access this asset's content."),
            status_code=401,
        )

    if not user_has_access(user, asset):
        raise ItqanError(
            "access_denied",
            _("You don't have an approved access request for this asset."),
            status_code=403,
        )


def user_has_access(user: User, asset: Asset) -> bool:
    if asset.is_open_access:
        return True

    try:
        access = AssetAccess.objects.get(user=user, asset=asset)
        return access.is_active
    except AssetAccess.DoesNotExist:
        return False


class AssetAccessStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def get_access_status(user: User | None, asset: Asset) -> AssetAccessStatus | None:
    if asset.is_open_access:
        return None

    if not (user and user.is_authenticated):
        return None

    if user_has_access(user, asset):
        return AssetAccessStatus.APPROVED

    req = AssetAccessRequestRepository().get_existing(developer_user=user, asset=asset)
    if req is None:
        return AssetAccessStatus.NOT_REQUESTED

    return AssetAccessStatus(req.status)
