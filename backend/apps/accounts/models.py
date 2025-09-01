"""
User accounts and role management models for Itqan CMS
"""
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import EmailValidator
from apps.core.models import BaseModel, ActiveObjectsManager, AllObjectsManager


class Role(BaseModel):
    """
    Role model defining user roles in the Itqan CMS system.
    Supports Admin, Publisher, Developer, and Reviewer roles.
    """
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Publisher', 'Publisher'),
        ('Developer', 'Developer'),
        ('Reviewer', 'Reviewer'),
    ]
    
    name = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        unique=True,
        help_text="Role name (Admin, Publisher, Developer, Reviewer)"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the role and its responsibilities"
    )
    
    permissions = models.JSONField(
        default=dict,
        help_text="Role-specific permissions as JSON object"
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'role'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def get_default_permissions(cls, role_name):
        """
        Get default permissions for a specific role
        """
        default_permissions = {
            'Admin': {
                'users': ['create', 'read', 'update', 'delete'],
                'roles': ['create', 'read', 'update', 'delete'],
                'resources': ['create', 'read', 'update', 'delete'],
                'licenses': ['create', 'read', 'update', 'delete'],
                'distributions': ['create', 'read', 'update', 'delete'],
                'access_requests': ['read', 'update', 'approve', 'reject'],
                'usage_events': ['read'],
                'system': ['admin_panel', 'system_settings'],
            },
            'Publisher': {
                'resources': ['create', 'read', 'update'],
                'licenses': ['create', 'read', 'update'],
                'distributions': ['create', 'read', 'update'],
                'usage_events': ['read_own'],
            },
            'Developer': {
                'resources': ['read'],
                'distributions': ['read'],
                'access_requests': ['create', 'read_own'],
                'usage_events': ['read_own'],
            },
            'Reviewer': {
                'resources': ['read', 'review', 'approve'],
                'licenses': ['read', 'review'],
                'distributions': ['read'],
            }
        }
        return default_permissions.get(role_name, {})


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser with Auth0 integration
    and role-based access control for the Itqan CMS.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this user"
    )
    
    auth0_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Auth0 subject identifier (sub claim from JWT)"
    )
    
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        help_text="User's email address (must be unique)"
    )
    
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='users',
        help_text="User's role in the system"
    )
    
    profile_data = models.JSONField(
        default=dict,
        help_text="Additional user profile data and preferences"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this user account is active"
    )
    
    last_login = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of user's last login"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this user was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this user was last updated"
    )

    # Use email as the unique identifier for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def get_full_name(self):
        """
        Return the user's full name
        """
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def get_short_name(self):
        """
        Return the user's short name (first name)
        """
        return self.first_name or self.username
    
    def is_admin(self):
        """Check if user has Admin role"""
        return self.role and self.role.name == 'Admin'
    
    def is_publisher(self):
        """Check if user has Publisher role"""
        return self.role and self.role.name == 'Publisher'
    
    def is_developer(self):
        """Check if user has Developer role"""
        return self.role and self.role.name == 'Developer'
    
    def is_reviewer(self):
        """Check if user has Reviewer role"""
        return self.role and self.role.name == 'Reviewer'
    
    def get_auth0_roles(self):
        """Get Auth0 role names from Django role"""
        if not self.role:
            return []
        
        # Reverse mapping from Django role to Auth0 role
        try:
            from django.conf import settings
            role_mapping = settings.AUTH0_ROLE_MAPPING
            
            for auth0_role, django_role in role_mapping.items():
                if django_role == self.role.name:
                    return [auth0_role]
        except:
            pass  # Settings not available during migrations
        
        return []

    def has_permission(self, resource, action):
        """
        Check if user has a specific permission
        """
        if not self.role:
            return False
        
        permissions = self.role.permissions
        resource_permissions = permissions.get(resource, [])
        
        return action in resource_permissions

    def can_manage_users(self):
        """Check if user can manage other users"""
        return self.has_permission('users', 'create') or self.is_admin()

    def can_access_admin_panel(self):
        """Check if user can access Django admin panel"""
        return self.has_permission('system', 'admin_panel') or self.is_admin()

    def can_manage_system_settings(self):
        """Check if user can modify system settings"""
        return self.has_permission('system', 'system_settings') or self.is_admin()

    def can_create_content(self):
        """Check if user can create content (Resources, Licenses)"""
        return (self.has_permission('resources', 'create') or 
                self.has_permission('licenses', 'create') or 
                self.is_admin())

    def can_review_content(self):
        """Check if user can review and approve content"""
        return (self.has_permission('resources', 'review') or 
                self.has_permission('resources', 'approve') or 
                self.is_reviewer() or self.is_admin())

    def can_access_api(self):
        """Check if user can access the API"""
        return self.is_developer() or self.is_admin()

    def get_accessible_resources(self):
        """Get queryset of resources user can access"""
        from apps.content.models import Resource
        
        if self.is_admin():
            return Resource.objects.all()
        elif self.is_publisher():
            return Resource.objects.filter(publisher=self)
        elif self.is_reviewer():
            return Resource.objects.all()  # Reviewers can see all for review
        elif self.is_developer():
            return Resource.objects.filter(is_published=True)  # Only published content
        else:
            return Resource.objects.none()

    def get_auth0_metadata(self):
        """
        Get Auth0-specific metadata from profile_data
        """
        return self.profile_data.get('auth0_metadata', {})

    def update_from_auth0(self, auth0_user_data):
        """
        Update user fields from Auth0 user data
        """
        if 'email' in auth0_user_data:
            self.email = auth0_user_data['email']
        
        if 'given_name' in auth0_user_data:
            self.first_name = auth0_user_data['given_name']
        
        if 'family_name' in auth0_user_data:
            self.last_name = auth0_user_data['family_name']
        
        if 'nickname' in auth0_user_data and not self.username:
            self.username = auth0_user_data['nickname']
        
        # Store additional Auth0 metadata
        auth0_metadata = {
            'picture': auth0_user_data.get('picture'),
            'locale': auth0_user_data.get('locale'),
            'updated_at': auth0_user_data.get('updated_at'),
        }
        
        if not self.profile_data:
            self.profile_data = {}
        
        self.profile_data['auth0_metadata'] = auth0_metadata
        self.save()

    def delete(self, using=None, keep_parents=False):
        """
        Soft delete: Mark as inactive instead of actually deleting
        """
        self.is_active = False
        self.save(using=using)

    def hard_delete(self, using=None, keep_parents=False):
        """
        Hard delete: Actually remove from database (use with caution)
        """
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """
        Restore a soft-deleted user
        """
        self.is_active = True
        self.save()


