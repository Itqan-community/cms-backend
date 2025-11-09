from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from .models import Asset, Resource


@register(Resource)
class ResourceTranslationOptions(TranslationOptions):
    """Translation configuration for Resource model"""

    fields = (
        "name",
        "description",
    )


@register(Asset)
class AssetTranslationOptions(TranslationOptions):
    """Translation configuration for Asset model"""

    fields = (
        "name",
        "description",
        "long_description",
    )
