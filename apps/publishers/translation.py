from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions
import simple_history

from apps.core.audit import AuditHistoricalRecords

from .models import Publisher, PublisherGroup


@register(Publisher)
class PublisherTranslationOptions(TranslationOptions):
    """Translation configuration for Publisher model"""

    fields = (
        "name",
        "description",
    )


@register(PublisherGroup)
class PublisherGroupTranslationOptions(TranslationOptions):
    """Role names are entered in both languages and shown in the reader's language."""

    fields = ("name",)


simple_history.register(Publisher, records_class=AuditHistoricalRecords)
