from django.db.models.enums import TextChoices
from django.utils.translation import gettext_lazy as _


class PermissionChoice(TextChoices):
    # please steer away from [view, add, change, delete] format as it is used by django's default permissions

    # Reciters
    PORTAL_READ_RECITER = "PORTAL_READ_reciter", _("Portal - View Reciters")
    PORTAL_CREATE_RECITER = "PORTAL_CREATE_reciter", _("Portal - Create Reciters")
    PORTAL_UPDATE_RECITER = "PORTAL_UPDATE_reciter", _("Portal - Update Reciters")
    PORTAL_DELETE_RECITER = "PORTAL_DELETE_reciter", _("Portal - Delete Reciters")

    # Recitations
    PORTAL_READ_RECITATION = "PORTAL_READ_recitation", _("Portal - View Recitations")
    PORTAL_CREATE_RECITATION = "PORTAL_CREATE_recitation", _("Portal - Create Recitations")
    PORTAL_UPDATE_RECITATION = "PORTAL_UPDATE_recitation", _("Portal - Update Recitations")
    PORTAL_DELETE_RECITATION = "PORTAL_DELETE_recitation", _("Portal - Delete Recitations")

    # Timing Upload
    PORTAL_UPLOAD_TIMING = "upload_portal_timing", _("Portal - Upload Recitation Timings")

    # Tafsirs
    PORTAL_READ_TAFSIR = "PORTAL_READ_tafsir", _("Portal - View Tafsirs")
    PORTAL_CREATE_TAFSIR = "PORTAL_CREATE_tafsir", _("Portal - Create Tafsirs")
    PORTAL_UPDATE_TAFSIR = "PORTAL_UPDATE_tafsir", _("Portal - Update Tafsirs")
    PORTAL_DELETE_TAFSIR = "PORTAL_DELETE_tafsir", _("Portal - Delete Tafsirs")

    # Translations
    PORTAL_READ_TRANSLATION = "PORTAL_READ_translation", _("View Portal Translations")
    PORTAL_CREATE_TRANSLATION = "PORTAL_CREATE_translation", _("Create Portal Translations")
    PORTAL_UPDATE_TRANSLATION = "PORTAL_UPDATE_translation", _("Update Portal Translations")
    PORTAL_DELETE_TRANSLATION = "PORTAL_DELETE_translation", _("Delete Portal Translations")
