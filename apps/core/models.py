"""
Core models and base classes for Itqan CMS
"""

from django.db import models


class BaseModel(models.Model):
    """
    Abstract base model providing common functionality for all Itqan CMS models:
    - Integer primary key
    - Timestamp tracking (created_at, updated_at)
    - Soft delete functionality (is_active)
    """

    id = models.AutoField(
        primary_key=True,
        help_text="Unique identifier for this record",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this record was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this record was last updated",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this record is active (soft delete mechanism)",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.__class__.__name__}({self.id})"

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
        Restore a soft-deleted record
        """
        self.is_active = True
        self.save()


class ActiveObjectsManager(models.Manager):
    """
    Manager that returns only active (non-soft-deleted) objects by default
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class AllObjectsManager(models.Manager):
    """
    Manager that returns all objects including soft-deleted ones
    """

    # Uses default behavior
