"""
Search Configuration Models for Itqan CMS
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel

User = get_user_model()


class SearchIndex(BaseModel):
    """
    Configuration model for MeiliSearch indexes
    """
    name = models.CharField(max_length=100, unique=True, help_text="Index name in MeiliSearch")
    display_name = models.CharField(max_length=200, help_text="Human-readable index name")
    description = models.TextField(blank=True, help_text="Description of this search index")
    
    # Index configuration
    primary_key = models.CharField(max_length=50, default='id', help_text="Primary key field name")
    searchable_attributes = models.JSONField(
        default=list, 
        help_text="List of attributes that can be searched"
    )
    filterable_attributes = models.JSONField(
        default=list,
        help_text="List of attributes that can be used for filtering"
    )
    sortable_attributes = models.JSONField(
        default=list,
        help_text="List of attributes that can be used for sorting"
    )
    ranking_rules = models.JSONField(
        default=list,
        help_text="Custom ranking rules for search results"
    )
    
    # Index status
    is_active = models.BooleanField(default=True, help_text="Whether this index is active")
    last_indexed = models.DateTimeField(null=True, blank=True, help_text="Last time this index was updated")
    document_count = models.PositiveIntegerField(default=0, help_text="Number of documents in the index")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_indexes')
    
    class Meta:
        db_table = 'search_indexes'
        ordering = ['name']
        verbose_name = 'Search Index'
        verbose_name_plural = 'Search Indexes'
    
    def __str__(self):
        return f"{self.display_name} ({self.name})"


class SearchConfiguration(BaseModel):
    """
    Global search configuration settings
    """
    # Search behavior settings
    default_limit = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Default number of search results to return"
    )
    max_limit = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Maximum number of search results allowed per request"
    )
    
    # Auto-suggestion settings
    suggestions_enabled = models.BooleanField(default=True, help_text="Enable search suggestions")
    suggestion_min_chars = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Minimum characters required for suggestions"
    )
    suggestion_limit = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Maximum number of suggestions to return"
    )
    
    # Search features
    highlighting_enabled = models.BooleanField(default=True, help_text="Enable search result highlighting")
    highlight_pre_tag = models.CharField(max_length=20, default='<mark>', help_text="HTML tag to start highlighting")
    highlight_post_tag = models.CharField(max_length=20, default='</mark>', help_text="HTML tag to end highlighting")
    
    faceting_enabled = models.BooleanField(default=True, help_text="Enable search faceting")
    
    # Performance settings
    search_timeout = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(300)],
        help_text="Search timeout in seconds"
    )
    
    # Analytics
    track_searches = models.BooleanField(default=True, help_text="Track search queries for analytics")
    
    # Metadata
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_search_configs')
    
    class Meta:
        db_table = 'search_configuration'
        verbose_name = 'Search Configuration'
        verbose_name_plural = 'Search Configuration'
    
    def __str__(self):
        return f"Search Configuration (updated {self.updated_at.strftime('%Y-%m-%d')})"
    
    @classmethod
    def get_current(cls):
        """Get the current search configuration"""
        return cls.objects.first()


class SearchQuery(BaseModel):
    """
    Track search queries for analytics and improvement
    """
    query = models.CharField(max_length=500, help_text="The search query")
    index_name = models.CharField(max_length=100, help_text="Index that was searched")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='search_queries')
    
    # Search parameters
    filters_used = models.JSONField(default=dict, blank=True, help_text="Filters applied to the search")
    sort_criteria = models.CharField(max_length=200, blank=True, help_text="Sort criteria used")
    
    # Results metadata
    results_count = models.PositiveIntegerField(default=0, help_text="Number of results returned")
    processing_time = models.FloatField(null=True, blank=True, help_text="Search processing time in milliseconds")
    
    # User interaction
    clicked_result_id = models.CharField(max_length=100, blank=True, help_text="ID of result that was clicked")
    session_id = models.CharField(max_length=100, blank=True, help_text="User session identifier")
    
    class Meta:
        db_table = 'search_queries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['query']),
            models.Index(fields=['index_name']),
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Search Query'
        verbose_name_plural = 'Search Queries'
    
    def __str__(self):
        return f"'{self.query}' ({self.results_count} results)"


class IndexingTask(BaseModel):
    """
    Track indexing operations and their status
    """
    TASK_TYPES = [
        ('full_rebuild', 'Full Index Rebuild'),
        ('incremental', 'Incremental Update'),
        ('bulk_import', 'Bulk Import'),
        ('single_document', 'Single Document Update'),
        ('delete_document', 'Delete Document'),
        ('clear_index', 'Clear Index'),
    ]
    
    TASK_STATUS = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    task_id = models.CharField(max_length=100, unique=True, help_text="Celery task ID")
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, help_text="Type of indexing task")
    status = models.CharField(max_length=20, choices=TASK_STATUS, default='pending', help_text="Current task status")
    
    # Task details
    index_name = models.CharField(max_length=100, help_text="Target index name")
    document_ids = models.JSONField(default=list, blank=True, help_text="List of document IDs to process")
    batch_size = models.PositiveIntegerField(null=True, blank=True, help_text="Batch size for processing")
    
    # Progress tracking
    total_documents = models.PositiveIntegerField(default=0, help_text="Total number of documents to process")
    processed_documents = models.PositiveIntegerField(default=0, help_text="Number of documents processed")
    
    # Results
    error_message = models.TextField(blank=True, help_text="Error message if task failed")
    execution_time = models.FloatField(null=True, blank=True, help_text="Task execution time in seconds")
    
    # Metadata
    started_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='started_indexing_tasks')
    started_at = models.DateTimeField(null=True, blank=True, help_text="When the task actually started")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When the task completed")
    
    class Meta:
        db_table = 'indexing_tasks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task_id']),
            models.Index(fields=['status']),
            models.Index(fields=['index_name']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Indexing Task'
        verbose_name_plural = 'Indexing Tasks'
    
    def __str__(self):
        return f"{self.get_task_type_display()} - {self.get_status_display()}"
    
    @property
    def progress_percentage(self):
        """Calculate completion percentage"""
        if self.total_documents == 0:
            return 0
        return min(100, (self.processed_documents / self.total_documents) * 100)