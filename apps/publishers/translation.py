from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions
import simple_history

from apps.core.audit import AuditHistoricalRecords

from .models import Publisher


@register(Publisher)
class PublisherTranslationOptions(TranslationOptions):
    """Translation configuration for Publisher model"""

    fields = (
        "name",
        "description",
    )


simple_history.register(Publisher, records_class=AuditHistoricalRecords)
