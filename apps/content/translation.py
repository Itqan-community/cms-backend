from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions

from .models import Asset, EditorialRecommendation, Qiraah, RecitationFolder, Reciter, Riwayah


@register(Asset)
class AssetTranslationOptions(TranslationOptions):
    fields = (
        "name",
        "description",
        "long_description",
    )


@register(Reciter)
class ReciterTranslationOptions(TranslationOptions):
    fields = ("name", "bio")


@register(Riwayah)
class RiwayahTranslationOptions(TranslationOptions):
    fields = ("name", "bio")


@register(Qiraah)
class QiraahTranslationOptions(TranslationOptions):
    fields = ("name", "bio")


@register(RecitationFolder)
class RecitationFolderTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(EditorialRecommendation)
class EditorialRecommendationTranslationOptions(TranslationOptions):
    fields = ("title", "description")
