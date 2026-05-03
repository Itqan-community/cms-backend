from django.db.models.enums import TextChoices
from django.utils.translation import gettext_lazy as _


class PermissionChoice(TextChoices):
    # please steer away from [view, add, change, delete] format as it is used by django's default permissions

    # Reciters
    READ_PORTAL_RECITER = "read_portal_reciter", _("View Portal Reciters")
    CREATE_PORTAL_RECITER = "create_portal_reciter", _("Create Portal Reciters")
    UPDATE_PORTAL_RECITER = "update_portal_reciter", _("Update Portal Reciters")
    DELETE_PORTAL_RECITER = "delete_portal_reciter", _("Delete Portal Reciters")

    # Recitations
    READ_PORTAL_RECITATION = "read_portal_recitation", _("View Portal Recitations")
    CREATE_PORTAL_RECITATION = "create_portal_recitation", _("Create Portal Recitations")
    UPDATE_PORTAL_RECITATION = "update_portal_recitation", _("Update Portal Recitations")
    DELETE_PORTAL_RECITATION = "delete_portal_recitation", _("Delete Portal Recitations")

    # Timing Upload
    UPLOAD_PORTAL_TIMING = "upload_portal_timing", _("Upload Portal Recitation Timings")

    # Tafsirs
    READ_PORTAL_TAFSIR = "read_portal_tafsir", _("View Portal Tafsirs")
    CREATE_PORTAL_TAFSIR = "create_portal_tafsir", _("Create Portal Tafsirs")
    UPDATE_PORTAL_TAFSIR = "update_portal_tafsir", _("Update Portal Tafsirs")
    DELETE_PORTAL_TAFSIR = "delete_portal_tafsir", _("Delete Portal Tafsirs")

    # Translations
    READ_PORTAL_TRANSLATION = "read_portal_translation", _("View Portal Translations")
    CREATE_PORTAL_TRANSLATION = "create_portal_translation", _("Create Portal Translations")
    UPDATE_PORTAL_TRANSLATION = "update_portal_translation", _("Update Portal Translations")
    DELETE_PORTAL_TRANSLATION = "delete_portal_translation", _("Delete Portal Translations")
