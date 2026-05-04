from django.db.models.enums import TextChoices
from django.utils.translation import gettext_lazy as _


class PermissionChoice(TextChoices):
    # please steer away from [view, add, change, delete] format as it is used by django's default permissions
    # Permission to be used in FE to show/hide portal
    PORTAL_ACCESS = "portal_access", _("Access Portal")

    # Reciters
    PORTAL_READ_RECITER = "portal_read_reciter", _("Portal - View Reciters")
    PORTAL_CREATE_RECITER = "portal_create_reciter", _("Portal - Create Reciters")
    PORTAL_UPDATE_RECITER = "portal_update_reciter", _("Portal - Update Reciters")
    PORTAL_DELETE_RECITER = "portal_delete_reciter", _("Portal - Delete Reciters")

    # Recitations
    PORTAL_READ_RECITATION = "portal_read_recitation", _("Portal - View Recitations")
    PORTAL_CREATE_RECITATION = "portal_create_recitation", _("Portal - Create Recitations")
    PORTAL_UPDATE_RECITATION = "portal_update_recitation", _("Portal - Update Recitations")
    PORTAL_DELETE_RECITATION = "portal_delete_recitation", _("Portal - Delete Recitations")

    # Timing Upload
    PORTAL_UPLOAD_TIMING = "portal_upload_timing", _("Portal - Upload Recitation Timings")

    # Tafsirs
    PORTAL_READ_TAFSIR = "portal_read_tafsir", _("Portal - View Tafsirs")
    PORTAL_CREATE_TAFSIR = "portal_create_tafsir", _("Portal - Create Tafsirs")
    PORTAL_UPDATE_TAFSIR = "portal_update_tafsir", _("Portal - Update Tafsirs")
    PORTAL_DELETE_TAFSIR = "portal_delete_tafsir", _("Portal - Delete Tafsirs")

    # Translations
    PORTAL_READ_TRANSLATION = "portal_read_translation", _("View Portal Translations")
    PORTAL_CREATE_TRANSLATION = "portal_create_translation", _("Create Portal Translations")
    PORTAL_UPDATE_TRANSLATION = "portal_update_translation", _("Update Portal Translations")
    PORTAL_DELETE_TRANSLATION = "portal_delete_translation", _("Delete Portal Translations")
