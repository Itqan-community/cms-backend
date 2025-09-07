"""
License API Views implementing OpenAPI specification
Complete license management with terms and usage statistics
"""

from django.db.models import Count
from django.db.models import Q
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
from .models import License
from .models import Resource
from .serializers import LicenseDetailSerializer
from .serializers import LicenseSummarySerializer


class LicenseListView(APIView):
    """
    API Endpoint: GET /licenses
    List all available licenses with usage statistics
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        summary="List licenses",
        description="Get list of all available licenses with usage statistics",
        parameters=[
            OpenApiParameter(
                name="type",
                description="Filter by license type",
                required=False,
                type=str,
                enum=["open", "restricted", "commercial"],
            ),
            OpenApiParameter(
                name="default_only",
                description="Return only default licenses",
                required=False,
                type=bool,
            ),
            OpenApiParameter(
                name="min_usage",
                description="Filter by minimum usage count",
                required=False,
                type=int,
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="List of licenses",
                response={
                    "type": "object",
                    "properties": {
                        "licenses": {
                            "type": "array",
                            "items": LicenseSummarySerializer,
                        },
                    },
                },
            ),
        },
    )
    def get(self, request):
        """Get list of licenses with filtering options"""
        # Start with all active licenses
        queryset = License.objects.annotate(
            usage_count=Count("assets") + Count("default_for_resources") + Count("effective_for_accesses"),
        ).order_by("-is_default", "-usage_count", "name")

        # Apply filters
        license_type = request.query_params.get("type")
        if license_type:
            # This could be expanded based on license categorization
            if license_type == "open":
                queryset = queryset.filter(
                    Q(code__startswith="cc") | Q(code__in=["mit", "apache-2.0"]),
                )
            elif license_type == "restricted":
                queryset = queryset.filter(
                    ~Q(code__startswith="cc") & ~Q(code__in=["mit", "apache-2.0"]),
                )

        default_only = request.query_params.get("default_only", "").lower() == "true"
        if default_only:
            queryset = queryset.filter(is_default=True)

        min_usage = request.query_params.get("min_usage")
        if min_usage:
            try:
                min_usage_int = int(min_usage)
                queryset = queryset.filter(usage_count__gte=min_usage_int)
            except ValueError:
                pass

        # Serialize licenses
        licenses_data = []
        for license_obj in queryset:
            license_data = LicenseSummarySerializer.from_license_model(license_obj)
            licenses_data.append(license_data)

        return Response(
            {
                "licenses": licenses_data,
            },
        )


class LicenseDetailView(APIView):
    """
    API Endpoint: GET /licenses/{license_code}
    Get complete license information with terms and permissions
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        summary="Get license details",
        description="Get complete license information including terms, permissions, and usage statistics",
        responses={
            200: LicenseDetailSerializer,
            404: OpenApiResponse(description="License not found"),
        },
    )
    def get(self, request, license_code):
        """Get detailed license information"""
        try:
            license_obj = License.objects.get(code=license_code)
        except License.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "LICENSE_NOT_FOUND",
                        "message": "License not found",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Serialize license details
        license_data = LicenseDetailSerializer.from_license_model(license_obj)

        return Response(license_data)


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
@extend_schema(
    summary="Get license usage statistics",
    description="Get detailed usage statistics for a specific license",
    responses={
        200: {
            "type": "object",
            "properties": {
                "license_code": {"type": "string"},
                "name": {"type": "string"},
                "usage_stats": {
                    "type": "object",
                    "properties": {
                        "total_usage": {"type": "integer"},
                        "assets_count": {"type": "integer"},
                        "resources_count": {"type": "integer"},
                        "access_grants_count": {"type": "integer"},
                        "popular_assets": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "title": {"type": "string"},
                                    "download_count": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
            },
        },
        404: OpenApiResponse(description="License not found"),
    },
)
def license_usage_statistics(request, license_code):
    """Get comprehensive usage statistics for a license"""
    try:
        license_obj = License.objects.get(code=license_code)
    except License.DoesNotExist:
        return Response(
            {"error": {"code": "LICENSE_NOT_FOUND", "message": "License not found"}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Calculate detailed statistics
    assets = Asset.objects.filter(license=license_obj)
    resources = Resource.objects.filter(default_license=license_obj)

    # Get access grants with this license
    try:
        from .models import AssetAccess

        access_grants = AssetAccess.all_objects.filter(effective_license=license_obj)
        access_grants_count = access_grants.count()
    except:
        access_grants_count = 0

    # Get popular assets with this license
    popular_assets = assets.order_by("-download_count")[:5]
    popular_assets_data = [
        {
            "id": asset.id,
            "title": asset.title,
            "download_count": asset.download_count,
        }
        for asset in popular_assets
    ]

    return Response(
        {
            "license_code": license_obj.code,
            "name": license_obj.name,
            "usage_stats": {
                "total_usage": assets.count() + resources.count() + access_grants_count,
                "assets_count": assets.count(),
                "resources_count": resources.count(),
                "access_grants_count": access_grants_count,
                "popular_assets": popular_assets_data,
            },
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
@extend_schema(
    summary="Get license terms",
    description="Get structured license terms in Arabic and English",
    parameters=[
        OpenApiParameter(
            name="language",
            description="Preferred language for terms",
            required=False,
            type=str,
            enum=["en", "ar"],
        ),
    ],
    responses={
        200: {
            "type": "object",
            "properties": {
                "license_code": {"type": "string"},
                "name": {"type": "string"},
                "terms": {
                    "type": "object",
                    "properties": {
                        "license_terms": {"type": "array"},
                        "permissions": {"type": "array"},
                        "conditions": {"type": "array"},
                        "limitations": {"type": "array"},
                    },
                },
                "language": {"type": "string"},
            },
        },
        404: OpenApiResponse(description="License not found"),
    },
)
def license_terms(request, license_code):
    """Get structured license terms with localization support"""
    try:
        license_obj = License.objects.get(code=license_code)
    except License.DoesNotExist:
        return Response(
            {"error": {"code": "LICENSE_NOT_FOUND", "message": "License not found"}},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get preferred language
    language = request.query_params.get("language", "en")

    # Prepare terms data
    terms_data = {
        "license_terms": license_obj.license_terms or [],
        "permissions": license_obj.permissions or [],
        "conditions": license_obj.conditions or [],
        "limitations": license_obj.limitations or [],
    }

    # Apply language filtering if Arabic is requested
    if language == "ar":
        # Filter for Arabic terms or use English as fallback
        for category in terms_data:
            if isinstance(terms_data[category], list):
                for item in terms_data[category]:
                    if isinstance(item, dict) and "title_ar" in item:
                        item["title"] = item.get("title_ar", item.get("title", ""))
                        item["description"] = item.get(
                            "description_ar",
                            item.get("description", ""),
                        )

    return Response(
        {
            "license_code": license_obj.code,
            "name": license_obj.name,
            "terms": terms_data,
            "language": language,
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
@extend_schema(
    summary="Search licenses",
    description="Search licenses by name, code, or terms content",
    parameters=[
        OpenApiParameter(
            name="q",
            description="Search query",
            required=True,
            type=str,
        ),
        OpenApiParameter(
            name="search_terms",
            description="Also search within license terms",
            required=False,
            type=bool,
        ),
    ],
    responses={
        200: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "results": {
                    "type": "array",
                    "items": LicenseSummarySerializer,
                },
            },
        },
    },
)
def search_licenses(request):
    """Search licenses by name, code, or terms"""
    query = request.query_params.get("q", "").strip()
    if not query:
        return Response(
            {
                "query": "",
                "results": [],
            },
        )

    search_terms = request.query_params.get("search_terms", "").lower() == "true"

    # Basic search in name and code
    queryset = License.objects.filter(
        Q(name__icontains=query)
        | Q(code__icontains=query)
        | Q(short_name__icontains=query)
        | Q(summary__icontains=query),
    )

    # Extended search in terms if requested
    if search_terms:
        queryset = queryset | License.objects.filter(
            Q(full_text__icontains=query) | Q(license_terms__icontains=query),
        )

    # Remove duplicates and order by relevance
    queryset = queryset.distinct().order_by("-is_default", "name")

    # Serialize results
    results_data = []
    for license_obj in queryset[:20]:  # Limit to 20 results
        license_data = LicenseSummarySerializer.from_license_model(license_obj)
        results_data.append(license_data)

    return Response(
        {
            "query": query,
            "results": results_data,
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
@extend_schema(
    summary="Get default license",
    description="Get the system default license (CC0 in V1)",
    responses={
        200: LicenseDetailSerializer,
        404: OpenApiResponse(description="Default license not found"),
    },
)
def default_license(request):
    """Get the system default license"""
    try:
        license_obj = License.objects.filter(is_default=True).first()
        if not license_obj:
            # Fallback to CC0 if no default is set
            license_obj = License.objects.filter(code="cc0").first()

        if not license_obj:
            return Response(
                {
                    "error": {
                        "code": "DEFAULT_LICENSE_NOT_FOUND",
                        "message": "Default license not configured",
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        license_data = LicenseDetailSerializer.from_license_model(license_obj)
        return Response(license_data)

    except Exception as e:
        return Response(
            {"error": {"code": "LICENSE_ERROR", "message": str(e)}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
