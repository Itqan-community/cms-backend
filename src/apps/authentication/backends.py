"""
Custom Django authentication backend for Auth0 JWT tokens
"""
import logging
from typing import Optional, Any

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.http import HttpRequest

from .jwt_validator import jwt_service, JWTValidationError
from .user_service import auth0_user_service, UserServiceError

logger = logging.getLogger(__name__)

User = get_user_model()


class Auth0JWTBackend(BaseBackend):
    """
    Custom authentication backend for Auth0 JWT tokens
    """
    
    def authenticate(self, request: HttpRequest, token: str = None, **kwargs) -> Optional[User]:
        """
        Authenticate user using Auth0 JWT token
        
        Args:
            request: HTTP request object
            token: JWT token string
            **kwargs: Additional keyword arguments
            
        Returns:
            Authenticated User object or None
        """
        if not token:
            logger.debug("No token provided for authentication")
            return None
        
        try:
            # Validate JWT token and extract payload
            token_payload = jwt_service.decode_token(token)
            
            # Authenticate user using the token payload
            user = auth0_user_service.authenticate_user(token_payload)
            
            if user:
                logger.info(f"Successfully authenticated user: {user.email}")
                
                # Add token info to user object for later use
                user._auth0_token_payload = token_payload
                user._auth_backend = self.__class__.__module__ + '.' + self.__class__.__name__
                
                return user
            else:
                logger.warning("User authentication returned None (inactive user?)")
                return None
                
        except JWTValidationError as e:
            logger.warning(f"JWT validation failed: {e}")
            return None
        
        except UserServiceError as e:
            logger.error(f"User service error during authentication: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            return None
    
    def get_user(self, user_id: int) -> Optional[User]:
        """
        Get user by ID (required by Django auth backend interface)
        
        Args:
            user_id: User primary key
            
        Returns:
            User object or None
        """
        try:
            return User.objects.select_related('role').get(pk=user_id)
        except User.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    def has_perm(self, user_obj: User, perm: str, obj: Any = None) -> bool:
        """
        Check if user has a specific permission
        
        Args:
            user_obj: User object
            perm: Permission string
            obj: Object to check permission against
            
        Returns:
            True if user has permission
        """
        if not user_obj.is_active:
            return False
        
        # Superuser has all permissions
        if user_obj.is_superuser:
            return True
        
        # Check role-based permissions
        if user_obj.role:
            role_permissions = user_obj.role.permissions or {}
            return role_permissions.get(perm, False)
        
        return False
    
    def has_module_perms(self, user_obj: User, app_label: str) -> bool:
        """
        Check if user has permissions for a specific app
        
        Args:
            user_obj: User object
            app_label: Django app label
            
        Returns:
            True if user has module permissions
        """
        if not user_obj.is_active:
            return False
        
        # Superuser has all permissions
        if user_obj.is_superuser:
            return True
        
        # Admin role has access to all modules
        if user_obj.role and user_obj.role.name == 'Admin':
            return True
        
        # Check specific app permissions in role
        if user_obj.role:
            role_permissions = user_obj.role.permissions or {}
            app_perms = [perm for perm in role_permissions.keys() if perm.startswith(f'{app_label}.')]
            return any(role_permissions.get(perm, False) for perm in app_perms)
        
        return False
    
    def user_can_authenticate(self, user: User) -> bool:
        """
        Check if user is allowed to authenticate
        
        Args:
            user: User object
            
        Returns:
            True if user can authenticate
        """
        return user.is_active


class Auth0TokenAuthenticationMiddleware:
    """
    Middleware for Auth0 JWT token authentication
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.backend = Auth0JWTBackend()
    
    def __call__(self, request: HttpRequest):
        """
        Process request and authenticate user if token is present
        
        Args:
            request: HTTP request object
            
        Returns:
            HTTP response
        """
        # Skip authentication for certain paths
        skip_paths = [
            '/admin/',
            '/api/v1/auth/token/',
            '/api/v1/docs/',
            '/api/v1/redoc/',
            '/api/v1/schema/',
        ]
        
        if any(request.path.startswith(path) for path in skip_paths):
            return self.get_response(request)
        
        # Extract token from Authorization header
        token = self._extract_token_from_request(request)
        
        if token:
            # Authenticate user with token
            user = self.backend.authenticate(request, token=token)
            
            if user:
                # Set authenticated user
                request.user = user
                logger.debug(f"Authenticated user via token: {user.email}")
            else:
                logger.debug("Token authentication failed")
        
        response = self.get_response(request)
        return response
    
    def _extract_token_from_request(self, request: HttpRequest) -> Optional[str]:
        """
        Extract JWT token from request
        
        Args:
            request: HTTP request object
            
        Returns:
            JWT token string or None
        """
        # Check Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Check for token in query parameters (less secure, for debugging)
        token_param = request.GET.get('token')
        if token_param:
            logger.warning("Token provided in query parameter (not recommended for production)")
            return token_param
        
        return None


class TokenPermissionMixin:
    """
    Mixin for views that need token-based permission checking
    """
    
    def get_user_from_token(self, request: HttpRequest) -> Optional[User]:
        """
        Get authenticated user from token in request
        
        Args:
            request: HTTP request object
            
        Returns:
            User object or None
        """
        if hasattr(request, 'user') and request.user.is_authenticated:
            return request.user
        
        # Try to authenticate with token
        middleware = Auth0TokenAuthenticationMiddleware(lambda r: None)
        token = middleware._extract_token_from_request(request)
        
        if token:
            backend = Auth0JWTBackend()
            return backend.authenticate(request, token=token)
        
        return None
    
    def check_token_permission(self, request: HttpRequest, required_role: str = None) -> bool:
        """
        Check if user has required permission based on token
        
        Args:
            request: HTTP request object
            required_role: Required role name
            
        Returns:
            True if user has permission
        """
        user = self.get_user_from_token(request)
        
        if not user:
            return False
        
        if not required_role:
            return True
        
        return user.role and user.role.name == required_role
