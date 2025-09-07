"""
Asset API Views implementing OpenAPI specification
Updated for ERD-aligned models with access control integration
"""

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Asset
from .models import AssetAccess
from .models import AssetAccessRequest
from .models import UsageEvent
from .serializers import AccessRequestResponseSerializer
from .serializers import AssetDetailSerializer
from .serializers import AssetSummarySerializer


class AssetListView(APIView):
    """
    API Endpoint: GET /assets
    List all assets with filtering and access status
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        summary="List assets",
        description="Get paginated list of assets with optional filtering",
        parameters=[
            OpenApiParameter(
                name="category",
                description="Filter by category",
                required=False,
                type=str,
                enum=["mushaf", "tafsir", "recitation"],
            ),
            OpenApiParameter(
                name="license_code",
                description="Filter by license code",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="publisher_id",
                description="Filter by publisher (organization) ID",
                required=False,
                type=int,
            ),
            OpenApiParameter(
                name="search",
                description="Search in asset titles and descriptions",
                required=False,
                type=str,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="List of assets",
                response={
                    "type": "object",
                    "properties": {
                        "assets": {
                            "type": "array",
                            "items": AssetSummarySerializer,
                        },
                    },
                },
            ),
        },
    )
    def get(self, request):
        """Get list of assets with optional filtering"""
        # Start with all active assets
        queryset = (
            Asset.objects.select_related(
                "publishing_organization",
                "license",
            )
            .prefetch_related(
                "assetversion_set",
            )
            .order_by("-created_at")
        )

        # Apply filters
        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category)

        license_code = request.query_params.get("license_code")
        if license_code:
            queryset = queryset.filter(license__code=license_code)

        publisher_id = request.query_params.get("publisher_id")
        if publisher_id:
            queryset = queryset.filter(publishing_organization_id=publisher_id)

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search) | Q(long_description__icontains=search),
            )

        # Serialize assets
        assets_data = []
        for asset in queryset[:50]:  # Limit to 50 for now
            # Track view event for authenticated users
            if request.user.is_authenticated:
                UsageEvent.track_asset_view(
                    user=request.user,
                    asset=asset,
                    ip_address=self._get_client_ip(request),
                    user_agent=request.headers.get("user-agent", ""),
                )
                # Increment view count
                asset.increment_view_count()

            asset_data = AssetSummarySerializer.from_asset_model(asset, request)
            assets_data.append(asset_data)

        return Response(
            {
                "assets": assets_data,
            },
        )

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")


class AssetDetailView(APIView):
    """
    API Endpoint: GET /assets/{asset_id}
    Get detailed asset information with access status
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        summary="Get asset details",
        description="Get complete asset information including access status, technical details, and related assets",
        responses={
            200: AssetDetailSerializer,
            404: OpenApiResponse(description="Asset not found"),
        },
    )
    def get(self, request, asset_id):
        """Get detailed asset information"""
        try:
            asset = (
                Asset.objects.select_related(
                    "publishing_organization",
                    "license",
                )
                .prefetch_related(
                    "assetversion_set__resource_version",
                )
                .get(id=asset_id)
            )
        except Asset.DoesNotExist:
            return Response(
                {"error": {"code": "ASSET_NOT_FOUND", "message": "Asset not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Track view event for authenticated users
        if request.user.is_authenticated:
            UsageEvent.track_asset_view(
                user=request.user,
                asset=asset,
                ip_address=self._get_client_ip(request),
                user_agent=request.headers.get("user-agent", ""),
            )
            # Increment view count
            asset.increment_view_count()

        # Serialize asset details
        asset_data = AssetDetailSerializer.from_asset_model(asset, request)

        return Response(asset_data)

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")


class AssetRequestAccessView(APIView):
    """
    API Endpoint: POST /assets/{asset_id}/request-access
    Request access to an asset (V1: auto-approval)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Request asset access",
        description="Request access to an asset. In V1, requests are automatically approved.",
        request={
            "type": "object",
            "properties": {
                "purpose": {
                    "type": "string",
                    "description": "Reason for requesting access",
                },
                "intended_use": {
                    "type": "string",
                    "enum": ["commercial", "non-commercial"],
                    "description": "Intended use of the asset",
                },
            },
            "required": ["purpose", "intended_use"],
        },
        responses={
            200: AccessRequestResponseSerializer,
            400: OpenApiResponse(description="Invalid request"),
            404: OpenApiResponse(description="Asset not found"),
        },
    )
    def post(self, request, asset_id):
        """Request access to an asset"""
        try:
            asset = Asset.objects.get(id=asset_id)
        except Asset.DoesNotExist:
            return Response(
                {"error": {"code": "ASSET_NOT_FOUND", "message": "Asset not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get request data
        purpose = request.data.get("purpose")
        intended_use = request.data.get("intended_use")

        if not purpose or not intended_use:
            return Response(
                {
                    "error": {
                        "code": "INVALID_REQUEST",
                        "message": "Purpose and intended_use are required",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if intended_use not in ["commercial", "non-commercial"]:
            return Response(
                {
                    "error": {
                        "code": "INVALID_INTENDED_USE",
                        "message": "intended_use must be commercial or non-commercial",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create access request with auto-approval
        try:
            access_request, access_grant = AssetAccessRequest.request_access(
                user=request.user,
                asset=asset,
                purpose=purpose,
                intended_use=intended_use,
                auto_approve=True,  # V1: Auto-approval
            )

            # Create response
            response_data = AccessRequestResponseSerializer.from_request_and_access(
                access_request,
                access_grant,
            )

            return Response(response_data)

        except Exception as e:
            return Response(
                {"error": {"code": "ACCESS_REQUEST_FAILED", "message": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AssetDownloadView(APIView):
    """
    API Endpoint: GET /assets/{asset_id}/download
    Download an asset (requires access)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Download asset",
        description="Download an asset file. Requires user to have access.",
        responses={
            302: OpenApiResponse(description="Redirect to download URL"),
            403: OpenApiResponse(description="Access denied"),
            404: OpenApiResponse(description="Asset not found"),
        },
    )
    def get(self, request, asset_id):
        """Download an asset"""
        try:
            asset = Asset.objects.get(id=asset_id)
        except Asset.DoesNotExist:
            return Response(
                {"error": {"code": "ASSET_NOT_FOUND", "message": "Asset not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if user has access
        user_access = AssetAccess.get_user_access(request.user, asset)
        if not user_access or not user_access.is_active:
            return Response(
                {
                    "error": {
                        "code": "ACCESS_DENIED",
                        "message": "You do not have access to this asset",
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get download URL
        download_url = user_access.get_download_url()
        if not download_url:
            return Response(
                {
                    "error": {
                        "code": "DOWNLOAD_UNAVAILABLE",
                        "message": "Download URL not available",
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Track download event
        UsageEvent.track_asset_download(
            user=request.user,
            asset=asset,
            ip_address=self._get_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )

        # Increment download count
        asset.increment_download_count()

        # Create usage event from access
        user_access.create_usage_event(
            usage_kind="file_download",
            ip_address=self._get_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )

        # Return download URL
        return Response(
            {
                "download_url": download_url,
                "expires_at": user_access.expires_at.isoformat() if user_access.expires_at else None,
            },
        )

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")


# ============================================================================
# CONVENIENCE FUNCTION VIEWS
# ============================================================================


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
@extend_schema(
    summary="Get asset access status",
    description="Check if user has access to a specific asset",
    responses={
        200: {
            "type": "object",
            "properties": {
                "has_access": {"type": "boolean"},
                "requires_approval": {"type": "boolean"},
                "download_url": {"type": "string", "nullable": True},
            },
        },
    },
)
def asset_access_status(request, asset_id):
    """Get asset access status for the authenticated user"""
    try:
        asset = Asset.objects.get(id=asset_id)
    except Asset.DoesNotExist:
        return Response(
            {"error": {"code": "ASSET_NOT_FOUND", "message": "Asset not found"}},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not request.user.is_authenticated:
        return Response(
            {
                "has_access": False,
                "requires_approval": False,
                "download_url": None,
            },
        )

    # Check access
    user_access = AssetAccess.get_user_access(request.user, asset)

    return Response(
        {
            "has_access": user_access is not None and user_access.is_active,
            "requires_approval": False,  # V1: Auto-approval
            "download_url": user_access.get_download_url() if user_access else None,
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
@extend_schema(
    summary="Get related assets",
    description="Get assets related to the specified asset",
    responses={
        200: {
            "type": "object",
            "properties": {
                "related_assets": {
                    "type": "array",
                    "items": AssetSummarySerializer,
                },
            },
        },
    },
)
def asset_related(request, asset_id):
    """Get related assets"""
    try:
        asset = Asset.objects.get(id=asset_id)
    except Asset.DoesNotExist:
        return Response(
            {"error": {"code": "ASSET_NOT_FOUND", "message": "Asset not found"}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get related assets
    related_assets = asset.get_related_assets(limit=10)
    related_data = [AssetSummarySerializer.from_asset_model(related, request) for related in related_assets]

    return Response(
        {
            "related_assets": related_data,
        },
    )
