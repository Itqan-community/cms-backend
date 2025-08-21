"""
Authentication API views for Auth0 integration
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .jwt_validator import jwt_service, JWTValidationError
from .user_service import auth0_user_service, UserServiceError
from .jwks import jwks_service
from .backends import Auth0JWTBackend

logger = logging.getLogger(__name__)


class Auth0LoginView(APIView):
    """
    Validate Auth0 JWT token and return user information
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Validate Auth0 JWT token",
        description="Validate Auth0 JWT token and return user information",
        request={
            'type': 'object',
            'properties': {
                'token': {'type': 'string', 'description': 'Auth0 JWT access token'}
            },
            'required': ['token']
        }
    )
    def post(self, request):
        """Validate Auth0 JWT token and return user information"""
        token = request.data.get('token')
        
        if not token:
            return Response(
                {'error': 'Token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Use the authentication backend to validate token and get user
            backend = Auth0JWTBackend()
            user = backend.authenticate(request, token=token)
            
            if not user:
                return Response(
                    {'error': 'Invalid token or user authentication failed'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Get token info for response
            token_info = jwt_service.get_token_info(token)
            role_info = auth0_user_service.get_user_roles_info(user)
            
            response_data = {
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'full_name': user.get_full_name(),
                    'auth0_id': user.auth0_id,
                    'role': user.role.name if user.role else None,
                    'is_active': user.is_active,
                    'permissions': role_info.get('permissions', {}),
                    'role_flags': {
                        'is_admin': role_info.get('is_admin', False),
                        'is_publisher': role_info.get('is_publisher', False),
                        'is_developer': role_info.get('is_developer', False),
                        'is_reviewer': role_info.get('is_reviewer', False),
                    }
                },
                'token_info': {
                    'subject': token_info.get('subject'),
                    'expires_at': token_info.get('expires_at'),
                    'issued_at': token_info.get('issued_at'),
                },
                'message': 'User authenticated successfully'
            }
            
            logger.info(f"User {user.email} authenticated successfully via Auth0")
            return Response(response_data, status=status.HTTP_200_OK)
        
        except (JWTValidationError, UserServiceError) as e:
            logger.warning(f"Authentication failed: {e}")
            return Response(
                {'error': f'Authentication failed: {e}'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        except Exception as e:
            logger.error(f"Unexpected authentication error: {e}")
            return Response(
                {'error': 'Authentication service error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([AllowAny])
@extend_schema(
    summary="Validate token",
    description="Validate Auth0 JWT token without user lookup"
)
def validate_token(request):
    """Validate Auth0 JWT token without user authentication"""
    token = request.data.get('token')
    
    if not token:
        return Response(
            {'error': 'Token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user_info = jwt_service.validate_token_and_extract_user(token)
        token_info = jwt_service.get_token_info(token)
        
        return Response({
            'valid': True,
            'token_info': token_info,
            'user_info': user_info,
        }, status=status.HTTP_200_OK)
    
    except JWTValidationError as e:
        return Response(
            {'valid': False, 'error': str(e)},
            status=status.HTTP_401_UNAUTHORIZED
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@extend_schema(
    summary="Get user profile",
    description="Get authenticated user's profile information"
)
def user_profile(request):
    """Get current user's profile information"""
    try:
        user = request.user
        role_info = auth0_user_service.get_user_roles_info(user)
        
        return Response({
            'user': {
                'id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': user.get_full_name(),
                'auth0_id': user.auth0_id,
                'role': user.role.name if user.role else None,
                'is_active': user.is_active,
            },
            'role_info': role_info,
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Profile retrieval error: {e}")
        return Response(
            {'error': 'Failed to retrieve user profile'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
@extend_schema(
    summary="Get Auth0 configuration",
    description="Get Auth0 configuration for frontend integration"
)
def auth0_config(request):
    """Get Auth0 configuration for frontend"""
    from django.conf import settings
    
    return Response({
        'domain': settings.AUTH0_DOMAIN,
        'audience': settings.AUTH0_AUDIENCE,
        'client_id': settings.AUTH0_CLIENT_ID,
        'algorithm': settings.AUTH0_ALGORITHM,
        'role_mapping': settings.AUTH0_ROLE_MAPPING,
        'default_role': settings.AUTH0_DEFAULT_ROLE,
        'role_claim': settings.AUTH0_ROLE_CLAIM,
    }, status=status.HTTP_200_OK)


class TokenExchangeView(APIView):
    """
    Auth0 to Django JWT token exchange (Task 15: AUTH-002)
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Exchange Auth0 token for Django JWT",
        description="Validate Auth0 access token and return Django JWT with user information",
        request={
            'type': 'object',
            'properties': {
                'access_token': {'type': 'string', 'description': 'Auth0 access token'},
                'id_token': {'type': 'string', 'description': 'Auth0 ID token (optional)'}
            },
            'required': ['access_token']
        }
    )
    def post(self, request):
        """Exchange Auth0 tokens for Django JWT"""
        access_token = request.data.get('access_token')
        id_token = request.data.get('id_token')
        
        if not access_token:
            return Response(
                {'error': 'access_token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Use the authentication backend to validate token and get/create user
            backend = Auth0JWTBackend()
            user = backend.authenticate(request, token=access_token)
            
            if not user:
                return Response(
                    {'error': 'Invalid token or user authentication failed'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Generate Django JWT for the user
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(user)
            django_access_token = str(refresh.access_token)
            django_refresh_token = str(refresh)
            
            # Get user role and permissions info
            role_info = auth0_user_service.get_user_roles_info(user)
            
            # Return response with Django JWT and user info
            response_data = {
                'tokens': {
                    'access': django_access_token,
                    'refresh': django_refresh_token
                },
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'full_name': user.get_full_name(),
                    'auth0_id': user.auth0_id,
                    'role': user.role.name if user.role else None,
                    'is_active': user.is_active,
                    'permissions': role_info.get('permissions', {}),
                    'role_flags': {
                        'is_admin': role_info.get('is_admin', False),
                        'is_publisher': role_info.get('is_publisher', False),
                        'is_developer': role_info.get('is_developer', False),
                        'is_reviewer': role_info.get('is_reviewer', False),
                    }
                },
                'message': 'Token exchange successful'
            }
            
            logger.info(f"Token exchange successful for user {user.email}")
            return Response(response_data, status=status.HTTP_200_OK)
        
        except (JWTValidationError, UserServiceError) as e:
            logger.warning(f"Token exchange failed: {e}")
            return Response(
                {'error': f'Token exchange failed: {e}'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        except Exception as e:
            logger.error(f"Unexpected token exchange error: {e}")
            return Response(
                {'error': 'Token exchange service error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([AllowAny])
@extend_schema(
    summary="Auth0 health check",
    description="Check Auth0 JWKS service health"
)
def auth0_health(request):
    """Check Auth0 service health"""
    try:
        health_info = jwks_service.health_check()
        
        if health_info['healthy']:
            return Response(health_info, status=status.HTTP_200_OK)
        else:
            return Response(health_info, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    except Exception as e:
        logger.error(f"Auth0 health check error: {e}")
        return Response(
            {'healthy': False, 'error': str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )