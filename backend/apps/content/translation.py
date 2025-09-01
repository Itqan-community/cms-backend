"""
Content model translations for Itqan CMS
Configures django-modeltranslation for English/Arabic bilingual support
"""
from modeltranslation.translator import translator, TranslationOptions
from .models import Resource, Distribution
from apps.licensing.models import License


class ResourceTranslationOptions(TranslationOptions):
    """Translation configuration for Resource model"""
    fields = (
        'title',           # Main resource title
        'description',     # Resource description
    )
    # Don't translate: resource_type, language, version, checksum, publisher, metadata, published_at
    # These are technical/structural fields that shouldn't vary by language


class DistributionTranslationOptions(TranslationOptions):
    """Translation configuration for Distribution model"""
    fields = (
        # No fields need translation - Distribution is technical configuration
        # endpoint_url, format_type, version, access_config are technical
        # We could add description field in future if needed for UI
    )
    empty = True  # Explicitly mark as having no translatable fields for now


class LicenseTranslationOptions(TranslationOptions):
    """Translation configuration for License model"""
    fields = (
        'terms',           # Legal terms and conditions for using the resource
    )
    # Don't translate: license_type, resource, geographic_restrictions, usage_restrictions (JSON)
    # requires_approval, effective_from, expires_at - these are structural/technical fields


# Register translation options
translator.register(Resource, ResourceTranslationOptions)
translator.register(Distribution, DistributionTranslationOptions)
translator.register(License, LicenseTranslationOptions)
