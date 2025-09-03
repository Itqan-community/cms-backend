"""
Core API views for basic functionality (health checks, etc.)
Authentication is now handled by apps.accounts.auth_views
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from datetime import datetime


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint to verify API status
    """
    return Response({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'version': '1.0.0'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def api_info(request):
    """
    Get API information and available endpoints
    """
    return Response({
        'name': 'Itqan CMS API',
        'version': '1.0.0',
        'description': 'Content Management System API for Itqan platform',
        'endpoints': {
            'health': '/api/v1/health/',
            'auth': {
                'register': '/api/v1/auth/register/',
                'login': '/api/v1/auth/login/',
                'profile': '/api/v1/auth/profile/',
                'logout': '/api/v1/auth/logout/',
                'token_refresh': '/api/v1/auth/token/refresh/',
                'oauth': {
                    'google': '/api/v1/auth/oauth/google/start/',
                    'github': '/api/v1/auth/oauth/github/start/'
                }
            },
            'docs': {
                'swagger': '/api/v1/docs/',
                'redoc': '/api/v1/redoc/',
                'schema': '/api/v1/schema/'
            }
        }
    })