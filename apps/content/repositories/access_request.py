from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import Q
from django.utils import timezone

from apps.content.models import Asset, AssetAccess, AssetAccessRequest

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.users.models import User


class AssetAccessRequestRepository:
    def list_qs(
        self, *, filters: dict[str, Any] | None = None, q_filter: Q | None = None
    ) -> QuerySet[AssetAccessRequest]:
        qs = AssetAccessRequest.objects.select_related(
            "developer_user", "asset", "asset__publisher", "approved_by", "rejected_by"
        ).order_by("-created_at")
        if filters:
            qs = qs.filter(**filters)
        if q_filter:
            qs = qs.filter(q_filter)
        return qs

    def get_by_id(self, request_id: int, *, for_update: bool = False) -> AssetAccessRequest | None:
        qs = self.list_qs()
        if for_update:
            # Nullable reviewer joins cannot be locked by PostgreSQL.
            qs = qs.select_for_update(of=("self",))
        return qs.filter(id=request_id).first()

    def get_asset_for_update(self, asset_id: int) -> Asset:
        # A stable parent row serializes submissions even before a request exists.
        # NO KEY UPDATE permits FK inserts by a reviewer holding a request lock,
        # avoiding an asset/request lock inversion during concurrent approval.
        return Asset.objects.select_related("publisher").select_for_update(of=("self",), no_key=True).get(pk=asset_id)

    def list_pending_for_publisher_notification(self) -> QuerySet[AssetAccessRequest]:
        return (
            self.list_qs()
            .filter(status=AssetAccessRequest.StatusChoice.PENDING)
            .order_by("asset__publisher_id", "-created_at")
        )

    def get_existing(
        self, *, developer_user: User, asset: Asset, for_update: bool = False
    ) -> AssetAccessRequest | None:
        qs = AssetAccessRequest.objects.filter(developer_user=developer_user, asset=asset).order_by(
            "-created_at", "-id"
        )
        if for_update:
            qs = qs.select_for_update(of=("self",))
        return qs.first()

    def get_access(self, *, developer_user: User, asset: Asset) -> AssetAccess | None:
        return AssetAccess.objects.filter(user=developer_user, asset=asset).first()

    def create_request(
        self, *, developer_user: User, asset: Asset, developer_access_reason: str, intended_use: str
    ) -> AssetAccessRequest:
        return AssetAccessRequest.objects.create(
            developer_user=developer_user,
            asset=asset,
            developer_access_reason=developer_access_reason,
            intended_use=intended_use,
        )

    def mark_approved(self, request: AssetAccessRequest, *, approved_by: User | None) -> AssetAccess:
        request.status = AssetAccessRequest.StatusChoice.APPROVED
        request.approved_at = timezone.now()
        request.approved_by = approved_by
        request.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])
        access, _created = AssetAccess.objects.get_or_create(
            user=request.developer_user,
            asset=request.asset,
            defaults={
                "asset_access_request": request,
                "effective_license": request.asset.license,
                "expires_at": None,
            },
        )
        return access

    def mark_rejected(self, request: AssetAccessRequest, *, rejected_by: User, reason: str) -> AssetAccessRequest:
        request.status = AssetAccessRequest.StatusChoice.REJECTED
        request.rejected_at = timezone.now()
        request.rejected_by = rejected_by
        request.rejection_reason = reason
        request.save(update_fields=["status", "rejected_at", "rejected_by", "rejection_reason", "updated_at"])
        return request
