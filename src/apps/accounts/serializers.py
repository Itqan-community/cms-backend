"""
Serializers for user accounts and role management
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Role

def get_file_url(file_field):
    """Helper function to safely get URL from file field"""
    if file_field and hasattr(file_field, 'url'):
        return file_field.url
    return ''

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    """
    Serializer for Role model
    """
    user_count = serializers.SerializerMethodField()
    permission_categories = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description', 'permissions', 'user_count',
            'permission_categories', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user_count', 'permission_categories', 'created_at', 'updated_at']

    def get_user_count(self, obj):
        """Get number of users with this role"""
        return obj.users.filter(is_active=True).count()

    def get_permission_categories(self, obj):
        """Get list of permission categories for this role"""
        return list(obj.permissions.keys()) if obj.permissions else []

    def validate_permissions(self, value):
        """
        Validate permissions structure
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError("Permissions must be a dictionary")
        
        # Define valid permission categories and actions
        valid_categories = {
            'users', 'roles', 'resources', 'licenses', 'distributions',
            'access_requests', 'usage_events', 'system', 'workflow',
            'media', 'search', 'api'
        }
        
        valid_actions = {
            'create', 'read', 'update', 'delete', 'approve', 'reject',
            'review', 'publish', 'submit_for_review', 'manage', 'configure',
            'read_own', 'read_published', 'manage_own', 'upload', 'access',
            'generate_keys', 'accept', 'admin_panel', 'system_settings',
            'backup', 'restore', 'override', 'submit', 'draft', 'reindex',
            'read_own_content'
        }
        
        for category, actions in value.items():
            if category not in valid_categories:
                raise serializers.ValidationError(
                    f"Invalid permission category: {category}"
                )
            
            if not isinstance(actions, list):
                raise serializers.ValidationError(
                    f"Actions for {category} must be a list"
                )
            
            for action in actions:
                if action not in valid_actions:
                    raise serializers.ValidationError(
                        f"Invalid action '{action}' for category '{category}'"
                    )
        
        return value


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model
    """
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_permissions = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)
    can_access_admin = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'role_name', 'role_permissions', 'profile_data',
            'bio', 'organization', 'location', 'website', 'github_username',
            'avatar_url', 'auth_provider', 'email_verified', 'profile_completed',
            'is_active', 'last_login', 'can_access_admin', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'role_name', 'role_permissions', 'full_name',
            'can_access_admin', 'last_login', 'created_at', 'updated_at',
            'auth_provider', 'email_verified', 'profile_completed'
        ]

    def get_role_permissions(self, obj):
        """Get user's role permissions"""
        if obj.role:
            return obj.role.permissions
        return {}

    def get_can_access_admin(self, obj):
        """Check if user can access admin panel"""
        return obj.can_access_admin_panel()
    
    def get_avatar_url(self, obj):
        """Get avatar URL from file field"""
        return get_file_url(obj.avatar_url)

    def validate_email(self, value):
        """
        Validate email uniqueness
        """
        if User.objects.filter(email=value).exclude(id=self.instance.id if self.instance else None).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new users
    """
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 'role',
            'password', 'confirm_password', 'profile_data'
        ]

    def validate(self, attrs):
        """
        Validate password confirmation
        """
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        """
        Create user with encrypted password and default role
        """
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        
        # Get or create default role (Developer for new registrations)
        default_role, created = Role.objects.get_or_create(
            name='Developer',
            defaults={
                'description': 'API access for application development',
                'permissions': {
                    'resources': ['read'],
                    'distributions': ['read'],
                    'access_requests': ['create', 'read_own'],
                    'usage_events': ['read_own']
                }
            }
        )
        
        user = User(**validated_data)
        user.set_password(password)
        user.role = default_role  # Assign default role
        user.save()
        
        return user


class RolePermissionMatrixSerializer(serializers.Serializer):
    """
    Serializer for role permission matrix
    """
    matrix = serializers.DictField(
        child=serializers.DictField(
            child=serializers.ListField(child=serializers.CharField())
        )
    )
    roles = serializers.ListField(child=serializers.CharField())
    resources = serializers.ListField(child=serializers.CharField())


class RoleAssignmentSerializer(serializers.Serializer):
    """
    Serializer for role assignment operations
    """
    user_id = serializers.UUIDField()
    role_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=500, required=False)

    def validate_user_id(self, value):
        """Validate user exists"""
        try:
            User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        return value

    def validate_role_id(self, value):
        """Validate role exists"""
        try:
            Role.objects.get(id=value, is_active=True)
        except Role.DoesNotExist:
            raise serializers.ValidationError("Role not found")
        return value


class PermissionCheckSerializer(serializers.Serializer):
    """
    Serializer for checking user permissions
    """
    resource = serializers.CharField(max_length=50)
    action = serializers.CharField(max_length=50)
    user_id = serializers.UUIDField(required=False)

    def validate_resource(self, value):
        """Validate resource category"""
        valid_resources = {
            'users', 'roles', 'resources', 'licenses', 'distributions',
            'access_requests', 'usage_events', 'system', 'workflow',
            'media', 'search', 'api'
        }
        if value not in valid_resources:
            raise serializers.ValidationError(f"Invalid resource: {value}")
        return value


class UserStatsSerializer(serializers.Serializer):
    """
    Serializer for user statistics
    """
    role_distribution = serializers.DictField(child=serializers.IntegerField())
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    inactive_users = serializers.IntegerField()
    roles_count = serializers.IntegerField()


class RoleSummarySerializer(serializers.ModelSerializer):
    """
    Summary serializer for Role model (for lists)
    """
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'user_count', 'is_active']

    def get_user_count(self, obj):
        """Get number of users with this role"""
        return obj.users.filter(is_active=True).count()


class UserSummarySerializer(serializers.ModelSerializer):
    """
    Summary serializer for User model (for lists)
    """
    role_name = serializers.CharField(source='role.name', read_only=True)
    full_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'full_name', 'role_name',
            'is_active', 'last_login', 'created_at'
        ]