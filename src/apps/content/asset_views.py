"""
Asset API views for simplified frontend interface.
Combines Resource + Distribution + Access Control into unified Asset endpoints.
"""
from rest_framework import status, views, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.openapi import OpenApiTypes

from .models import Resource, Distribution
from .serializers import AssetSummarySerializer, AssetDetailSerializer
from apps.licensing.models import License, AccessRequest
from apps.licensing.access_control import DistributionAccessController
from apps.licensing.serializers import AccessRequestSerializer


class AssetListView(views.APIView):
    """
    List assets with optional filtering by category and license.
    Combines resources and their distributions into simplified asset format.
    """
    permission_classes = [permissions.AllowAny]  # Public endpoint
    
    @extend_schema(
        tags=['Assets'],
        summary='List assets',
        description='Retrieve a list of available assets with optional filtering',
        parameters=[
            OpenApiParameter(
                name='category',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=['mushaf', 'tafsir', 'recitation'],
                description='Filter assets by category'
            ),
            OpenApiParameter(
                name='license_code',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter assets by license code'
            ),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'assets': {
                        'type': 'array',
                        'items': {'$ref': '#/components/schemas/AssetSummary'}
                    }
                }
            }
        }
    )
    def get(self, request):
        # Get published resources only
        resources = Resource.objects.filter(
            workflow_status='published',
            published_at__isnull=False
        )
        
        # Apply filters
        category = request.query_params.get('category')
        if category:
            # Map API categories to resource types
            category_map = {
                'mushaf': 'text',
                'tafsir': 'tafsir', 
                'recitation': 'audio'
            }
            resource_type = category_map.get(category)
            if resource_type:
                resources = resources.filter(resource_type=resource_type)
        
        license_code = request.query_params.get('license_code')
        if license_code:
            resources = resources.filter(licenses__code=license_code)
        
        # Convert to asset format
        assets = []
        access_controller = DistributionAccessController()
        
        for resource in resources:
            # Get the primary distribution for this resource
            distribution = resource.distributions.filter(is_active=True).first()
            if not distribution:
                continue
                
            # Check user access if authenticated
            has_access = False
            if request.user.is_authenticated:
                try:
                    access_result = access_controller.check_distribution_access(
                        request.user, distribution, raise_exception=False
                    )
                    has_access = access_result.get('access_granted', False)
                except:
                    has_access = False
            
            # Get primary license
            license = resource.licenses.filter(is_active=True).first()
            
            # Map resource type to API category
            type_to_category = {
                'text': 'mushaf',
                'tafsir': 'tafsir',
                'audio': 'recitation'
            }
            
            asset_data = {
                'id': resource.id,
                'title': resource.title,
                'description': resource.description,
                'thumbnail_url': self._get_thumbnail_url(resource),
                'category': type_to_category.get(resource.resource_type, 'mushaf'),
                'license': {
                    'code': self._get_license_code(license) if license else 'cc0',
                    'name': self._get_license_name(license) if license else 'CC0 - Public Domain'
                },
                'publisher': {
                    'id': resource.publisher.id,
                    'name': f"{resource.publisher.first_name} {resource.publisher.last_name}",
                    'thumbnail_url': self._get_publisher_thumbnail(resource.publisher),
                    'verified': True  # Simplified for V1
                },
                'has_access': has_access,
                'download_count': self._get_download_count(resource),
                'file_size': self._get_file_size(distribution)
            }
            assets.append(asset_data)
        
        return Response({'assets': assets})
    
    def _get_thumbnail_url(self, resource):
        """Get thumbnail URL for resource"""
        # For V1, use placeholder - in real system would be from MediaLib
        return f"https://cdn.example.com/thumbnails/asset-{resource.id}.jpg"
    
    def _get_publisher_thumbnail(self, user):
        """Get publisher thumbnail URL"""
        return f"https://cdn.example.com/publishers/publisher-{user.id}.jpg"
    
    def _get_download_count(self, resource):
        """Get download count for resource"""
        # For V1, return dummy count - would be from analytics in real system
        return 1250
    
    def _get_file_size(self, distribution):
        """Get file size for distribution"""
        # For V1, return dummy size - would be from actual file metadata
        return "2.5 MB"
    
    def _get_license_code(self, license):
        """Get license code from license object"""
        if not license:
            return 'cc0'
        
        # Map license types to codes - this is a temporary mapping
        # In a real system, License model should have a code field
        license_type_to_code = {
            'open': 'cc0',
            'restricted': 'custom-restricted',
            'commercial': 'commercial'
        }
        return license_type_to_code.get(license.license_type, 'cc0')
    
    def _get_license_name(self, license):
        """Get license name from license object"""
        if not license:
            return 'CC0 - Public Domain'
        
        # Map license types to names
        license_type_to_name = {
            'open': 'CC0 - Public Domain',
            'restricted': 'Custom Restricted License',
            'commercial': 'Commercial License'
        }
        return license_type_to_name.get(license.license_type, 'CC0 - Public Domain')


