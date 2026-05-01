from django.db.models.enums import TextChoices
from django.utils.translation import gettext_lazy as _


class PermissionChoice(TextChoices):
    # please steer away from [view, add, change, delete] format as it is used by django's default permissions
    READ_PORTAL_RECITER = "read_portal_reciter", _("View Portal Reciters")
    CREATE_PORTAL_RECITER = "create_portal_reciter", _("Create Portal Reciters")
    UPDATE_PORTAL_RECITER = "update_portal_reciter", _("Update Portal Reciters")
    DROP_PORTAL_RECITER = "drop_portal_reciter", _("Delete Portal Reciters")
