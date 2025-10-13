
from modeltranslation.decorators import register
from modeltranslation.translator import TranslationOptions
from .models import Publisher


@register(Publisher)
class PublisherTranslationOptions(TranslationOptions):
    """Translation configuration for Publisher model"""
    fields = (
        'name',
        'description',
    )
