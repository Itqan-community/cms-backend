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

    # Publishers
    PORTAL_READ_PUBLISHER = "portal_read_publisher", _("Portal - View Publishers")
    PORTAL_CREATE_PUBLISHER = "portal_create_publisher", _("Portal - Create Publishers")
    PORTAL_UPDATE_PUBLISHER = "portal_update_publisher", _("Portal - Update Publishers")
    PORTAL_DELETE_PUBLISHER = "portal_delete_publisher", _("Portal - Delete Publishers")

    # Groups (role management)
    PORTAL_READ_GROUP = "portal_read_group", _("Portal - View Groups")
    PORTAL_CREATE_GROUP = "portal_create_group", _("Portal - Create Groups")
    PORTAL_UPDATE_GROUP = "portal_update_group", _("Portal - Update Groups")
    PORTAL_DELETE_GROUP = "portal_delete_group", _("Portal - Delete Groups")

    # Members
    PORTAL_VIEW_PUBLISHER_MEMBERS = "portal_view_publisher_members", _("Portal - View Publisher Members")
    PORTAL_INVITE_PUBLISHER_MEMBERS = "portal_invite_publisher_members", _("Portal - Invite Publisher Members")
    PORTAL_UPDATE_PUBLISHER_MEMBERS = "portal_update_publisher_members", _("Portal - Update Publisher Members")
    PORTAL_DELETE_PUBLISHER_MEMBERS = "portal_delete_publisher_members", _("Portal - Delete Publisher Members")


# Permission hierarchy: maps each permission to the set of permissions it directly implies.
#
# Within a resource group, CREATE, UPDATE and DELETE each independently imply READ: you must
# be able to read a resource to act on it at all, but the write actions do not depend on each
# other (a user may UPDATE without being able to CREATE, or DELETE without being able to
# UPDATE). The shape is a star pointing at READ, not a seniority chain.
#
# Only direct implications are listed here; the transitive closure (e.g. UPLOAD_TIMING -> READ)
# is computed by the service layer, so this map stays easy to read and edit.
PERMISSION_IMPLICATIONS: dict[PermissionChoice, frozenset[PermissionChoice]] = {
    # Reciters
    PermissionChoice.PORTAL_CREATE_RECITER: frozenset({PermissionChoice.PORTAL_READ_RECITER}),
    PermissionChoice.PORTAL_UPDATE_RECITER: frozenset({PermissionChoice.PORTAL_READ_RECITER}),
    PermissionChoice.PORTAL_DELETE_RECITER: frozenset({PermissionChoice.PORTAL_READ_RECITER}),
    # Recitations
    PermissionChoice.PORTAL_CREATE_RECITATION: frozenset({PermissionChoice.PORTAL_READ_RECITATION}),
    PermissionChoice.PORTAL_UPDATE_RECITATION: frozenset({PermissionChoice.PORTAL_READ_RECITATION}),
    PermissionChoice.PORTAL_DELETE_RECITATION: frozenset({PermissionChoice.PORTAL_READ_RECITATION}),
    # Uploading timings mutates an existing recitation, so it requires being able to update it.
    PermissionChoice.PORTAL_UPLOAD_TIMING: frozenset({PermissionChoice.PORTAL_UPDATE_RECITATION}),
    # Tafsirs
    PermissionChoice.PORTAL_CREATE_TAFSIR: frozenset({PermissionChoice.PORTAL_READ_TAFSIR}),
    PermissionChoice.PORTAL_UPDATE_TAFSIR: frozenset({PermissionChoice.PORTAL_READ_TAFSIR}),
    PermissionChoice.PORTAL_DELETE_TAFSIR: frozenset({PermissionChoice.PORTAL_READ_TAFSIR}),
    # Translations
    PermissionChoice.PORTAL_CREATE_TRANSLATION: frozenset({PermissionChoice.PORTAL_READ_TRANSLATION}),
    PermissionChoice.PORTAL_UPDATE_TRANSLATION: frozenset({PermissionChoice.PORTAL_READ_TRANSLATION}),
    PermissionChoice.PORTAL_DELETE_TRANSLATION: frozenset({PermissionChoice.PORTAL_READ_TRANSLATION}),
    # Publishers
    PermissionChoice.PORTAL_CREATE_PUBLISHER: frozenset({PermissionChoice.PORTAL_READ_PUBLISHER}),
    PermissionChoice.PORTAL_UPDATE_PUBLISHER: frozenset({PermissionChoice.PORTAL_READ_PUBLISHER}),
    PermissionChoice.PORTAL_DELETE_PUBLISHER: frozenset({PermissionChoice.PORTAL_READ_PUBLISHER}),
    # Groups
    PermissionChoice.PORTAL_CREATE_GROUP: frozenset({PermissionChoice.PORTAL_READ_GROUP}),
    PermissionChoice.PORTAL_UPDATE_GROUP: frozenset({PermissionChoice.PORTAL_READ_GROUP}),
    PermissionChoice.PORTAL_DELETE_GROUP: frozenset({PermissionChoice.PORTAL_READ_GROUP}),
    # Members — every write action requires being able to view members first.
    PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS: frozenset({PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS}),
    PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS: frozenset({PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS}),
    PermissionChoice.PORTAL_DELETE_PUBLISHER_MEMBERS: frozenset({PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS}),
}
