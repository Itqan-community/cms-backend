"""
User service for Auth0 integration - handles user creation and role mapping
"""
import logging
from typing import Dict, Optional, Tuple, Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.accounts.models import Role

logger = logging.getLogger(__name__)

User = get_user_model()


class UserServiceError(Exception):
    """Base exception for user service errors"""
    pass


class RoleMappingError(UserServiceError):
    """Exception raised when role mapping fails"""
    pass


class UserCreationError(UserServiceError):
    """Exception raised when user creation fails"""
    pass


class Auth0UserService:
    """
    Service for managing Auth0 users in Django
    """
    
    def __init__(self):
        self.role_mapping = settings.AUTH0_ROLE_MAPPING
        self.default_role = settings.AUTH0_DEFAULT_ROLE
    
    def _map_auth0_roles_to_django(self, auth0_roles: list) -> str:
        """
        Map Auth0 roles to Django role names
        
        Args:
            auth0_roles: List of Auth0 role strings
            
        Returns:
            Django role name
            
        Raises:
            RoleMappingError: If role mapping fails
        """
        if not auth0_roles:
            logger.info(f"No Auth0 roles provided, using default role: {self.default_role}")
            return self.default_role
        
        # Find the first matching role (order matters for priority)
        for auth0_role in auth0_roles:
            django_role = self.role_mapping.get(auth0_role.lower())
            if django_role:
                logger.debug(f"Mapped Auth0 role '{auth0_role}' to Django role '{django_role}'")
                return django_role
        
        # No matching role found, use default
        logger.warning(f"No matching Django role for Auth0 roles {auth0_roles}, using default: {self.default_role}")
        return self.default_role
    
    def _get_or_create_role(self, role_name: str) -> Role:
        """
        Get or create a Django Role object
        
        Args:
            role_name: Name of the role
            
        Returns:
            Role object
            
        Raises:
            RoleMappingError: If role cannot be found or created
        """
        try:
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    'description': f'Auto-created role for {role_name} users',
                    'permissions': {}
                }
            )
            
            if created:
                logger.info(f"Created new role: {role_name}")
            else:
                logger.debug(f"Using existing role: {role_name}")
            
            return role
            
        except Exception as e:
            logger.error(f"Failed to get or create role '{role_name}': {e}")
            raise RoleMappingError(f"Failed to get or create role '{role_name}': {e}")
    
    def _generate_username_from_email(self, email: str) -> str:
        """
        Generate a unique username from email
        
        Args:
            email: User's email address
            
        Returns:
            Unique username
        """
        if not email:
            raise UserCreationError("Cannot generate username without email")
        
        # Use email as username initially
        base_username = email.lower()
        username = base_username
        counter = 1
        
        # Ensure username is unique
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
        
        return username
    
    def _create_user_from_auth0_info(self, user_info: Dict[str, Any]) -> User:
        """
        Create a new Django user from Auth0 user information
        
        Args:
            user_info: User information from Auth0 token
            
        Returns:
            Created User object
            
        Raises:
            UserCreationError: If user creation fails
        """
        try:
            # Extract required information
            auth0_id = user_info.get('auth0_id')
            email = user_info.get('email')
            
            if not auth0_id:
                raise UserCreationError("Auth0 ID is required for user creation")
            
            if not email:
                raise UserCreationError("Email is required for user creation")
            
            # Generate username
            username = self._generate_username_from_email(email)
            
            # Map roles
            auth0_roles = user_info.get('roles', [])
            django_role_name = self._map_auth0_roles_to_django(auth0_roles)
            role = self._get_or_create_role(django_role_name)
            
            # Extract names
            first_name = user_info.get('given_name', '')
            last_name = user_info.get('family_name', '')
            
            # If no given/family names, try to split the 'name' field
            if not first_name and not last_name:
                full_name = user_info.get('name', '')
                if full_name:
                    name_parts = full_name.split(' ', 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                auth0_id=auth0_id,
                role=role,
                is_active=True,
            )
            
            logger.info(f"Created new user: {email} with role: {django_role_name}")
            return user
            
        except Exception as e:
            logger.error(f"Failed to create user from Auth0 info: {e}")
            raise UserCreationError(f"Failed to create user: {e}")
    
    def _update_user_from_auth0_info(self, user: User, user_info: Dict[str, Any]) -> User:
        """
        Update existing Django user with Auth0 information
        
        Args:
            user: Existing User object
            user_info: User information from Auth0 token
            
        Returns:
            Updated User object
        """
        try:
            updated_fields = []
            
            # Update email if changed
            email = user_info.get('email')
            if email and user.email != email:
                user.email = email
                updated_fields.append('email')
            
            # Update names if provided
            first_name = user_info.get('given_name', '')
            last_name = user_info.get('family_name', '')
            
            # If no given/family names, try to split the 'name' field
            if not first_name and not last_name:
                full_name = user_info.get('name', '')
                if full_name:
                    name_parts = full_name.split(' ', 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated_fields.append('first_name')
            
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated_fields.append('last_name')
            
            # Update role if changed
            auth0_roles = user_info.get('roles', [])
            django_role_name = self._map_auth0_roles_to_django(auth0_roles)
            
            if not user.role or user.role.name != django_role_name:
                role = self._get_or_create_role(django_role_name)
                user.role = role
                updated_fields.append('role')
            
            # Update Auth0 ID if missing
            auth0_id = user_info.get('auth0_id')
            if auth0_id and not user.auth0_id:
                user.auth0_id = auth0_id
                updated_fields.append('auth0_id')
            
            # Save if any fields were updated
            if updated_fields:
                user.save(update_fields=updated_fields)
                logger.info(f"Updated user {user.email} fields: {updated_fields}")
            else:
                logger.debug(f"No updates needed for user: {user.email}")
            
            return user
            
        except Exception as e:
            logger.error(f"Failed to update user {user.email}: {e}")
            raise UserCreationError(f"Failed to update user: {e}")
    
    def get_or_create_user(self, user_info: Dict[str, Any]) -> Tuple[User, bool]:
        """
        Get or create a Django user from Auth0 user information
        
        Args:
            user_info: User information from Auth0 token
            
        Returns:
            Tuple of (User object, created flag)
            
        Raises:
            UserServiceError: If user lookup/creation fails
        """
        auth0_id = user_info.get('auth0_id')
        email = user_info.get('email')
        
        if not auth0_id:
            raise UserServiceError("Auth0 ID is required")
        
        if not email:
            raise UserServiceError("Email is required")
        
        try:
            with transaction.atomic():
                # Try to find user by Auth0 ID first
                try:
                    user = User.objects.select_related('role').get(auth0_id=auth0_id)
                    logger.debug(f"Found user by Auth0 ID: {auth0_id}")
                    
                    # Update user information
                    user = self._update_user_from_auth0_info(user, user_info)
                    return user, False
                    
                except User.DoesNotExist:
                    pass
                
                # Try to find user by email
                try:
                    user = User.objects.select_related('role').get(email=email)
                    logger.debug(f"Found user by email: {email}")
                    
                    # Update Auth0 ID if missing and update other info
                    user = self._update_user_from_auth0_info(user, user_info)
                    return user, False
                    
                except User.DoesNotExist:
                    pass
                
                # Create new user
                user = self._create_user_from_auth0_info(user_info)
                return user, True
                
        except Exception as e:
            logger.error(f"Failed to get or create user: {e}")
            raise UserServiceError(f"Failed to get or create user: {e}")
    
    def authenticate_user(self, token_payload: Dict[str, Any]) -> Optional[User]:
        """
        Authenticate user using Auth0 token payload
        
        Args:
            token_payload: Decoded JWT payload
            
        Returns:
            Authenticated User object or None
            
        Raises:
            UserServiceError: If authentication fails
        """
        try:
            # Extract user info from token
            from .jwt_validator import jwt_service
            user_info = jwt_service.extract_user_info(token_payload)
            
            # Get or create user
            user, created = self.get_or_create_user(user_info)
            
            # Check if user is active
            if not user.is_active:
                logger.warning(f"Inactive user attempted login: {user.email}")
                return None
            
            # Check email verification if required
            email_verified = user_info.get('email_verified', False)
            if not email_verified:
                logger.warning(f"Unverified email attempted login: {user.email}")
                # Still allow login but log the warning
            
            if created:
                logger.info(f"New user authenticated and created: {user.email}")
            else:
                logger.debug(f"Existing user authenticated: {user.email}")
            
            return user
            
        except Exception as e:
            logger.error(f"User authentication failed: {e}")
            raise UserServiceError(f"Authentication failed: {e}")
    
    def get_user_roles_info(self, user: User) -> Dict[str, Any]:
        """
        Get comprehensive role information for a user
        
        Args:
            user: User object
            
        Returns:
            Role information dictionary
        """
        if not user.role:
            return {
                'role_name': None,
                'permissions': {},
                'is_admin': False,
                'is_publisher': False,
                'is_developer': False,
                'is_reviewer': False,
            }
        
        role_name = user.role.name
        
        return {
            'role_name': role_name,
            'permissions': user.role.permissions,
            'is_admin': role_name == 'Admin',
            'is_publisher': role_name == 'Publisher',
            'is_developer': role_name == 'Developer',
            'is_reviewer': role_name == 'Reviewer',
        }


# Global user service instance
auth0_user_service = Auth0UserService()
