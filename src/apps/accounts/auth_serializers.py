"""
Serializers for authentication endpoints matching API contract
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework_simplejwt.tokens import RefreshToken

def get_file_url(file_field):
    """Helper function to safely get URL from file field"""
    if file_field and hasattr(file_field, 'url'):
        return file_field.url
    return ''

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """
    Serializer for email/password registration (API 1.1)
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    job_title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    
    # Backward compatibility alias
    title = serializers.CharField(max_length=255, required=False, allow_blank=True, write_only=True)
    
    def validate_email(self, value):
        """Check if email is already taken"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value
    
    def validate_password(self, value):
        """Validate password using Django's validators"""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value
    
    def create(self, validated_data):
        """Create new user"""
        password = validated_data.pop('password')
        
        # Handle backward compatibility: title -> job_title
        job_title = validated_data.get('job_title', '') or validated_data.get('title', '')
        validated_data.pop('title', None)  # Remove title if present
        
        # Get or create default role (Developer for new registrations)
        from .models import Role
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
        
        # Create user using standard create method and set password separately
        user = User(
            email=validated_data['email'],
            username=validated_data['email'],  # Use email as username
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone_number=validated_data.get('phone_number', ''),
            job_title=job_title,
            auth_provider='email',
            role=default_role  # Assign default role
        )
        user.set_password(password)
        user.save()
        
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for email/password login (API 1.2)
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """Authenticate user"""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            try:
                # Use direct user lookup instead of Django's authenticate
                user = User.objects.get(email=email)
                
                if not user.check_password(password):
                    raise serializers.ValidationError("Invalid email or password")
                
                if not user.is_active:
                    raise serializers.ValidationError("User account is disabled")
                    
                attrs['user'] = user
                return attrs
                
            except User.DoesNotExist:
                raise serializers.ValidationError("Invalid email or password")
        
        raise serializers.ValidationError("Email and password are required")


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile (API 1.4 & 1.5) - Updated for ERD User model
    """
    name = serializers.SerializerMethodField()
    # Backward compatibility alias
    title = serializers.CharField(source='job_title', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'first_name', 'last_name', 'phone_number', 'job_title', 'title',
            'avatar_url', 'bio', 'organization', 'location', 'website', 'github_username', 
            'email_verified', 'profile_completed', 'auth_provider', 'profile_data'
        ]
        read_only_fields = ['id', 'email', 'email_verified', 'auth_provider', 'title']
    
    def get_name(self, obj):
        """Get full name"""
        return obj.get_full_name()


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile (API 1.5) - Updated for ERD User model
    """
    name = serializers.CharField(write_only=True, required=False)
    # Backward compatibility alias
    title = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = [
            'name', 'first_name', 'last_name', 'phone_number', 'job_title', 'title',
            'bio', 'organization', 'location', 'website', 'github_username'
        ]
    
    def update(self, instance, validated_data):
        """Update user profile"""
        # Handle name field specially
        if 'name' in validated_data:
            name = validated_data.pop('name')
            name_parts = name.strip().split(' ', 1)
            instance.first_name = name_parts[0]
            instance.last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # Handle backward compatibility: title -> job_title
        if 'title' in validated_data:
            title = validated_data.pop('title')
            if not validated_data.get('job_title'):
                validated_data['job_title'] = title
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update profile completion status if method exists
        if hasattr(instance, 'update_profile_completion_status'):
            instance.update_profile_completion_status()
        
        return instance


class TokenRefreshResponseSerializer(serializers.Serializer):
    """
    Serializer for token refresh response (API 1.6)
    """
    access_token = serializers.CharField()


class AuthResponseSerializer(serializers.Serializer):
    """
    Serializer for authentication response (APIs 1.1, 1.2, 1.3)
    """
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserProfileSerializer()


class ErrorResponseSerializer(serializers.Serializer):
    """
    Serializer for error responses
    """
    error = serializers.DictField(
        child=serializers.CharField()
    )


def create_auth_response(user):
    """
    Create authentication response with tokens and user data - Updated for ERD User model
    """
    refresh = RefreshToken.for_user(user)
    
    return {
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
        'user': {
            'id': user.id,
            'email': user.email,
            'name': user.get_full_name(),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
            'job_title': user.job_title,
            'title': user.job_title,  # Backward compatibility alias
            'avatar_url': get_file_url(user.avatar_url),
            'bio': user.bio,
            'organization': user.organization,
            'location': user.location,
            'website': user.website,
            'github_username': user.github_username,
            'auth_provider': user.auth_provider,
            'email_verified': user.email_verified,
            'profile_completed': user.profile_completed
        }
    }


def create_error_response(code, message):
    """
    Create error response matching API contract format
    """
    return {
        'error': {
            'code': code,
            'message': message
        }
    }
