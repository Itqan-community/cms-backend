"""
Serializers for search document formatting
"""
from rest_framework import serializers
from apps.content.models import Resource


class ResourceSearchSerializer(serializers.ModelSerializer):
    """
    Serializer for converting Resource models to MeiliSearch documents
    """
    publisher_name = serializers.CharField(source='publisher.get_full_name', read_only=True)
    publisher_email = serializers.CharField(source='publisher.email', read_only=True)
    publisher_id = serializers.UUIDField(source='publisher.id', read_only=True)
    language_display = serializers.CharField(source='get_language_display', read_only=True)
    is_published = serializers.SerializerMethodField()
    
    # Timestamps as Unix timestamps for MeiliSearch sorting
    created_at_timestamp = serializers.SerializerMethodField()
    updated_at_timestamp = serializers.SerializerMethodField()
    published_at_timestamp = serializers.SerializerMethodField()
    
    # Search-optimized fields
    search_content = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    
    class Meta:
        model = Resource
        fields = [
            'id',
            'title',
            'description', 
            'resource_type',
            'language',
            'language_display',
            'version',
            'checksum',
            'publisher_id',
            'publisher_name',
            'publisher_email',
            'metadata',
            'is_published',
            'is_active',
            'created_at',
            'updated_at',
            'published_at',
            'created_at_timestamp',
            'updated_at_timestamp',
            'published_at_timestamp',
            'search_content',
            'tags',
        ]
    
    def get_is_published(self, obj):
        """Check if resource is published"""
        return obj.published_at is not None
    
    def get_created_at_timestamp(self, obj):
        """Convert created_at to Unix timestamp"""
        return int(obj.created_at.timestamp()) if obj.created_at else None
    
    def get_updated_at_timestamp(self, obj):
        """Convert updated_at to Unix timestamp"""
        return int(obj.updated_at.timestamp()) if obj.updated_at else None
    
    def get_published_at_timestamp(self, obj):
        """Convert published_at to Unix timestamp"""
        return int(obj.published_at.timestamp()) if obj.published_at else None
    
    def get_search_content(self, obj):
        """
        Combine multiple fields for better full-text search
        """
        content_parts = [
            obj.title,
            obj.description,
            obj.publisher.get_full_name() if obj.publisher else '',
            obj.get_language_display(),
            obj.resource_type,
        ]
        
        # Add metadata content if it contains searchable text
        if obj.metadata:
            if isinstance(obj.metadata, dict):
                for key, value in obj.metadata.items():
                    if isinstance(value, str) and len(value) > 2:
                        content_parts.append(value)
        
        return ' '.join(filter(None, content_parts))
    
    def get_tags(self, obj):
        """
        Generate searchable tags based on content
        """
        tags = [
            obj.resource_type,
            obj.language,
            obj.get_language_display(),
        ]
        
        # Add publisher-based tags
        if obj.publisher:
            tags.extend([
                f"publisher:{obj.publisher.email}",
                f"publisher_name:{obj.publisher.get_full_name()}",
            ])
        
        # Add metadata-based tags
        if obj.metadata and isinstance(obj.metadata, dict):
            for key, value in obj.metadata.items():
                if isinstance(value, str) and len(value) < 50:
                    tags.append(f"{key}:{value}")
                elif isinstance(value, (int, float, bool)):
                    tags.append(f"{key}:{value}")
        
        # Add status tags
        if obj.published_at:
            tags.append("status:published")
        else:
            tags.append("status:draft")
        
        if obj.is_active:
            tags.append("status:active")
        else:
            tags.append("status:inactive")
        
        return list(set(filter(None, tags)))  # Remove duplicates and empty values


class SearchResultSerializer(serializers.Serializer):
    """
    Serializer for formatting search results from MeiliSearch
    """
    hits = serializers.ListField(
        child=serializers.DictField(),
        help_text="Search result documents"
    )
    
    query = serializers.CharField(
        help_text="Original search query"
    )
    
    processing_time_ms = serializers.IntegerField(
        help_text="Time taken to process the search"
    )
    
    hits_count = serializers.IntegerField(
        source='estimatedTotalHits',
        help_text="Estimated total number of matching documents"
    )
    
    offset = serializers.IntegerField(
        default=0,
        help_text="Offset of the first result"
    )
    
    limit = serializers.IntegerField(
        default=20,
        help_text="Maximum number of results returned"
    )
    
    facet_distribution = serializers.DictField(
        required=False,
        help_text="Facet counts for filterable attributes"
    )


class SearchRequestSerializer(serializers.Serializer):
    """
    Serializer for validating search requests
    """
    q = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Search query string"
    )
    
    offset = serializers.IntegerField(
        default=0,
        min_value=0,
        max_value=10000,
        help_text="Number of results to skip"
    )
    
    limit = serializers.IntegerField(
        default=20,
        min_value=1,
        max_value=100,
        help_text="Maximum number of results to return"
    )
    
    filter = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Filter expression (e.g., 'resource_type = text')"
    )
    
    sort = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Sort criteria (e.g., ['published_at:desc'])"
    )
    
    facets = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Attributes to return facet counts for"
    )
    
    attributes_to_retrieve = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Specific attributes to retrieve from documents"
    )
    
    attributes_to_highlight = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Attributes to highlight in search results"
    )
    
    highlight_pre_tag = serializers.CharField(
        default='<mark>',
        help_text="HTML tag to insert before highlighted terms"
    )
    
    highlight_post_tag = serializers.CharField(
        default='</mark>',
        help_text="HTML tag to insert after highlighted terms"
    )
    
    def validate_filter(self, value):
        """Validate filter expression syntax"""
        if not value:
            return value
        
        # Basic validation for allowed filter attributes
        allowed_attributes = [
            'resource_type',
            'language', 
            'publisher_id',
            'is_active',
            'is_published'
        ]
        
        # Simple check that filter contains allowed attributes
        # Note: In production, you'd want more sophisticated filter validation
        for attr in allowed_attributes:
            if attr in value:
                return value
        
        # If no recognized attributes found, check if it's a simple expression
        if any(op in value for op in ['=', '!=', '>', '<', 'IN', 'TO']):
            return value
        
        raise serializers.ValidationError(
            f"Filter must use allowed attributes: {', '.join(allowed_attributes)}"
        )
    
    def validate_sort(self, value):
        """Validate sort criteria"""
        if not value:
            return value
        
        allowed_sort_fields = [
            'created_at',
            'updated_at', 
            'published_at',
            'title',
            'created_at_timestamp',
            'updated_at_timestamp',
            'published_at_timestamp',
        ]
        
        for sort_expr in value:
            # Extract field name (remove :asc or :desc)
            field = sort_expr.split(':')[0]
            if field not in allowed_sort_fields:
                raise serializers.ValidationError(
                    f"Invalid sort field '{field}'. Allowed: {', '.join(allowed_sort_fields)}"
                )
        
        return value
