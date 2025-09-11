from modeltranslation.translator import TranslationOptions
from modeltranslation.translator import register

from .models import Asset
from .models import License
from .models import Resource


@register(Resource)
class ResourceTranslationOptions(TranslationOptions):
    fields = (
        "name",
        "description",
    )


@register(Asset)
class AssetTranslationOptions(TranslationOptions):
    fields = (
        "title",
        "description",
        "long_description",
    )


@register(License)
class LicenseTranslationOptions(TranslationOptions):
    """Translation configuration for License model"""

    fields = (
        "name",  # License name
        "summary",  # Brief license description
        "full_text",  # Complete license text
    )
