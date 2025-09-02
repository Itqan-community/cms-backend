"""
Other mock API views (publishers, licenses, resources, content standards, system)
"""

from datetime import datetime, timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from .dummy_data import (
    DUMMY_PUBLISHERS, DUMMY_LICENSES, DUMMY_ASSETS,
    CONTENT_STANDARDS, APP_CONFIG
)


# ============================================================================
# PUBLISHERS ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_publisher_details(request, publisher_id):
    """Get publisher details"""
    publisher = next((p for p in DUMMY_PUBLISHERS if p['id'] == int(publisher_id)), None)
    
    if not publisher:
        return Response({
            "error": {
                "code": "PUBLISHER_NOT_FOUND",
                "message": "Publisher not found"
            }
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Add assets for this publisher
    publisher_assets = [a for a in DUMMY_ASSETS if a['publisher']['id'] == int(publisher_id)]
    asset_summaries = []
    
    for asset in publisher_assets:
        summary = {
            "id": asset["id"],
            "title": asset["title"],
            "description": asset["description"],
            "thumbnail_url": asset["thumbnail_url"],
            "category": asset["category"],
            "license": {
                "code": asset["license"]["code"],
                "name": asset["license"]["name"],
                "short_name": asset["license"]["short_name"],
                "icon_url": asset["license"]["icon_url"],
                "is_default": asset["license"]["is_default"]
            },
            "publisher": asset["publisher"],
            "has_access": asset["has_access"],
            "download_count": asset["download_count"],
            "file_size": asset["file_size"]
        }
        asset_summaries.append(summary)
    
    publisher_data = publisher.copy()
    publisher_data['assets'] = asset_summaries
    
    return Response(publisher_data, status=status.HTTP_200_OK)


# ============================================================================
# RESOURCES ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def download_resource(request, resource_id):
    """Download original resource"""
    # Find assets belonging to this resource
    resource_assets = [a for a in DUMMY_ASSETS if a.get('resource', {}).get('id') == int(resource_id)]
    
    if not resource_assets:
        return Response({
            "error": {
                "code": "RESOURCE_NOT_FOUND",
                "message": "Resource not found"
            }
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if user has access to at least one asset
    has_any_access = any(asset['has_access'] for asset in resource_assets)
    
    if not has_any_access:
        return Response({
            "error": {
                "code": "ACCESS_DENIED",
                "message": "You need access to at least one asset in this resource to download"
            }
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Return dummy package content
    dummy_content = f"Dummy resource package for resource {resource_id} containing {len(resource_assets)} assets"
    response = HttpResponse(dummy_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="resource_{resource_id}.zip"'
    response['Content-Length'] = len(dummy_content)
    
    return response


# ============================================================================
# LICENSES ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_license_by_code(request, license_code):
    """Get license by code"""
    license_data = next((l for l in DUMMY_LICENSES if l['code'] == license_code), None)
    
    if not license_data:
        return Response({
            "error": {
                "code": "LICENSE_NOT_FOUND",
                "message": "License not found"
            }
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response(license_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_licenses(request):
    """List all licenses"""
    license_summaries = []
    for license_data in DUMMY_LICENSES:
        summary = {
            "code": license_data["code"],
            "name": license_data["name"],
            "short_name": license_data["short_name"],
            "icon_url": license_data["icon_url"],
            "is_default": license_data["is_default"]
        }
        license_summaries.append(summary)
    
    return Response({"licenses": license_summaries}, status=status.HTTP_200_OK)


# ============================================================================
# CONTENT STANDARDS ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_content_standards(request):
    """Get content standards"""
    return Response(CONTENT_STANDARDS, status=status.HTTP_200_OK)


# ============================================================================
# SYSTEM ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_app_config(request):
    """Get application configuration"""
    return Response(APP_CONFIG, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check"""
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "services": {
            "database": "healthy",
            "storage": "healthy",
            "auth": "healthy"
        }
    }
    
    return Response(health_data, status=status.HTTP_200_OK)
