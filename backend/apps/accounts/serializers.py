"""
Serializers for User and Role models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Role

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    """
    Serializer for Role model with permission management
    """
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description', 'permissions', 
            'is_active', 'user_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_count']
    
    def get_user_count(self, obj):
        """Get count of active users with this role"""
        return obj.users.filter(is_active=True).count()
    
    def validate_name(self, value):
        """Validate role name is one of the allowed choices"""
        valid_roles = ['Admin', 'Publisher', 'Developer', 'Reviewer']
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"Role name must be one of: {', '.join(valid_roles)}"
            )
        return value
    
    def validate_permissions(self, value):
        """Validate permissions structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Permissions must be a JSON object")
        
        # Validate permission structure (basic validation)
        valid_resources = ['users', 'roles', 'resources', 'licenses', 'distributions', 
                          'access_requests', 'usage_events', 'system']
        valid_actions = ['create', 'read', 'update', 'delete', 'approve', 'reject', 
                        'read_own', 'admin_panel', 'system_settings', 'review']
        
        for resource, actions in value.items():
            if resource not in valid_resources:
                raise serializers.ValidationError(
                    f"Invalid resource '{resource}'. Valid resources: {', '.join(valid_resources)}"
                )
            
            if not isinstance(actions, list):
                raise serializers.ValidationError(
                    f"Actions for '{resource}' must be a list"
                )
            
            for action in actions:
                if action not in valid_actions:
                    raise serializers.ValidationError(
                        f"Invalid action '{action}' for resource '{resource}'. "
                        f"Valid actions: {', '.join(valid_actions)}"
                    )
        
        return value


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with role information
    """
    role_name = serializers.CharField(source='role.name', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    auth0_status = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 
            'full_name', 'role', 'role_name', 'auth0_id', 'auth0_status',
            'profile_data', 'is_active', 'is_staff', 'is_superuser',
            'last_login', 'date_joined', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'auth0_id', 'last_login', 'date_joined', 
            'created_at', 'updated_at', 'full_name', 'role_name', 'auth0_status'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'profile_data': {'required': False},
        }
    
    def get_auth0_status(self, obj):
        """Get Auth0 integration status"""
        return 'connected' if obj.auth0_id else 'not_connected'
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if self.instance and self.instance.email == value:
            return value
        
        if User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("A user with this email already exists")
        
        return value
    
    def validate_role(self, value):
        """Validate role exists and is active"""
        if not value or not value.is_active:
            raise serializers.ValidationError("Role must be active")
        return value
    
    def validate_profile_data(self, value):
        """Validate profile data structure"""
        if value and not isinstance(value, dict):
            raise serializers.ValidationError("Profile data must be a JSON object")
        return value or {}


class UserCreateSerializer(UserSerializer):
    """
    Serializer for creating new users with password
    """
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['password', 'password_confirm']
    
    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError("Passwords do not match")
        
        attrs.pop('password_confirm', None)
        return attrs
    
    def create(self, validated_data):
        """Create user with hashed password"""
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserUpdateSerializer(UserSerializer):
    """
    Serializer for updating existing users (without password)
    """
    class Meta(UserSerializer.Meta):
        fields = [field for field in UserSerializer.Meta.fields if field != 'password']


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for user profile information
    """
    role_name = serializers.CharField(source='role.name', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 
            'full_name', 'role_name', 'permissions', 'profile_data',
            'last_login', 'date_joined'
        ]
        read_only_fields = [
            'id', 'email', 'role_name', 'permissions', 
            'last_login', 'date_joined', 'full_name'
        ]
    
    def get_permissions(self, obj):
        """Get user's role permissions"""
        return obj.role.permissions if obj.role else {}


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for changing user password
    """
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True)
    
    def validate_current_password(self, value):
        """Validate current password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        return value
    
    def validate(self, attrs):
        """Validate new password confirmation"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords do not match")
        return attrs
    
    def save(self):
        """Update user password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
