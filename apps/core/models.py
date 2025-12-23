from django.db import models


class BaseModel(models.Model):
    """
    Abstract base model providing common functionality for all Itqan CMS models:
    - Integer primary key
    - Timestamp tracking (created_at, updated_at)
    """

    id = models.AutoField(primary_key=True, help_text="Unique identifier for this record")

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when this record was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when this record was last updated"
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.__class__.__name__}({self.id})"
