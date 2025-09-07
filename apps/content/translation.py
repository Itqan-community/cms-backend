"""
Content model translations for Itqan CMS
Configures django-modeltranslation for English/Arabic bilingual support
"""

from modeltranslation.translator import TranslationOptions
from modeltranslation.translator import translator

from .models import Asset
from .models import Distribution
from .models import License
from .models import Resource


class ResourceTranslationOptions(TranslationOptions):
    """Translation configuration for Resource model"""

    fields = (
        "name",  # Main resource name (was title)
        "description",  # Resource description
    )
    # Don't translate: category, status, slug, publishing_organization, default_license
    # These are technical/structural fields that shouldn't vary by language


class AssetTranslationOptions(TranslationOptions):
    """Translation configuration for Asset model"""

    fields = (
        "title",  # Display title for API
        "description",  # Asset description
        "long_description",  # Extended description
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


class LicenseTranslationOptions(TranslationOptions):
    """Translation configuration for License model"""

    fields = (
        "name",  # License name
        "summary",  # Brief license description
        "full_text",  # Complete license text
    )
    # Don't translate: code, url, icon_url, legal_code_url, license_terms (JSON)
    # permissions, conditions, limitations (JSON) - these are structured data


# Register translation options
translator.register(Resource, ResourceTranslationOptions)
translator.register(Asset, AssetTranslationOptions)
translator.register(Distribution, DistributionTranslationOptions)
translator.register(License, LicenseTranslationOptions)
