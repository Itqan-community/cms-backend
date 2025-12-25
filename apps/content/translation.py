from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from .models import Asset, Reciter, Resource, Riwayah


@register(Resource)
class ResourceTranslationOptions(TranslationOptions):

    fields = (
        "name",
        "description",
    )


@register(Asset)
class AssetTranslationOptions(TranslationOptions):

    fields = (
        "name",
        "description",
        "long_description",
    )


@register(Reciter)
class ReciterTranslationOptions(TranslationOptions):

    fields = ("name",)


@register(Riwayah)
class RiwayahTranslationOptions(TranslationOptions):

    fields = ("name",)
