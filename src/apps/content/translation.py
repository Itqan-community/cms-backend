"""
Content model translations for Itqan CMS
Configures django-modeltranslation for English/Arabic bilingual support
"""
from modeltranslation.translator import translator, TranslationOptions
from .models import Resource, Distribution, Asset


class ResourceTranslationOptions(TranslationOptions):
    """Translation configuration for Resource model"""
    fields = (
        'name',           # Main resource name (was title)
        'description',    # Resource description
    )
    # Don't translate: category, status, slug, publishing_organization, default_license
    # These are technical/structural fields that shouldn't vary by language


class AssetTranslationOptions(TranslationOptions):
    """Translation configuration for Asset model"""
    fields = (
        'name',          # Display name for API
        'description',    # Asset description
        'long_description',  # Extended description
    )
    # Don't translate: name, category, format, version, language, file_size, etc.


class DistributionTranslationOptions(TranslationOptions):
    """Translation configuration for Distribution model"""
    fields = (
        # No fields need translation - Distribution is technical configuration
        # endpoint_url, format_type, version, access_config are technical
        # We could add description field in future if needed for UI
    )
    empty = True  # Explicitly mark as having no translatable fields for now



# Register translation options
translator.register(Resource, ResourceTranslationOptions)
translator.register(Asset, AssetTranslationOptions)
translator.register(Distribution, DistributionTranslationOptions)
