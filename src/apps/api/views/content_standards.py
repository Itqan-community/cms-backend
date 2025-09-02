"""
Content Standards API Views
Provides public access to content usage standards and guidelines.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json


class ContentStandardsView(View):
    """
    Public API endpoint for content standards documentation.
    No authentication required as this is public information.
    """
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """
        Get content standards documentation.
        Returns structured data for verse, word, and tafsir usage standards.
        """
        standards_data = {
            "title": {
                "en": "Documents: Data Access Standards",
                "ar": "الوثائق: معايير الوصول إلى البيانات"
            },
            "subtitle": {
                "en": "This document describes the standards for accessing data in files. Please follow the guidelines below for each category.",
                "ar": "هذه الوثيقة تصف معايير الوصول إلى البيانات في الملفات. يرجى اتباع الإرشادات أدناه لكل فئة."
            },
            "sections": [
                {
                    "id": "verse_standards",
                    "title": {
                        "en": "Verse Usage Standards",
                        "ar": "معايير استخدام الآية"
                    },
                    "description": {
                        "en": "To access verses, follow the standards below:",
                        "ar": "للوصول إلى الآيات، اتبع المعايير التالية:"
                    },
                    "guidelines": [
                        {
                            "en": "Use correct verse identifier format",
                            "ar": "استخدم تنسيق معرف الآية الصحيح"
                        },
                        {
                            "en": "Ensure proper verse indexing",
                            "ar": "تأكد من فهرسة الآية بشكل صحيح"
                        },
                        {
                            "en": "Check for latest updates in verse database",
                            "ar": "تحقق من آخر التحديثات في قاعدة بيانات الآيات"
                        }
                    ],
                    "example": {
                        "title": {
                            "en": "Example: To access verse 2:255, use",
                            "ar": "مثال: للوصول إلى الآية 2:255، استخدم"
                        },
                        "code": "getVerse('2:255')",
                        "description": {
                            "en": "This will return the complete verse data with Arabic text, translations, and metadata.",
                            "ar": "سيؤدي هذا إلى إرجاع بيانات الآية الكاملة بالنص العربي والترجمات والبيانات الوصفية."
                        }
                    }
                },
                {
                    "id": "word_standards",
                    "title": {
                        "en": "Word Usage Standards",
                        "ar": "معايير استخدام الكلمات"
                    },
                    "description": {
                        "en": "To access words, adhere to the following:",
                        "ar": "للوصول إلى الكلمات، التزم بما يلي:"
                    },
                    "guidelines": [
                        {
                            "en": "Use specified word keys",
                            "ar": "استخدم مفاتيح الكلمات المحددة"
                        },
                        {
                            "en": "Ensure word list is updated",
                            "ar": "تأكد من تحديث قائمة الكلمات"
                        },
                        {
                            "en": "Maintain consistency in word formatting",
                            "ar": "احفظ على الاتساق في تنسيق الكلمات"
                        }
                    ],
                    "example": {
                        "title": {
                            "en": "Example: To retrieve word \"الله\", use",
                            "ar": "مثال: لاسترجاع كلمة \"الله\"، استخدم"
                        },
                        "code": "getWord(\"الله\")",
                        "description": {
                            "en": "This will return word analysis, root information, and grammatical details.",
                            "ar": "سيؤدي هذا إلى إرجاع تحليل الكلمة ومعلومات الجذر والتفاصيل النحوية."
                        }
                    }
                },
                {
                    "id": "tafsir_standards", 
                    "title": {
                        "en": "Tafsir Usage Standards",
                        "ar": "معايير استخدام تفسير"
                    },
                    "description": {
                        "en": "When accessing tafsir, follow the guidelines below:",
                        "ar": "عند الوصول إلى تفسير، اتبع الإرشادات التالية:"
                    },
                    "guidelines": [
                        {
                            "en": "Use correct tafsir reference",
                            "ar": "استخدم مرجع التفسير الصحيح"
                        },
                        {
                            "en": "Ensure accuracy of translations",
                            "ar": "تأكد من دقة الترجمات"
                        },
                        {
                            "en": "Check for updated interpretations",
                            "ar": "تحقق من وجود تفسيرات محدثة لتفسير"
                        }
                    ],
                    "example": {
                        "title": {
                            "en": "Example: To access tafsir for verse 2:255, use",
                            "ar": "مثال: للوصول إلى تفسير للآية 2:255، استخدم"
                        },
                        "code": "getTafsir('2:255')",
                        "description": {
                            "en": "This will return scholarly interpretations and commentary for the specified verse.",
                            "ar": "سيؤدي هذا إلى إرجاع التفسيرات العلمية والتعليقات للآية المحددة."
                        }
                    }
                }
            ],
            "footer": {
                "copyright": {
                    "en": "© Documentation Standards 2023. All rights reserved.",
                    "ar": "© معايير التوثيق لعام 2023. كل الحقوق محفوظة."
                }
            },
            "meta": {
                "version": "1.0",
                "last_updated": "2024-01-01",
                "language_support": ["en", "ar"],
                "public_access": True
            }
        }
        
        return JsonResponse(standards_data, safe=False)


@require_http_methods(["GET"])
def content_standards_simple(request):
    """
    Simple function-based view for content standards.
    Alternative to class-based view for lighter weight response.
    """
    return JsonResponse({
        "message": "Content standards endpoint is active",
        "status": "success",
        "public_access": True
    })
