"""
Publisher API Views implementing OpenAPI specification
Maps PublishingOrganization model to Publisher API endpoints
"""

from django.db.models import Count
from django.db.models import Sum
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Asset
from .models import PublishingOrganization
from .models import Resource
from .serializers import AssetSummarySerializer
from .serializers import PublisherSerializer


class PublisherDetailView(APIView):
    """
    API Endpoint: GET /publishers/{publisher_id}
    Get detailed publisher information using PublishingOrganization model
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        summary="Get publisher details",
        description="Get complete publisher information with statistics and published assets",
        responses={
            200: PublisherSerializer,
            404: OpenApiResponse(description="Publisher not found"),
        },
    )
    def get(self, request, publisher_id):
        """Get detailed publisher information"""
        try:
            # Get organization with optimized queries
            organization = (
                PublishingOrganization.objects.select_related()
                .annotate(
                    resources_count=Count("resources"),
                    assets_count=Count("resources__asset", distinct=True),
                    total_downloads=Sum("resources__asset__download_count"),
                )
                .get(id=publisher_id)
            )
        except PublishingOrganization.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "PUBLISHER_NOT_FOUND",
                        "message": "Publisher not found",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Serialize publisher data
        publisher_data = PublisherSerializer.from_publishing_organization(
            organization,
            request,
        )

        return Response(publisher_data)


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
@extend_schema(
    summary="Get publisher assets",
    description="Get paginated list of assets published by the organization",
    parameters=[
        OpenApiParameter(
            name="category",
            description="Filter by category",
            required=False,
            type=str,
            enum=["mushaf", "tafsir", "recitation"],
        ),
        OpenApiParameter(
            name="limit",
            description="Number of assets to return (max 50)",
            required=False,
            type=int,
        ),
    ],
    responses={
        200: {
            "type": "object",
            "properties": {
                "publisher": PublisherSerializer,
                "assets": {
                    "type": "array",
                    "items": AssetSummarySerializer,
                },
                "total_count": {"type": "integer"},
            },
        },
        404: OpenApiResponse(description="Publisher not found"),
    },
)
def publisher_assets(request, publisher_id):
    """Get assets published by the organization"""
    try:
        organization = PublishingOrganization.objects.get(id=publisher_id)
    except PublishingOrganization.DoesNotExist:
        return Response(
            {
                "error": {
                    "code": "PUBLISHER_NOT_FOUND",
                    "message": "Publisher not found",
                },
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get assets query
    assets_query = (
        Asset.objects.filter(
            publishing_organization=organization,
        )
        .select_related("license")
        .order_by("-created_at")
    )

    # Apply category filter if provided
    category = request.query_params.get("category")
    if category:
        assets_query = assets_query.filter(category=category)

    # Apply limit
    limit = min(int(request.query_params.get("limit", 20)), 50)
    assets = assets_query[:limit]
    total_count = assets_query.count()

    # Serialize data
    publisher_data = PublisherSerializer.from_publishing_organization(
        organization,
        request,
    )
    assets_data = []

    for asset in assets:
        asset_data = AssetSummarySerializer.from_asset_model(asset, request)
        assets_data.append(asset_data)

    return Response(
        {
            "publisher": publisher_data,
            "assets": assets_data,
            "total_count": total_count,
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
@extend_schema(
    summary="Get publisher statistics",
    description="Get detailed statistics for a publisher organization",
    responses={
        200: {
            "type": "object",
            "properties": {
                "publisher_id": {"type": "integer"},
                "name": {"type": "string"},
                "stats": {
                    "type": "object",
                    "properties": {
                        "resources_count": {"type": "integer"},
                        "assets_count": {"type": "integer"},
                        "total_downloads": {"type": "integer"},
                        "total_views": {"type": "integer"},
                        "categories": {
                            "type": "object",
                            "properties": {
                                "mushaf": {"type": "integer"},
                                "tafsir": {"type": "integer"},
                                "recitation": {"type": "integer"},
                            },
                        },
                        "joined_at": {"type": "string", "format": "date-time"},
                    },
                },
            },
        },
        404: OpenApiResponse(description="Publisher not found"),
    },
)
def publisher_statistics(request, publisher_id):
    """Get comprehensive statistics for a publisher"""
    try:
        organization = PublishingOrganization.objects.get(id=publisher_id)
    except PublishingOrganization.DoesNotExist:
        return Response(
            {
                "error": {
                    "code": "PUBLISHER_NOT_FOUND",
                    "message": "Publisher not found",
                },
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Calculate comprehensive statistics
    assets = Asset.objects.filter(publishing_organization=organization)
    resources = Resource.objects.filter(publishing_organization=organization)

    # Basic counts
    resources_count = resources.count()
    assets_count = assets.count()
    total_downloads = sum(asset.download_count for asset in assets)
    total_views = sum(asset.view_count for asset in assets)

    # Category breakdown
    categories = {
        "mushaf": assets.filter(category="mushaf").count(),
        "tafsir": assets.filter(category="tafsir").count(),
        "recitation": assets.filter(category="recitation").count(),
    }

    return Response(
        {
            "publisher_id": organization.id,
            "name": organization.name,
            "stats": {
                "resources_count": resources_count,
                "assets_count": assets_count,
                "total_downloads": total_downloads,
                "total_views": total_views,
                "categories": categories,
                "joined_at": organization.created_at.isoformat() if organization.created_at else None,
            },
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
@extend_schema(
    summary="List all publishers",
    description="Get paginated list of all publishing organizations",
    parameters=[
        OpenApiParameter(
            name="verified_only",
            description="Return only verified publishers",
            required=False,
            type=bool,
        ),
        OpenApiParameter(
            name="has_assets",
            description="Return only publishers with published assets",
            required=False,
            type=bool,
        ),
        OpenApiParameter(
            name="limit",
            description="Number of publishers to return (max 50)",
            required=False,
            type=int,
        ),
    ],
    responses={
        200: {
            "type": "object",
            "properties": {
                "publishers": {
                    "type": "array",
                    "items": PublisherSerializer,
                },
                "total_count": {"type": "integer"},
            },
        },
    },
)
def publisher_list(request):
    """Get list of all publishers"""
    # Start with all organizations
    publishers_query = PublishingOrganization.objects.annotate(
        resources_count=Count("resources"),
        assets_count=Count("resources__asset", distinct=True),
        total_downloads=Sum("resources__asset__download_count"),
    ).order_by("name")

    # Apply filters
    verified_only = request.query_params.get("verified_only", "").lower() == "true"
    if verified_only:
        publishers_query = publishers_query.filter(verified=True)

    has_assets = request.query_params.get("has_assets", "").lower() == "true"
    if has_assets:
        publishers_query = publishers_query.filter(assets_count__gt=0)

    # Apply limit
    limit = min(int(request.query_params.get("limit", 20)), 50)
    publishers = publishers_query[:limit]
    total_count = publishers_query.count()

    # Serialize data
    publishers_data = []
    for publisher in publishers:
        publisher_data = PublisherSerializer.from_publishing_organization(
            publisher,
            request,
        )
        publishers_data.append(publisher_data)

    return Response(
        {
            "publishers": publishers_data,
            "total_count": total_count,
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
@extend_schema(
    summary="Get publisher members",
    description="Get list of organization members and their roles",
    responses={
        200: {
            "type": "object",
            "properties": {
                "publisher_id": {"type": "integer"},
                "name": {"type": "string"},
                "members": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "integer"},
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "role": {"type": "string"},
                            "joined_at": {"type": "string", "format": "date-time"},
                        },
                    },
                },
            },
        },
        404: OpenApiResponse(description="Publisher not found"),
    },
)
def publisher_members(request, publisher_id):
    """Get organization members and their roles"""
    try:
        organization = PublishingOrganization.objects.get(id=publisher_id)
    except PublishingOrganization.DoesNotExist:
        return Response(
            {
                "error": {
                    "code": "PUBLISHER_NOT_FOUND",
                    "message": "Publisher not found",
                },
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get members through the membership relationship
    memberships = organization.memberships.select_related("user").order_by(
        "-created_at",
    )

    members_data = [
        {
            "user_id": membership.user.id,
            "name": membership.user.get_full_name(),
            "email": membership.user.email,
            "role": membership.role,
            "joined_at": membership.created_at.isoformat() if membership.created_at else None,
        }
        for membership in memberships
    ]

    return Response(
        {
            "publisher_id": organization.id,
            "name": organization.name,
            "members": members_data,
        },
    )
