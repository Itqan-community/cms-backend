
from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions
from .models import Resource, Distribution, Asset

@register(Resource)
class ResourceTranslationOptions(TranslationOptions):
    """Translation configuration for Resource model"""
    fields = (
        'name',           # Main resource name (was title)
        'description',    # Resource description
    )
    # Don't translate: category, status, slug, publisher, default_license
    # These are technical/structural fields that shouldn't vary by language

@register(Asset)
class AssetTranslationOptions(TranslationOptions):
    """Translation configuration for Asset model"""
    fields = (
        'name',          # Display name for API
        'description',    # Asset description
        'long_description',  # Extended description
    )
    # Don't translate: name, category, format, version, language, file_size, etc.

@register(Distribution)
class DistributionTranslationOptions(TranslationOptions):
    """Translation configuration for Distribution model"""
    fields = (
        # No fields need translation - Distribution is technical configuration
        # endpoint_url, format_type, version, access_config are technical
        # We could add description field in future if needed for UI
    )
    empty = True  # Explicitly mark as having no translatable fields for now
