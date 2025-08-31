"""
Core models for the CMS application
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager
from django.utils import timezone


class BaseModel(models.Model):
    """
    Abstract base model with common fields
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class UserManager(BaseUserManager):
    """
    Custom user manager
    """
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    Custom user model
    """
    
    AUTH_PROVIDER_CHOICES = [
        ('auth0', 'Auth0'),
        ('github', 'GitHub'),
        ('google', 'Google'),
        ('email', 'Email'),
    ]
    
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    # Auth provider information
    auth_provider = models.CharField(
        max_length=20, 
        choices=AUTH_PROVIDER_CHOICES, 
        default='email'
    )
    auth_provider_id = models.CharField(max_length=255, blank=True)
    
    # User status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    
    # Profile information
    avatar_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    website_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    
    # Additional profile fields for Auth0 integration
    job_title = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    business_model = models.TextField(blank=True)
    team_size = models.CharField(max_length=50, blank=True)
    about_yourself = models.TextField(blank=True)
    
    # Localization
    preferred_language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='UTC')
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        db_table = 'core_users'
    
    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def profile_completed(self):
        """Check if user has completed their profile"""
        return bool(
            self.first_name and 
            self.last_name and
            self.job_title and
            self.phone_number and
            self.business_model and
            self.team_size and
            self.about_yourself
        )


class License(BaseModel):
    """
    License model for resources
    """
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    url = models.URLField(help_text='URL to the full license text')
    summary = models.TextField(help_text='Human-readable summary of the license')
    full_text = models.TextField(blank=True, help_text='Full legal text of the license')
    
    # License permissions
    allows_commercial_use = models.BooleanField(default=True)
    allows_modification = models.BooleanField(default=True)
    allows_distribution = models.BooleanField(default=True)
    requires_attribution = models.BooleanField(default=False)
    requires_share_alike = models.BooleanField(default=False)
    
    # License metadata
    version = models.CharField(max_length=10, blank=True)
    publisher = models.CharField(max_length=100, blank=True)
    published_date = models.DateField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'License'
        verbose_name_plural = 'Licenses'
        db_table = 'core_licenses'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Role(BaseModel):
    """
    Role model for organization permissions
    """
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('manager', 'Manager'),
        ('auditor', 'Auditor'),
        ('contributor', 'Contributor'),
    ]
    
    code = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Permissions
    can_create_resources = models.BooleanField(default=False)
    can_edit_resources = models.BooleanField(default=False)
    can_delete_resources = models.BooleanField(default=False)
    can_manage_members = models.BooleanField(default=False)
    can_manage_organization = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        db_table = 'core_roles'
    
    def __str__(self):
        return self.name