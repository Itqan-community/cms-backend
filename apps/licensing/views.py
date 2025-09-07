"""
API ViewSets for Licensing models
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.api.permissions import AccessRequestPermission
from apps.api.permissions import IsAdminUser
from apps.api.permissions import LicensePermission

from .models import AccessRequest
from .models import LegacyLicense
from .serializers import AccessRequestApprovalSerializer
from .serializers import AccessRequestListSerializer
from .serializers import AccessRequestSerializer
from .serializers import AccessRequestWorkflowSerializer
from .serializers import BulkAccessRequestActionSerializer
from .serializers import LicenseSerializer


class LicenseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for License management
    """

    queryset = LegacyLicense.objects.all()
    serializer_class = LicenseSerializer
    permission_classes = [LicensePermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["license_type", "resource", "requires_approval", "is_active"]
    search_fields = ["terms"]
    ordering_fields = ["license_type", "effective_from", "expires_at", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = LegacyLicense.objects.all()

        if self.request.user.is_admin() or self.request.user.is_reviewer():
            # Admin and Reviewers can see all licenses
            return queryset
        if self.request.user.is_publisher():
            # Publishers can see licenses for their resources
            return queryset.filter(resource__publisher=self.request.user)
        if self.request.user.is_developer():
            # Developers can see licenses for published resources
            return queryset.filter(resource__published_at__isnull=False)

        return queryset.none()


class AccessRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for AccessRequest management
    """

    queryset = AccessRequest.objects.all()
    permission_classes = [AccessRequestPermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "status",
        "priority",
        "requester",
        "distribution",
        "notification_sent",
        "is_active",
    ]
    search_fields = ["justification", "admin_notes"]
    ordering_fields = ["status", "requested_at", "reviewed_at"]
    ordering = ["-requested_at"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "list":
            return AccessRequestListSerializer
        if self.action in ["approve", "reject"]:
            return AccessRequestApprovalSerializer
        if self.action in ["workflow_action", "start_review", "revoke"]:
            return AccessRequestWorkflowSerializer
        if self.action == "bulk_action":
            return BulkAccessRequestActionSerializer
        return AccessRequestSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        queryset = AccessRequest.objects.all()

        if self.request.user.is_admin():
            # Admin can see all requests
            return queryset
        if self.request.user.is_developer():
            # Developers can see their own requests
            return queryset.filter(requester=self.request.user)
        if self.request.user.is_publisher():
            # Publishers can see requests for their resources
            return queryset.filter(distribution__resource__publisher=self.request.user)
        if self.request.user.is_reviewer():
            # Reviewers can see all requests
            return queryset

        return queryset.none()

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Approve an access request"""
        access_request = self.get_object()
        serializer = self.get_serializer(access_request, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Access request approved successfully",
                "access_request": AccessRequestSerializer(access_request).data,
            },
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Reject an access request"""
        access_request = self.get_object()
        serializer = self.get_serializer(access_request, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Access request rejected successfully",
                "access_request": AccessRequestSerializer(access_request).data,
            },
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def workflow_action(self, request, pk=None):
        """Execute workflow action on access request"""
        access_request = self.get_object()
        serializer = self.get_serializer(access_request, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        action = request.data.get("action")
        return Response(
            {
                "message": f"Access request {action} executed successfully",
                "access_request": AccessRequestSerializer(access_request).data,
            },
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def start_review(self, request, pk=None):
        """Start review process for access request"""
        access_request = self.get_object()
        data = request.data.copy()
        data["action"] = "start_review"

        serializer = self.get_serializer(access_request, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Access request review started successfully",
                "access_request": AccessRequestSerializer(access_request).data,
            },
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def revoke(self, request, pk=None):
        """Revoke approved access request"""
        access_request = self.get_object()
        data = request.data.copy()
        data["action"] = "revoke"

        serializer = self.get_serializer(access_request, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Access request revoked successfully",
                "access_request": AccessRequestSerializer(access_request).data,
            },
        )

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def bulk_action(self, request):
        """Execute bulk actions on access requests"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request_ids = serializer.validated_data["request_ids"]
        action = serializer.validated_data["action"]
        admin_notes = serializer.validated_data.get("admin_notes", "")
        admin_user = request.user

        # Get access requests that can be acted upon
        access_requests = AccessRequest.objects.filter(
            id__in=request_ids,
            is_active=True,
        )

        successful_count = 0
        failed_count = 0
        errors = []

        for access_request in access_requests:
            try:
                if action == "start_review" and access_request.can_be_reviewed():
                    access_request.start_review(
                        admin_user=admin_user,
                        admin_notes=admin_notes,
                    )
                    successful_count += 1
                elif action == "approve" and access_request.can_be_reviewed():
                    expires_at = serializer.validated_data.get("expires_at")
                    access_request.approve(
                        admin_user=admin_user,
                        expires_at=expires_at,
                        admin_notes=admin_notes,
                    )
                    successful_count += 1
                elif action == "reject" and access_request.can_be_reviewed():
                    rejection_reason = serializer.validated_data.get(
                        "rejection_reason",
                        "",
                    )
                    access_request.reject(
                        admin_user=admin_user,
                        rejection_reason=rejection_reason,
                        admin_notes=admin_notes,
                    )
                    successful_count += 1
                else:
                    failed_count += 1
                    errors.append(
                        f"Request {access_request.id}: Cannot {action} in current state",
                    )
            except Exception as e:
                failed_count += 1
                errors.append(f"Request {access_request.id}: {e!s}")

        return Response(
            {
                "message": f"Bulk {action} completed",
                "successful_count": successful_count,
                "failed_count": failed_count,
                "errors": errors,
            },
        )

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        """Get dashboard data for access requests"""
        queryset = self.get_queryset()

        # Count by status
        status_counts = {}
        for choice in AccessRequest.STATUS_CHOICES:
            status = choice[0]
            status_counts[status] = queryset.filter(status=status).count()

        # Count by priority
        priority_counts = {}
        for choice in AccessRequest.PRIORITY_CHOICES:
            priority = choice[0]
            priority_counts[priority] = queryset.filter(priority=priority).count()

        # Recent requests (last 7 days)
        from datetime import timedelta

        from django.utils import timezone

        week_ago = timezone.now() - timedelta(days=7)
        recent_requests = queryset.filter(requested_at__gte=week_ago).count()

        # Pending notifications
        pending_notifications = queryset.filter(
            notification_sent=False,
            status__in=["approved", "rejected", "revoked", "expired"],
        ).count()

        return Response(
            {
                "status_counts": status_counts,
                "priority_counts": priority_counts,
                "recent_requests": recent_requests,
                "pending_notifications": pending_notifications,
                "total_requests": queryset.count(),
            },
        )
