"""
Asset-related mock API views
"""

from datetime import datetime, timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from .dummy_data import DUMMY_ASSETS


@api_view(['GET'])
@permission_classes([AllowAny])
def list_assets(request):
    """List assets with optional filtering"""
    category = request.GET.get('category')
    license_code = request.GET.get('license_code')
    
    assets = DUMMY_ASSETS.copy()
    
    # Apply filters
    if category:
        assets = [a for a in assets if a['category'] == category]
    
    if license_code:
        assets = [a for a in assets if a['license']['code'] == license_code]
    
    # Return summary format
    asset_summaries = []
    for asset in assets:
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
    
    return Response({"assets": asset_summaries}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_asset_details(request, asset_id):
    """Get asset details"""
    asset = next((a for a in DUMMY_ASSETS if a['id'] == int(asset_id)), None)
    
    if not asset:
        return Response({
            "error": {
                "code": "ASSET_NOT_FOUND",
                "message": "Asset not found"
            }
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response(asset, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def request_asset_access(request, asset_id):
    """Request asset access"""
    asset = next((a for a in DUMMY_ASSETS if a['id'] == int(asset_id)), None)
    
    if not asset:
        return Response({
            "error": {
                "code": "ASSET_NOT_FOUND",
                "message": "Asset not found"
            }
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Simulate auto-approval for most assets
    response_data = {
        "request_id": 123,
        "status": "approved",
        "message": "Access granted automatically",
        "access": {
            "download_url": f"/assets/{asset_id}/download",
            "expires_at": None,
            "granted_at": datetime.now(timezone.utc).isoformat()
        }
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def download_asset(request, asset_id):
    """Download asset file"""
    asset = next((a for a in DUMMY_ASSETS if a['id'] == int(asset_id)), None)
    
    if not asset:
        return Response({
            "error": {
                "code": "ASSET_NOT_FOUND",
                "message": "Asset not found"
            }
        }, status=status.HTTP_404_NOT_FOUND)
    
    if not asset['has_access']:
        return Response({
            "error": {
                "code": "ACCESS_DENIED",
                "message": "You need to request access to download this asset"
            }
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Return dummy file content
    dummy_content = f"Dummy content for asset {asset_id}: {asset['title']}"
    response = HttpResponse(dummy_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{asset["title"].replace(" ", "_")}.txt"'
    response['Content-Length'] = len(dummy_content)
    
    return response
