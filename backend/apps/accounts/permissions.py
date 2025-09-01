"""
Role-based permission classes for Itqan CMS
Implements granular permissions for Admin, Publisher, Developer, and Reviewer roles
"""
from rest_framework import permissions


class BaseRolePermission(permissions.BasePermission):
    """
    Base permission class for role-based access control
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active and
            request.user.role and
            request.user.role.is_active
        )

    def has_object_permission(self, request, view, obj):
        """
        Override in subclasses for object-level permissions
        """
        return self.has_permission(request, view)


class IsAdminUser(BaseRolePermission):
    """
    Permission class for Admin users only
    Admins have full access to all system features
    """
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) and
            request.user.is_admin()
        )


class IsPublisherUser(BaseRolePermission):
    """
    Permission class for Publisher users
    Publishers can create and manage their own content
    """
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) and
            request.user.is_publisher()
        )

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        # Publishers can only access their own content
        if hasattr(obj, 'publisher'):
            return obj.publisher == request.user
        elif hasattr(obj, 'resource') and hasattr(obj.resource, 'publisher'):
            return obj.resource.publisher == request.user
        
        return False


class IsDeveloperUser(BaseRolePermission):
    """
    Permission class for Developer users
    Developers have read-only access to published content and can create access requests
    """
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) and
            request.user.is_developer()
        )

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        # Developers can only read published content
        if hasattr(obj, 'is_published'):
            return obj.is_published
        elif hasattr(obj, 'resource') and hasattr(obj.resource, 'is_published'):
            return obj.resource.is_published
        
        return True  # Default allow for other objects


class IsReviewerUser(BaseRolePermission):
    """
    Permission class for Reviewer users
    Reviewers can read all content and manage workflow states
    """
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) and
            request.user.is_reviewer()
        )


class IsAdminOrPublisher(BaseRolePermission):
    """
    Permission class for Admin or Publisher users
    """
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) and
            (request.user.is_admin() or request.user.is_publisher())
        )

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        # Admins have full access
        if request.user.is_admin():
            return True

        # Publishers can only access their own content
        if request.user.is_publisher():
            if hasattr(obj, 'publisher'):
                return obj.publisher == request.user
            elif hasattr(obj, 'resource') and hasattr(obj.resource, 'publisher'):
                return obj.resource.publisher == request.user
        
        return False


class IsAdminOrReviewer(BaseRolePermission):
    """
    Permission class for Admin or Reviewer users
    """
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) and
            (request.user.is_admin() or request.user.is_reviewer())
        )


class IsAdminOrOwner(BaseRolePermission):
    """
    Permission class for Admin users or object owners
    """
    def has_permission(self, request, view):
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        # Admins have full access
        if request.user.is_admin():
            return True

        # Check if user is the owner of the object
        if hasattr(obj, 'publisher'):
            return obj.publisher == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class IsAdminOrReadOnly(BaseRolePermission):
    """
    Permission class for Admin users with write access, others with read-only
    """
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        # Admin users have full access
        if request.user.is_admin():
            return True

        # All other authenticated users have read-only access
        if request.method in permissions.SAFE_METHODS:
            return True

        return False


class ContentManagementPermission(BaseRolePermission):
    """
    Permission class for content management operations
    Handles Resource, License, and Distribution permissions based on user role
    """
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        action = getattr(view, 'action', None)
        
        # Admin users have full access
        if request.user.is_admin():
            return True

        # Publishers can create and manage their own content
        if request.user.is_publisher():
            if request.method in ['GET', 'POST', 'PUT', 'PATCH']:
                return True

        # Reviewers can read and review content
        if request.user.is_reviewer():
            if request.method in ['GET', 'PATCH']:  # PATCH for workflow updates
                return True

        # Developers can only read published content
        if request.user.is_developer():
            if request.method in permissions.SAFE_METHODS:
                return True

        return False

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        # Admin users have full access
        if request.user.is_admin():
            return True

        # Publishers can only access their own content
        if request.user.is_publisher():
            if hasattr(obj, 'publisher'):
                return obj.publisher == request.user
            elif hasattr(obj, 'resource') and hasattr(obj.resource, 'publisher'):
                return obj.resource.publisher == request.user

        # Reviewers can read all content and update workflow states
        if request.user.is_reviewer():
            if request.method in permissions.SAFE_METHODS:
                return True
            # Allow PATCH for workflow updates
            if request.method == 'PATCH':
                return True

        # Developers can only read published content
        if request.user.is_developer():
            if request.method in permissions.SAFE_METHODS:
                if hasattr(obj, 'is_published'):
                    return obj.is_published
                elif hasattr(obj, 'resource') and hasattr(obj.resource, 'is_published'):
                    return obj.resource.is_published
                return True

        return False


class AccessRequestPermission(BaseRolePermission):
    """
    Permission class for AccessRequest operations
    """
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        # Admin and Reviewers can manage all access requests
        if request.user.is_admin() or request.user.is_reviewer():
            return True

        # Publishers can view access requests for their content
        if request.user.is_publisher():
            if request.method in permissions.SAFE_METHODS:
                return True

        # Developers can create and view their own access requests
        if request.user.is_developer():
            return True

        return False

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        # Admin and Reviewers have full access
        if request.user.is_admin() or request.user.is_reviewer():
            return True

        # Publishers can view requests for their content
        if request.user.is_publisher():
            if hasattr(obj, 'resource') and hasattr(obj.resource, 'publisher'):
                return obj.resource.publisher == request.user

        # Developers can only access their own requests
        if request.user.is_developer():
            if hasattr(obj, 'developer'):
                return obj.developer == request.user

        return False


class UsageEventPermission(BaseRolePermission):
    """
    Permission class for UsageEvent operations
    """
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        # Admin users have full access
        if request.user.is_admin():
            return True

        # All other users can only read
        if request.method in permissions.SAFE_METHODS:
            return True

        return False

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        # Admin users have full access
        if request.user.is_admin():
            return True

        # Publishers can view usage events for their content
        if request.user.is_publisher():
            if hasattr(obj, 'resource') and hasattr(obj.resource, 'publisher'):
                return obj.resource.publisher == request.user

        # Developers can view their own usage events
        if request.user.is_developer():
            if hasattr(obj, 'user'):
                return obj.user == request.user

        return False


class APIThrottlePermission(BaseRolePermission):
    """
    Permission class for API rate limiting based on user role
    """
    ROLE_RATE_LIMITS = {
        'Admin': None,  # No limit for admin
        'Publisher': 1000,  # 1000 requests per hour
        'Developer': 500,   # 500 requests per hour  
        'Reviewer': 100,    # 100 requests per hour
    }

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        # Check if user has exceeded their role-based rate limit
        role_name = request.user.role.name
        rate_limit = self.ROLE_RATE_LIMITS.get(role_name)
        
        if rate_limit is None:
            return True  # No limit

        # This would integrate with DRF throttling
        # For now, just return True - actual throttling handled by DRF throttle classes
        return True
