"""
Custom permission classes for Itqan CMS API
"""
from rest_framework import permissions


class IsAuthenticatedAndActive(permissions.BasePermission):
    """
    Permission to only allow authenticated and active users
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active
        )


class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow Admin users
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active and
            request.user.is_admin()
        )


class IsPublisherUser(permissions.BasePermission):
    """
    Permission to only allow Publisher users
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active and
            request.user.is_publisher()
        )


class IsDeveloperUser(permissions.BasePermission):
    """
    Permission to only allow Developer users
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active and
            request.user.is_developer()
        )


class IsReviewerUser(permissions.BasePermission):
    """
    Permission to only allow Reviewer users
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active and
            request.user.is_reviewer()
        )


class IsAdminOrPublisher(permissions.BasePermission):
    """
    Permission to allow Admin or Publisher users
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active and
            (request.user.is_admin() or request.user.is_publisher())
        )


class IsAdminOrDeveloper(permissions.BasePermission):
    """
    Permission to allow Admin or Developer users
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active and
            (request.user.is_admin() or request.user.is_developer())
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to allow owners of an object or Admin users
    """
    def has_object_permission(self, request, view, obj):
        # Admin users can access everything
        if request.user.is_admin():
            return True
        
        # Check if user is the owner based on different ownership patterns
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'requester'):
            return obj.requester == request.user
        elif hasattr(obj, 'publisher'):
            return obj.publisher == request.user
        else:
            # For User objects, check if accessing own profile
            return obj == request.user


class IsPublisherOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to allow publishers who own the content or Admin users
    """
    def has_object_permission(self, request, view, obj):
        # Admin users can access everything
        if request.user.is_admin():
            return True
        
        # Publishers can only access their own content
        if request.user.is_publisher():
            if hasattr(obj, 'publisher'):
                return obj.publisher == request.user
            elif hasattr(obj, 'resource') and hasattr(obj.resource, 'publisher'):
                return obj.resource.publisher == request.user
        
        return False


class ResourcePermission(permissions.BasePermission):
    """
    Custom permission for Resource objects based on actions and roles
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        
        action = view.action
        
        # Admin can do everything
        if request.user.is_admin():
            return True
        
        # Publishers can create, read, update their own resources
        if request.user.is_publisher():
            return action in ['list', 'retrieve', 'create', 'update', 'partial_update']
        
        # Developers and Reviewers can only read
        if request.user.is_developer() or request.user.is_reviewer():
            return action in ['list', 'retrieve']
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Admin can access everything
        if request.user.is_admin():
            return True
        
        # Publishers can only access their own resources
        if request.user.is_publisher():
            return obj.publisher == request.user
        
        # Developers and Reviewers can read any published resource
        if request.user.is_developer() or request.user.is_reviewer():
            return view.action in ['retrieve'] and obj.is_published()
        
        return False


class LicensePermission(permissions.BasePermission):
    """
    Custom permission for License objects
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        
        action = view.action
        
        # Admin can do everything
        if request.user.is_admin():
            return True
        
        # Publishers can manage licenses for their resources
        if request.user.is_publisher():
            return action in ['list', 'retrieve', 'create', 'update', 'partial_update']
        
        # Developers and Reviewers can only read
        if request.user.is_developer() or request.user.is_reviewer():
            return action in ['list', 'retrieve']
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Admin can access everything
        if request.user.is_admin():
            return True
        
        # Publishers can only access licenses for their resources
        if request.user.is_publisher():
            return obj.resource.publisher == request.user
        
        # Developers and Reviewers can read any license
        if request.user.is_developer() or request.user.is_reviewer():
            return view.action in ['retrieve']
        
        return False


class DistributionPermission(permissions.BasePermission):
    """
    Custom permission for Distribution objects
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        
        action = view.action
        
        # Admin can do everything
        if request.user.is_admin():
            return True
        
        # Publishers can manage distributions for their resources
        if request.user.is_publisher():
            return action in ['list', 'retrieve', 'create', 'update', 'partial_update']
        
        # Developers can read distributions they have access to
        if request.user.is_developer():
            return action in ['list', 'retrieve']
        
        # Reviewers can read all distributions
        if request.user.is_reviewer():
            return action in ['list', 'retrieve']
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Admin can access everything
        if request.user.is_admin():
            return True
        
        # Publishers can only access distributions for their resources
        if request.user.is_publisher():
            return obj.resource.publisher == request.user
        
        # Developers can only access distributions they have approved access to
        if request.user.is_developer():
            if view.action == 'retrieve':
                # Check if user has approved access to this distribution
                return obj.access_requests.filter(
                    requester=request.user,
                    status='approved',
                    is_active=True
                ).exists()
            return True  # For list view
        
        # Reviewers can read any distribution
        if request.user.is_reviewer():
            return view.action in ['retrieve']
        
        return False


class AccessRequestPermission(permissions.BasePermission):
    """
    Custom permission for AccessRequest objects
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        
        action = view.action
        
        # Admin can do everything
        if request.user.is_admin():
            return True
        
        # Developers can create and view their own requests
        if request.user.is_developer():
            return action in ['list', 'retrieve', 'create']
        
        # Publishers and Reviewers can view requests for their resources
        if request.user.is_publisher() or request.user.is_reviewer():
            return action in ['list', 'retrieve']
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Admin can access everything
        if request.user.is_admin():
            return True
        
        # Developers can only access their own requests
        if request.user.is_developer():
            return obj.requester == request.user
        
        # Publishers can view requests for their resources
        if request.user.is_publisher():
            return obj.distribution.resource.publisher == request.user
        
        # Reviewers can view any request
        if request.user.is_reviewer():
            return view.action in ['retrieve']
        
        return False


class UsageEventPermission(permissions.BasePermission):
    """
    Custom permission for UsageEvent objects
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        
        action = view.action
        
        # Admin can read all usage events
        if request.user.is_admin():
            return action in ['list', 'retrieve']
        
        # Publishers can read usage events for their resources
        if request.user.is_publisher():
            return action in ['list', 'retrieve']
        
        # Developers can read their own usage events
        if request.user.is_developer():
            return action in ['list', 'retrieve']
        
        # No one can create/update/delete usage events via API
        # (they should be created automatically by the system)
        return False
    
    def has_object_permission(self, request, view, obj):
        # Admin can access everything
        if request.user.is_admin():
            return True
        
        # Publishers can view usage events for their resources
        if request.user.is_publisher():
            return obj.resource.publisher == request.user
        
        # Developers can only view their own usage events
        if request.user.is_developer():
            return obj.user == request.user
        
        return False


class RolePermission(permissions.BasePermission):
    """
    Custom permission for Role objects - Admin only
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active and
            request.user.is_admin()
        )


class UserPermission(permissions.BasePermission):
    """
    Custom permission for User objects
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.is_active):
            return False
        
        action = view.action
        
        # Admin can do everything
        if request.user.is_admin():
            return True
        
        # Users can view their own profile and update it
        if action in ['retrieve', 'update', 'partial_update']:
            return True
        
        # Only Admin can list all users or create new users
        return False
    
    def has_object_permission(self, request, view, obj):
        # Admin can access everything
        if request.user.is_admin():
            return True
        
        # Users can only access their own profile
        return obj == request.user
