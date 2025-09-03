"""
Core models for the CMS application
"""

import uuid
from django.db import models
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


# User model moved to apps.accounts.models to avoid conflicts
# The User model is now defined in apps/accounts/models.py as specified in settings.AUTH_USER_MODEL


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