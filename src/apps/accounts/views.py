"""
API views for user accounts and role management
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from .models import Role, User
from .serializers import RoleSerializer, UserSerializer, RolePermissionMatrixSerializer
from .permissions import (
    IsAdminUser, IsAdminOrOwner, ContentManagementPermission,
    AccessRequestPermission
)

User = get_user_model()


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing roles and permissions
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'id'

    @extend_schema(
        summary="Get role permission matrix",
        description="Returns a comprehensive matrix of all roles and their permissions",
        responses={200: RolePermissionMatrixSerializer}
    )
    @action(detail=False, methods=['get'])
    def permission_matrix(self, request):
        """
        Get complete permission matrix for all roles
        """
        roles = Role.objects.filter(is_active=True)
        
        # Build permission matrix
        matrix = {}
        all_permissions = set()
        
        for role in roles:
            matrix[role.name] = role.permissions
            for resource, actions in role.permissions.items():
                all_permissions.add(resource)
        
        # Normalize permissions for consistent display
        normalized_matrix = {}
        for role in roles:
            normalized_matrix[role.name] = {}
            for resource in sorted(all_permissions):
                normalized_matrix[role.name][resource] = role.permissions.get(resource, [])
        
        serializer = RolePermissionMatrixSerializer(data={
            'matrix': normalized_matrix,
            'roles': [role.name for role in roles],
            'resources': sorted(all_permissions)
        })
        serializer.is_valid()
        
        return Response(serializer.data)

    @extend_schema(
        summary="Update role permissions",
        description="Update permissions for a specific role",
        request=RoleSerializer,
        responses={200: RoleSerializer}
    )
    @action(detail=True, methods=['patch'])
    def update_permissions(self, request, id=None):
        """
        Update permissions for a specific role
        """
        role = self.get_object()
        
        permissions_data = request.data.get('permissions', {})
        
        # Validate permissions structure
        if not isinstance(permissions_data, dict):
            return Response(
                {'error': 'Permissions must be a dictionary'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update permissions
        role.permissions = permissions_data
        role.save()
        
        # Log the change
        self.log_permission_change(request.user, role, permissions_data)
        
        serializer = self.get_serializer(role)
        return Response(serializer.data)

    @extend_schema(
        summary="Reset role to default permissions",
        description="Reset a role to its default permission set",
        responses={200: RoleSerializer}
    )
    @action(detail=True, methods=['post'])
    def reset_to_default(self, request, id=None):
        """
        Reset role to default permissions
        """
        role = self.get_object()
        
        default_permissions = Role.get_default_permissions(role.name)
        if not default_permissions:
            return Response(
                {'error': f'No default permissions defined for role: {role.name}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        role.permissions = default_permissions
        role.save()
        
        # Log the change
        self.log_permission_change(request.user, role, default_permissions, action='reset')
        
        serializer = self.get_serializer(role)
        return Response(serializer.data)

    def log_permission_change(self, user, role, permissions, action='update'):
        """
        Log permission changes for audit trail
        """
        # This could be enhanced to use a proper audit log model
        import logging
        logger = logging.getLogger('itqan.role_management')
        
        logger.info(
            f'Role permissions {action} - User: {user.email}, Role: {role.name}, '
            f'Permissions: {len(permissions)} categories'
        )


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrOwner]
    lookup_field = 'id'

    def get_queryset(self):
        """
        Filter users based on requesting user's role
        """
        user = self.request.user
        
        if user.is_admin():
            return User.objects.all()
        else:
            # Non-admin users can only see their own profile
            return User.objects.filter(id=user.id)

    @extend_schema(
        summary="Get user roles statistics",
        description="Returns statistics about user distribution across roles",
        responses={200: {'type': 'object'}}
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def role_statistics(self, request):
        """
        Get user role distribution statistics
        """
        from django.db.models import Count
        
        stats = {}
        
        # Count users by role
        role_counts = User.objects.values('role__name').annotate(
            count=Count('id')
        ).order_by('role__name')
        
        for item in role_counts:
            role_name = item['role__name'] or 'No Role'
            stats[role_name] = item['count']
        
        # Get additional statistics
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        inactive_users = total_users - active_users
        
        return Response({
            'role_distribution': stats,
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': inactive_users,
            'roles_count': Role.objects.filter(is_active=True).count()
        })

    @extend_schema(
        summary="Change user role",
        description="Change a user's role (Admin only)",
        request={'type': 'object', 'properties': {'role_id': {'type': 'string'}}},
        responses={200: UserSerializer}
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAdminUser])
    def change_role(self, request, id=None):
        """
        Change a user's role
        """
        user = self.get_object()
        role_id = request.data.get('role_id')
        
        if not role_id:
            return Response(
                {'error': 'role_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_role = Role.objects.get(id=role_id, is_active=True)
        except Role.DoesNotExist:
            return Response(
                {'error': 'Invalid role_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_role = user.role
        user.role = new_role
        user.save()
        
        # Log the role change
        import logging
        logger = logging.getLogger('itqan.role_management')
        logger.info(
            f'User role changed - Admin: {request.user.email}, User: {user.email}, '
            f'From: {old_role.name if old_role else "None"}, To: {new_role.name}'
        )
        
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @extend_schema(
        summary="Get current user profile",
        description="Returns the current authenticated user's profile and permissions",
        responses={200: UserSerializer}
    )
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get current user profile
        """
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)