class AssetDetailView(views.APIView):
    """
    Get detailed information about a specific asset.
    """
    permission_classes = [permissions.AllowAny]  # Public endpoint
    
    @extend_schema(
        tags=['Assets'],
        summary='Get asset details',
        description='Retrieve detailed information about a specific asset',
        responses={
            200: {'$ref': '#/components/schemas/Asset'},
            404: {'$ref': '#/components/schemas/ApiError'}
        }
    )
    def get(self, request, asset_id):
        try:
            resource = get_object_or_404(
                Resource,
                id=asset_id,
                workflow_status='published',
                published_at__isnull=False
            )
        except:
            return Response({
                'error': {
                    'code': 'ASSET_NOT_FOUND',
                    'message': 'Asset not found'
                }
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get primary distribution
        distribution = resource.distributions.filter(is_active=True).first()
        if not distribution:
            return Response({
                'error': {
                    'code': 'ASSET_NOT_AVAILABLE',
                    'message': 'Asset not available for download'
                }
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check user access
        access_controller = DistributionAccessController()
        has_access = False
        requires_approval = True
        
        if request.user.is_authenticated:
            try:
                access_result = access_controller.check_distribution_access(
                    request.user, distribution, raise_exception=False
                )
                has_access = access_result.get('access_granted', False)
                
                # Check if license requires approval
                license = resource.licenses.filter(is_active=True).first()
                if license:
                    requires_approval = license.requires_approval
                else:
                    requires_approval = False  # Default to open access for V1
                    
            except:
                has_access = False
        
        # Get primary license
        license = resource.licenses.filter(is_active=True).first()
        
        # Map resource type to API category
        type_to_category = {
            'text': 'mushaf',
            'tafsir': 'tafsir',
            'audio': 'recitation'
        }
        
        asset_data = {
            'id': resource.id,
            'title': resource.title,
            'description': resource.description,
            'long_description': resource.description,  # For V1, same as description
            'thumbnail_url': f"https://cdn.example.com/thumbnails/asset-{resource.id}.jpg",
            'category': type_to_category.get(resource.resource_type, 'mushaf'),
            'license': self._get_license_detail(license) if license else self._get_default_license(),
            'snapshots': [
                {
                    'thumbnail_url': f"https://cdn.example.com/snapshots/asset-{resource.id}-1.jpg",
                    'title': 'لقطة من المحتوى ١',
                    'description': 'كما هو مبين في اللقطة المرفقة ١ .. كلام'
                }
            ],
            'publisher': {
                'id': resource.publisher.id,
                'name': f"{resource.publisher.first_name} {resource.publisher.last_name}",
                'thumbnail_url': f"https://cdn.example.com/publishers/publisher-{resource.publisher.id}.jpg",
                'bio': 'Dedicated to preserving Quranic texts',
                'verified': True
            },
            'resource': {
                'id': resource.id,
                'title': resource.title,
                'description': resource.description
            },
            'technical_details': {
                'file_size': "2.5 MB",
                'format': 'json',
                'encoding': 'UTF-8',
                'version': resource.version,
                'language': resource.language
            },
            'stats': {
                'download_count': 1250,
                'view_count': 5420,
                'created_at': resource.created_at.isoformat(),
                'updated_at': resource.updated_at.isoformat()
            },
            'access': {
                'has_access': has_access,
                'requires_approval': requires_approval
            },
            'related_assets': []  # For V1, empty - would be populated based on tags/categories
        }
        
        return Response(asset_data)
    
    def _get_license_detail(self, license):
        """Get detailed license information"""
        # Map license type to code and get details
        license_code = self._get_license_code(license)
        license_name = self._get_license_name(license)
        
        return {
            'code': license_code,
            'name': license_name,
            'short_name': license_code.upper(),
            'url': f"https://creativecommons.org/licenses/{license_code}/" if license_code.startswith('cc') else "#",
            'icon_url': f"https://cdn.example.com/licenses/{license_code}.svg",
            'summary': license.terms[:100] + "..." if len(license.terms) > 100 else license.terms,
            'full_text': license.terms,
            'legal_code_url': f"https://creativecommons.org/licenses/{license_code}/legalcode" if license_code.startswith('cc') else "#",
            'license_terms': [],
            'permissions': [],
            'conditions': [],
            'limitations': [],
            'usage_count': 1250,
            'is_default': license_code == 'cc0'
        }
    
    def _get_default_license(self):
        """Get default CC0 license"""
        return {
            'code': 'cc0',
            'name': 'CC0 - Public Domain',
            'short_name': 'CC0',
            'url': 'https://creativecommons.org/publicdomain/zero/1.0/',
            'icon_url': 'https://cdn.example.com/licenses/cc0.svg',
            'summary': 'You can copy, modify, distribute and perform the work',
            'full_text': 'The person who associated a work with this deed has dedicated the work to the public domain...',
            'legal_code_url': 'https://creativecommons.org/publicdomain/zero/1.0/legalcode',
            'license_terms': [],
            'permissions': [],
            'conditions': [],
            'limitations': [],
            'usage_count': 1250,
            'is_default': True
        }
    
    def _get_license_code(self, license):
        """Get license code from license object"""
        if not license:
            return 'cc0'
        
        # Map license types to codes - this is a temporary mapping
        # In a real system, License model should have a code field
        license_type_to_code = {
            'open': 'cc0',
            'restricted': 'custom-restricted',
            'commercial': 'commercial'
        }
        return license_type_to_code.get(license.license_type, 'cc0')
    
    def _get_license_name(self, license):
        """Get license name from license object"""
        if not license:
            return 'CC0 - Public Domain'
        
        # Map license types to names
        license_type_to_name = {
            'open': 'CC0 - Public Domain',
            'restricted': 'Custom Restricted License',
            'commercial': 'Commercial License'
        }
        return license_type_to_name.get(license.license_type, 'CC0 - Public Domain')


class AssetRequestAccessView(views.APIView):
    """
    Request access to download a specific asset.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        tags=['Assets'],
        summary='Request asset access',
        description='Request access to download a specific asset',
        request={
            'type': 'object',
            'properties': {
                'purpose': {
                    'type': 'string',
                    'description': 'Reason for requesting access'
                },
                'intended_use': {
                    'type': 'string',
                    'enum': ['commercial', 'non-commercial'],
                    'description': 'Intended use of the asset'
                }
            },
            'required': ['purpose', 'intended_use']
        },
        responses={
            200: {'$ref': '#/components/schemas/AccessRequestResponse'},
            404: {'$ref': '#/components/schemas/ApiError'}
        }
    )
    def post(self, request, asset_id):
        try:
            resource = get_object_or_404(
                Resource,
                id=asset_id,
                workflow_status='published',
                published_at__isnull=False
            )
        except:
            return Response({
                'error': {
                    'code': 'ASSET_NOT_FOUND',
                    'message': 'Asset not found'
                }
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get primary distribution
        distribution = resource.distributions.filter(is_active=True).first()
        if not distribution:
            return Response({
                'error': {
                    'code': 'ASSET_NOT_AVAILABLE',
                    'message': 'Asset not available for download'
                }
            }, status=status.HTTP_404_NOT_FOUND)
        
        purpose = request.data.get('purpose')
        intended_use = request.data.get('intended_use')
        
        if not purpose or not intended_use:
            return Response({
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': 'Purpose and intended_use are required'
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # For V1: Auto-approve all requests
        # Create or get existing access request
        access_request, created = AccessRequest.objects.get_or_create(
            requester=request.user,
            distribution=distribution,
            defaults={
                'justification': f"Purpose: {purpose}, Intended use: {intended_use}",
                'status': 'approved',
                'priority': 'normal',  # Add required priority field
                'requested_at': timezone.now(),  # Add requested_at
                'reviewed_at': timezone.now(),   # Add reviewed_at for approval
                'approved_by': request.user,     # Set approved_by to current user
                'notification_sent': False       # Add notification_sent field
            }
        )
        
        if not created and access_request.status == 'approved':
            # Already have access
            pass
        else:
            # Auto-approve new requests
            access_request.status = 'approved'
            access_request.reviewed_at = timezone.now()
            access_request.approved_by = request.user
            access_request.save()
        
        return Response({
            'request_id': access_request.id,
            'status': 'approved',
            'message': 'Access granted automatically',
            'access': {
                'download_url': f"/assets/{asset_id}/download",
                'expires_at': None,  # V1: No expiration
                'granted_at': timezone.now().isoformat()
            }
        })


class AssetDownloadView(views.APIView):
    """
    Download asset file (requires access).
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        tags=['Assets'],
        summary='Download asset file',
        description='Download the asset file (requires access)',
        responses={
            200: {
                'content': {
                    'application/octet-stream': {
                        'schema': {'type': 'string', 'format': 'binary'}
                    }
                },
                'headers': {
                    'Content-Disposition': {'schema': {'type': 'string'}},
                    'Content-Length': {'schema': {'type': 'integer'}}
                }
            },
            403: {'$ref': '#/components/schemas/ApiError'},
            404: {'$ref': '#/components/schemas/ApiError'}
        }
    )
    def get(self, request, asset_id):
        try:
            resource = get_object_or_404(
                Resource,
                id=asset_id,
                workflow_status='published',
                published_at__isnull=False
            )
        except:
            return Response({
                'error': {
                    'code': 'ASSET_NOT_FOUND',
                    'message': 'Asset not found'
                }
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get primary distribution
        distribution = resource.distributions.filter(is_active=True).first()
        if not distribution:
            return Response({
                'error': {
                    'code': 'ASSET_NOT_AVAILABLE',
                    'message': 'Asset not available for download'
                }
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check access
        access_controller = DistributionAccessController()
        try:
            access_result = access_controller.check_distribution_access(
                request.user, distribution, raise_exception=True
            )
        except Exception as e:
            return Response({
                'error': {
                    'code': 'ACCESS_DENIED',
                    'message': 'You need to request access to download this asset'
                }
            }, status=status.HTTP_403_FORBIDDEN)
        
        # For V1: Return dummy file content
        # In real implementation, this would stream the actual file
        dummy_content = f'{{"title": "{resource.title}", "content": "Quranic data content here...", "version": "{resource.version}"}}'
        
        response = HttpResponse(
            dummy_content,
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{resource.title.lower().replace(" ", "-")}-v{resource.version}.json"'
        response['Content-Length'] = len(dummy_content)
        
        return response
