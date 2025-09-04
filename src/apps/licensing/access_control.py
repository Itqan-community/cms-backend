"""
Access control for Distribution resources based on AccessRequest workflow
"""
import logging
from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.utils import timezone

from django.db import models
from .models import AccessRequest, LegacyLicense

logger = logging.getLogger(__name__)

User = get_user_model()


class DistributionAccessError(Exception):
    """Base exception for distribution access errors"""
    pass


class AccessDeniedError(DistributionAccessError):
    """Exception raised when access is denied"""
    pass


class LicenseViolationError(DistributionAccessError):
    """Exception raised when license terms are violated"""
    pass


class DistributionAccessController:
    """
    Service for controlling access to distributions based on AccessRequest workflow
    """
    
    def __init__(self):
        self.cache_ttl = 300  # 5 minutes cache for access decisions
    
    def check_distribution_access(self, user: User, distribution, raise_exception: bool = True) -> Dict[str, Any]:
        """
        Check if user has access to a specific distribution
        
        Args:
            user: User requesting access
            distribution: Distribution object
            raise_exception: Whether to raise exception on access denial
            
        Returns:
            Access check result dictionary
            
        Raises:
            AccessDeniedError: If access is denied and raise_exception is True
            LicenseViolationError: If license terms are violated
        """
        result = {
            'access_granted': False,
            'access_type': None,
            'access_request': None,
            'license': None,
            'reason': 'Unknown',
            'restrictions': {}
        }
        
        try:
            # Admin users have unrestricted access
            if user.is_admin():
                result.update({
                    'access_granted': True,
                    'access_type': 'admin',
                    'reason': 'Admin user has unrestricted access'
                })
                return result
            
            # Publishers have access to their own resources
            if user.is_publisher() and distribution.resource.publisher == user:
                result.update({
                    'access_granted': True,
                    'access_type': 'owner',
                    'reason': 'Publisher has access to own resource'
                })
                return result
            
            # Check if resource is published
            if not distribution.resource.published_at:
                result['reason'] = 'Resource is not published'
                if raise_exception:
                    raise AccessDeniedError("Resource is not published")
                return result
            
            # Get active license for the resource
            license_obj = self._get_active_license(distribution.resource)
            if not license_obj:
                result['reason'] = 'No active license found'
                if raise_exception:
                    raise AccessDeniedError("No active license found for resource")
                return result
            
            result['license'] = license_obj
            
            # Check if license requires approval
            if not license_obj.requires_approval:
                # Open access - check license restrictions only
                access_check = self._check_license_restrictions(user, license_obj)
                result.update(access_check)
                result.update({
                    'access_granted': access_check['allowed'],
                    'access_type': 'open',
                    'reason': 'Open license access' if access_check['allowed'] else access_check['reason']
                })
                
                if not result['access_granted'] and raise_exception:
                    raise LicenseViolationError(result['reason'])
                
                return result
            
            # Restricted access - check AccessRequest
            access_request = self._get_valid_access_request(user, distribution)
            if not access_request:
                result['reason'] = 'No valid access request found'
                if raise_exception:
                    raise AccessDeniedError("Access requires approval. Please submit an access request.")
                return result
            
            result['access_request'] = access_request
            
            # Check license restrictions for approved access
            access_check = self._check_license_restrictions(user, license_obj)
            result.update(access_check)
            result.update({
                'access_granted': access_check['allowed'],
                'access_type': 'approved',
                'reason': 'Approved access request' if access_check['allowed'] else access_check['reason']
            })
            
            if not result['access_granted'] and raise_exception:
                raise LicenseViolationError(result['reason'])
            
            return result
            
        except (AccessDeniedError, LicenseViolationError):
            if raise_exception:
                raise
            return result
        
        except Exception as e:
            logger.error(f"Unexpected error in access check: {e}")
            result['reason'] = 'Internal access control error'
            if raise_exception:
                raise AccessDeniedError("Internal access control error")
            return result
    
    def _get_active_license(self, resource) -> Optional[License]:
        """Get active license for a resource"""
        try:
            return resource.licenses.filter(
                is_active=True,
                effective_from__lte=timezone.now()
            ).filter(
                models.Q(expires_at__isnull=True) | 
                models.Q(expires_at__gt=timezone.now())
            ).first()
        except Exception:
            return None
    
    def _get_valid_access_request(self, user: User, distribution) -> Optional[AccessRequest]:
        """Get valid (approved and not expired) access request"""
        try:
            return AccessRequest.objects.filter(
                requester=user,
                distribution=distribution,
                status='approved',
                is_active=True
            ).filter(
                models.Q(expires_at__isnull=True) | 
                models.Q(expires_at__gt=timezone.now())
            ).first()
        except Exception:
            return None
    
    def _check_license_restrictions(self, user: User, license_obj: License) -> Dict[str, Any]:
        """
        Check license-specific restrictions
        
        Returns:
            Dictionary with 'allowed', 'reason', and 'restrictions' keys
        """
        result = {
            'allowed': True,
            'reason': '',
            'restrictions': {}
        }
        
        try:
            geographic_restrictions = license_obj.geographic_restrictions or {}
            usage_restrictions = license_obj.usage_restrictions or {}
            
            # Check geographic restrictions
            # Note: In a real implementation, you'd get user's country from IP or profile
            user_country = getattr(user, 'country', None)
            if user_country and not license_obj.is_country_allowed(user_country):
                result.update({
                    'allowed': False,
                    'reason': f'Access not allowed from country: {user_country}'
                })
                return result
            
            # Check attribution requirements
            if usage_restrictions.get('requires_attribution', False):
                result['restrictions']['attribution'] = {
                    'required': True,
                    'text': usage_restrictions.get('attribution_text', '')
                }
            
            # Check rate limits
            rate_limits = usage_restrictions.get('rate_limits', {})
            if rate_limits:
                result['restrictions']['rate_limits'] = rate_limits
            
            # Store all restrictions for reference
            result['restrictions']['geographic'] = geographic_restrictions
            result['restrictions']['usage'] = usage_restrictions
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking license restrictions: {e}")
            result.update({
                'allowed': False,
                'reason': 'Error validating license restrictions'
            })
            return result
    
    def require_distribution_access(self, user: User, distribution) -> Dict[str, Any]:
        """
        Decorator/utility function to require distribution access
        
        Args:
            user: User requesting access
            distribution: Distribution object
            
        Returns:
            Access check result
            
        Raises:
            PermissionDenied: If access is denied
        """
        try:
            return self.check_distribution_access(user, distribution, raise_exception=True)
        except (AccessDeniedError, LicenseViolationError) as e:
            raise PermissionDenied(str(e))
    
    def log_access_attempt(self, user: User, distribution, granted: bool, reason: str = ''):
        """
        Log access attempt for audit purposes
        """
        try:
            logger.info(
                f"Distribution access: user={user.email}, "
                f"distribution={distribution.id}, "
                f"resource={distribution.resource.title}, "
                f"granted={granted}, "
                f"reason={reason}"
            )
            
            # In a real implementation, you might want to store this in a dedicated audit log
            # or send to analytics service
            
        except Exception as e:
            logger.error(f"Failed to log access attempt: {e}")
    
    def get_user_access_summary(self, user: User) -> Dict[str, Any]:
        """
        Get summary of user's access rights
        
        Args:
            user: User to get summary for
            
        Returns:
            Access summary dictionary
        """
        summary = {
            'user_id': str(user.id),
            'user_email': user.email,
            'user_role': user.role.name if user.role else None,
            'active_requests': 0,
            'approved_requests': 0,
            'pending_requests': 0,
            'expired_requests': 0,
            'accessible_distributions': []
        }
        
        try:
            # Count access requests by status
            if user.is_developer():
                user_requests = AccessRequest.objects.filter(requester=user, is_active=True)
                summary.update({
                    'active_requests': user_requests.count(),
                    'approved_requests': user_requests.filter(status='approved').count(),
                    'pending_requests': user_requests.filter(status__in=['pending', 'under_review']).count(),
                    'expired_requests': user_requests.filter(status='expired').count(),
                })
                
                # Get accessible distributions
                approved_requests = user_requests.filter(
                    status='approved'
                ).filter(
                    models.Q(expires_at__isnull=True) | 
                    models.Q(expires_at__gt=timezone.now())
                )
                
                for request in approved_requests:
                    summary['accessible_distributions'].append({
                        'distribution_id': str(request.distribution.id),
                        'resource_title': request.distribution.resource.title,
                        'format_type': request.distribution.format_type,
                        'expires_at': request.expires_at,
                        'access_request_id': str(request.id)
                    })
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting user access summary: {e}")
            return summary


# Global access controller instance
distribution_access_controller = DistributionAccessController()


def require_distribution_access(distribution_param: str = 'distribution'):
    """
    Decorator to require distribution access for view functions
    
    Args:
        distribution_param: Name of the parameter containing the distribution
    """
    def decorator(func):
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Get distribution from view kwargs or request
            distribution = kwargs.get(distribution_param)
            if not distribution:
                raise PermissionDenied("Distribution not found")
            
            # Check access
            access_result = distribution_access_controller.require_distribution_access(
                request.user, distribution
            )
            
            # Log access attempt
            distribution_access_controller.log_access_attempt(
                request.user, distribution, True, access_result.get('reason', '')
            )
            
            # Add access info to request for view use
            request.distribution_access = access_result
            
            return func(request, *args, **kwargs)
        
        return wrapper
    return decorator
