"""
User accounts and role management models for Itqan CMS
"""
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import EmailValidator
from django.contrib.auth.models import UserManager
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
    Custom User model extending Django's AbstractUser with django-allauth integration
    and role-based access control for the Itqan CMS.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this user"
    )
    
    # Using django-allauth for authentication
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether the user's email has been verified"
    )
    
    profile_completed = models.BooleanField(
        default=False,
        help_text="Whether the user has completed their profile setup"
    )
    
    # Additional profile fields to match API contract
    bio = models.TextField(
        blank=True,
        help_text="User's biography"
    )
    
    organization = models.CharField(
        max_length=255,
        blank=True,
        help_text="User's organization"
    )
    
    location = models.CharField(
        max_length=255,
        blank=True,
        help_text="User's location"
    )
    
    website = models.URLField(
        blank=True,
        help_text="User's website URL"
    )
    
    github_username = models.CharField(
        max_length=255,
        blank=True,
        help_text="User's GitHub username"
    )
    
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="User's phone number"
    )
    
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="User's professional title"
    )
    
    avatar_url = models.URLField(
        blank=True,
        help_text="User's avatar image URL"
    )
    
    auth_provider = models.CharField(
        max_length=50,
        default='email',
        choices=[
            ('email', 'Email/Password'),
            ('google', 'Google'),
            ('github', 'GitHub'),
        ],
        help_text="Authentication provider used for this account"
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

    # Managers - explicitly set Django's UserManager for authentication
    objects = UserManager()  # Provides create_user, create_superuser methods
    active_objects = ActiveObjectsManager()  # Custom manager for active objects
    all_objects = AllObjectsManager()  # Manager for all objects including inactive

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
    
    def save(self, *args, **kwargs):
        """Override save to set default role if none assigned"""
        if not self.role_id:
            # Set default role to Developer
            try:
                default_role = Role.objects.get(name='Developer')
                self.role = default_role
            except Role.DoesNotExist:
                pass  # Handle in migrations or fixtures
        super().save(*args, **kwargs)

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

    def update_profile_completion_status(self):
        """Check and update profile completion status"""
        required_fields = [
            self.first_name, self.last_name, self.bio, 
            self.organization, self.location
        ]
        self.profile_completed = all(field.strip() for field in required_fields if field)
        self.save(update_fields=['profile_completed'])

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


