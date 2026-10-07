from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions
import simple_history

from apps.core.audit import AuditHistoricalRecords

from .models import Asset, EditorialRecommendation, MushafLayout, Qiraah, RecitationFolder, Reciter, Riwayah


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


@register(MushafLayout)
class MushafLayoutTranslationOptions(TranslationOptions):
    fields = ("name",)


# Register translated models with django-simple-history using AuditHistoricalRecords
# after modeltranslation has attached the translated fields (name_ar, name_en, etc.).
for _translated_model in (
    Asset,
    Reciter,
    Riwayah,
    Qiraah,
    RecitationFolder,
    EditorialRecommendation,
    MushafLayout,
):
    simple_history.register(_translated_model, records_class=AuditHistoricalRecords)
