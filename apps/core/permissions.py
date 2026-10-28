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
    PORTAL_READ_TRANSLATION = "portal_read_translation", _("Portal - View Translations")
    PORTAL_CREATE_TRANSLATION = "portal_create_translation", _("Portal - Create Translations")
    PORTAL_UPDATE_TRANSLATION = "portal_update_translation", _("Portal - Update Translations")
    PORTAL_DELETE_TRANSLATION = "portal_delete_translation", _("Portal - Delete Translations")

    # Mushafs
    PORTAL_READ_MUSHAF = "portal_read_mushaf", _("Portal - View Mushafs")
    PORTAL_CREATE_MUSHAF = "portal_create_mushaf", _("Portal - Create Mushafs")
    PORTAL_UPDATE_MUSHAF = "portal_update_mushaf", _("Portal - Update Mushafs")
    PORTAL_DELETE_MUSHAF = "portal_delete_mushaf", _("Portal - Delete Mushafs")

    # Mushaf Layouts
    PORTAL_READ_MUSHAF_LAYOUT = "portal_read_mushaf_layout", _("Portal - View Mushaf Layouts")
    PORTAL_CREATE_MUSHAF_LAYOUT = "portal_create_mushaf_layout", _("Portal - Create Mushaf Layouts")
    PORTAL_UPDATE_MUSHAF_LAYOUT = "portal_update_mushaf_layout", _("Portal - Update Mushaf Layouts")
    PORTAL_DELETE_MUSHAF_LAYOUT = "portal_delete_mushaf_layout", _("Portal - Delete Mushaf Layouts")

    # Fonts
    PORTAL_READ_FONT = "portal_read_font", _("Portal - View Fonts")
    PORTAL_CREATE_FONT = "portal_create_font", _("Portal - Create Fonts")
    PORTAL_UPDATE_FONT = "portal_update_font", _("Portal - Update Fonts")
    PORTAL_DELETE_FONT = "portal_delete_font", _("Portal - Delete Fonts")

    # Publishers
    PORTAL_READ_PUBLISHER = "portal_read_publisher", _("Portal - View Publishers")
    PORTAL_CREATE_PUBLISHER = "portal_create_publisher", _("Portal - Create Publishers")
    PORTAL_UPDATE_PUBLISHER = "portal_update_publisher", _("Portal - Update Publishers")
    PORTAL_DELETE_PUBLISHER = "portal_delete_publisher", _("Portal - Delete Publishers")

    # Groups (role management)
    PORTAL_READ_GROUP = "portal_read_group", _("Portal - View Roles")
    PORTAL_CREATE_GROUP = "portal_create_group", _("Portal - Create Roles")
    PORTAL_UPDATE_GROUP = "portal_update_group", _("Portal - Update Roles")
    PORTAL_DELETE_GROUP = "portal_delete_group", _("Portal - Delete Roles")

    # Members
    PORTAL_VIEW_PUBLISHER_MEMBERS = "portal_view_publisher_members", _("Portal - View Publisher Members")
    PORTAL_INVITE_PUBLISHER_MEMBERS = "portal_invite_publisher_members", _("Portal - Invite Publisher Members")
    PORTAL_UPDATE_PUBLISHER_MEMBERS = "portal_update_publisher_members", _("Portal - Update Publisher Members")
    PORTAL_DELETE_PUBLISHER_MEMBERS = "portal_delete_publisher_members", _("Portal - Delete Publisher Members")

    # Access Requests
    PORTAL_VIEW_ACCESS_REQUESTS = "portal_view_access_requests", _("Portal - View Access Requests")
    PORTAL_ACCEPT_OR_REJECT_ACCESS_REQUESTS = (
        "portal_accept_or_reject_access_requests",
        _("Portal - Accept or Reject Access Requests"),
    )
    PORTAL_MANAGE_ACCESS_REQUESTS_SETTINGS = (
        "portal_manage_access_requests_settings",
        _("Portal - Manage Access Requests Settings"),
    )

    # Usage statistics
    PORTAL_READ_USAGE = "portal_read_usage", _("Portal - View Usage Statistics")

    # Content review
    PORTAL_REVIEW_CONTENT = "portal_review_content", _("Portal - Review Content")
    # Choosing which fully approved version of a translation / tafsir consumers see.
    PORTAL_PUBLISH_CONTENT = "portal_publish_content", _("Portal - Publish Content")
    # Removing a version from the package manager and every consumer surface. Itqan
    # admins only: unlike withdrawing, it breaks lockfiles pinned to the version.
    PORTAL_REMOVE_PACKAGE_VERSION = "portal_remove_package_version", _("Portal - Remove Package Versions")

    # Content editing: changing an asset's text (the content editor, uploading or
    # restoring a version). Separate from PORTAL_UPDATE_*, which covers metadata only.
    PORTAL_EDIT_TRANSLATION_CONTENT = "portal_edit_translation_content", _("Portal - Edit Translation Content")
    PORTAL_EDIT_TAFSIR_CONTENT = "portal_edit_tafsir_content", _("Portal - Edit Tafsir Content")

    # Asset languages
    # ACCESS_ALL_LANGUAGES bypasses per-member language assignment: the holder is treated as
    # assigned to every language on an asset. It grants no editing or reviewing rights of its
    # own — what the holder may DO is still governed by PORTAL_EDIT_*_CONTENT / PORTAL_REVIEW_CONTENT,
    # which is why it appears in no implication entry below.
    PORTAL_ACCESS_ALL_LANGUAGES = "portal_access_all_languages", _("Portal - Access All Languages")
    PORTAL_ADD_ASSET_LANGUAGE = "portal_add_asset_language", _("Portal - Add Asset Language")

    # Text columns of translations / tafsirs: add, label, reorder and delete columns.
    # Granted to very few users; editing the cells needs only PORTAL_EDIT_*_CONTENT.
    # Managing also requires PORTAL_ACCESS_ALL_LANGUAGES, since a column applies to every language.
    PORTAL_MANAGE_ASSET_COLUMNS = "portal_manage_asset_columns", _("Portal - Manage Asset Columns")


# Permission hierarchy: maps each permission to the set of permissions it directly implies.
#
# Within a resource group, every write action implies READ: you must be able to read a resource
# to act on it at all. On top of that, CREATE and UPDATE imply *each other* — they are treated
# as a single "may author content" capability, so granting either grants both and revoking
# either revokes both. There is deliberately no way to hold CREATE without UPDATE. DELETE sits
# above the pair and implies both, so granting DELETE yields the full CRUD set.
#
# The CREATE <-> UPDATE cycle is intentional; `PermissionHierarchyService._closure` walks the
# graph with a visited-set, so cycles terminate normally.
#
# Only direct implications are listed here; the transitive closure (e.g. UPLOAD_TIMING -> READ)
# is computed by the service layer, so this map stays easy to read and edit.
PERMISSION_IMPLICATIONS: dict[PermissionChoice, frozenset[PermissionChoice]] = {
    # Reciters
    PermissionChoice.PORTAL_CREATE_RECITER: frozenset(
        {PermissionChoice.PORTAL_READ_RECITER, PermissionChoice.PORTAL_UPDATE_RECITER}
    ),
    PermissionChoice.PORTAL_UPDATE_RECITER: frozenset(
        {PermissionChoice.PORTAL_READ_RECITER, PermissionChoice.PORTAL_CREATE_RECITER}
    ),
    PermissionChoice.PORTAL_DELETE_RECITER: frozenset(
        {
            PermissionChoice.PORTAL_READ_RECITER,
            PermissionChoice.PORTAL_UPDATE_RECITER,
            PermissionChoice.PORTAL_CREATE_RECITER,
        }
    ),
    # Recitations
    PermissionChoice.PORTAL_CREATE_RECITATION: frozenset(
        {PermissionChoice.PORTAL_READ_RECITATION, PermissionChoice.PORTAL_UPDATE_RECITATION}
    ),
    PermissionChoice.PORTAL_UPDATE_RECITATION: frozenset(
        {PermissionChoice.PORTAL_READ_RECITATION, PermissionChoice.PORTAL_CREATE_RECITATION}
    ),
    PermissionChoice.PORTAL_DELETE_RECITATION: frozenset(
        {
            PermissionChoice.PORTAL_READ_RECITATION,
            PermissionChoice.PORTAL_UPDATE_RECITATION,
            PermissionChoice.PORTAL_CREATE_RECITATION,
        }
    ),
    # Uploading timings mutates an existing recitation, so it requires being able to update it.
    PermissionChoice.PORTAL_UPLOAD_TIMING: frozenset({PermissionChoice.PORTAL_UPDATE_RECITATION}),
    # Tafsirs
    PermissionChoice.PORTAL_CREATE_TAFSIR: frozenset(
        {PermissionChoice.PORTAL_READ_TAFSIR, PermissionChoice.PORTAL_UPDATE_TAFSIR}
    ),
    PermissionChoice.PORTAL_UPDATE_TAFSIR: frozenset(
        {PermissionChoice.PORTAL_READ_TAFSIR, PermissionChoice.PORTAL_CREATE_TAFSIR}
    ),
    PermissionChoice.PORTAL_DELETE_TAFSIR: frozenset(
        {
            PermissionChoice.PORTAL_READ_TAFSIR,
            PermissionChoice.PORTAL_UPDATE_TAFSIR,
            PermissionChoice.PORTAL_CREATE_TAFSIR,
        }
    ),
    # Editing an asset's text requires reading the asset, not editing its metadata.
    PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT: frozenset({PermissionChoice.PORTAL_READ_TAFSIR}),
    PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT: frozenset({PermissionChoice.PORTAL_READ_TRANSLATION}),
    # Translations
    PermissionChoice.PORTAL_CREATE_TRANSLATION: frozenset(
        {PermissionChoice.PORTAL_READ_TRANSLATION, PermissionChoice.PORTAL_UPDATE_TRANSLATION}
    ),
    PermissionChoice.PORTAL_UPDATE_TRANSLATION: frozenset(
        {PermissionChoice.PORTAL_READ_TRANSLATION, PermissionChoice.PORTAL_CREATE_TRANSLATION}
    ),
    PermissionChoice.PORTAL_DELETE_TRANSLATION: frozenset(
        {
            PermissionChoice.PORTAL_READ_TRANSLATION,
            PermissionChoice.PORTAL_UPDATE_TRANSLATION,
            PermissionChoice.PORTAL_CREATE_TRANSLATION,
        }
    ),
    # Mushafs
    PermissionChoice.PORTAL_CREATE_MUSHAF: frozenset(
        {PermissionChoice.PORTAL_READ_MUSHAF, PermissionChoice.PORTAL_UPDATE_MUSHAF}
    ),
    PermissionChoice.PORTAL_UPDATE_MUSHAF: frozenset(
        {PermissionChoice.PORTAL_READ_MUSHAF, PermissionChoice.PORTAL_CREATE_MUSHAF}
    ),
    PermissionChoice.PORTAL_DELETE_MUSHAF: frozenset(
        {
            PermissionChoice.PORTAL_READ_MUSHAF,
            PermissionChoice.PORTAL_UPDATE_MUSHAF,
            PermissionChoice.PORTAL_CREATE_MUSHAF,
        }
    ),
    # Mushaf Layouts
    PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT: frozenset(
        {PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT, PermissionChoice.PORTAL_UPDATE_MUSHAF_LAYOUT}
    ),
    PermissionChoice.PORTAL_UPDATE_MUSHAF_LAYOUT: frozenset(
        {PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT, PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT}
    ),
    PermissionChoice.PORTAL_DELETE_MUSHAF_LAYOUT: frozenset(
        {
            PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT,
            PermissionChoice.PORTAL_UPDATE_MUSHAF_LAYOUT,
            PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT,
        }
    ),
    # Fonts
    PermissionChoice.PORTAL_CREATE_FONT: frozenset(
        {PermissionChoice.PORTAL_READ_FONT, PermissionChoice.PORTAL_UPDATE_FONT}
    ),
    PermissionChoice.PORTAL_UPDATE_FONT: frozenset(
        {PermissionChoice.PORTAL_READ_FONT, PermissionChoice.PORTAL_CREATE_FONT}
    ),
    PermissionChoice.PORTAL_DELETE_FONT: frozenset(
        {
            PermissionChoice.PORTAL_READ_FONT,
            PermissionChoice.PORTAL_UPDATE_FONT,
            PermissionChoice.PORTAL_CREATE_FONT,
        }
    ),
    # Publishers
    PermissionChoice.PORTAL_CREATE_PUBLISHER: frozenset(
        {PermissionChoice.PORTAL_READ_PUBLISHER, PermissionChoice.PORTAL_UPDATE_PUBLISHER}
    ),
    PermissionChoice.PORTAL_UPDATE_PUBLISHER: frozenset({PermissionChoice.PORTAL_READ_PUBLISHER}),
    PermissionChoice.PORTAL_DELETE_PUBLISHER: frozenset(
        {
            PermissionChoice.PORTAL_READ_PUBLISHER,
            PermissionChoice.PORTAL_UPDATE_PUBLISHER,
            PermissionChoice.PORTAL_CREATE_PUBLISHER,
        }
    ),
    # Groups
    PermissionChoice.PORTAL_CREATE_GROUP: frozenset(
        {PermissionChoice.PORTAL_READ_GROUP, PermissionChoice.PORTAL_UPDATE_GROUP}
    ),
    PermissionChoice.PORTAL_UPDATE_GROUP: frozenset(
        {PermissionChoice.PORTAL_READ_GROUP, PermissionChoice.PORTAL_CREATE_GROUP}
    ),
    PermissionChoice.PORTAL_DELETE_GROUP: frozenset(
        {
            PermissionChoice.PORTAL_READ_GROUP,
            PermissionChoice.PORTAL_UPDATE_GROUP,
            PermissionChoice.PORTAL_CREATE_GROUP,
        }
    ),
    # Members — every write action requires being able to view members first.
    PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS: frozenset({PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS}),
    PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS: frozenset({PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS}),
    PermissionChoice.PORTAL_DELETE_PUBLISHER_MEMBERS: frozenset({PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS}),
    # Asset columns
    PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS: frozenset(
        {PermissionChoice.PORTAL_READ_TAFSIR, PermissionChoice.PORTAL_READ_TRANSLATION}
    ),
    # Access Requests
    PermissionChoice.PORTAL_ACCEPT_OR_REJECT_ACCESS_REQUESTS: frozenset({PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS}),
    PermissionChoice.PORTAL_MANAGE_ACCESS_REQUESTS_SETTINGS: frozenset({PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS}),
}


P = PermissionChoice

# Permissions grouped by what they are used for, in the order the role editor shows them.
# Every PermissionChoice appears in exactly one group (enforced by a test).
PERMISSION_GROUPS: list[tuple[str, str, list[PermissionChoice]]] = [
    ("portal", _("Control panel"), [P.PORTAL_ACCESS]),
    (
        "reciters",
        _("Reciters"),
        [P.PORTAL_READ_RECITER, P.PORTAL_CREATE_RECITER, P.PORTAL_UPDATE_RECITER, P.PORTAL_DELETE_RECITER],
    ),
    (
        "recitations",
        _("Recitations"),
        [
            P.PORTAL_READ_RECITATION,
            P.PORTAL_CREATE_RECITATION,
            P.PORTAL_UPDATE_RECITATION,
            P.PORTAL_DELETE_RECITATION,
            P.PORTAL_UPLOAD_TIMING,
        ],
    ),
    (
        "tafsirs",
        _("Tafsirs"),
        [
            P.PORTAL_READ_TAFSIR,
            P.PORTAL_CREATE_TAFSIR,
            P.PORTAL_UPDATE_TAFSIR,
            P.PORTAL_DELETE_TAFSIR,
            P.PORTAL_EDIT_TAFSIR_CONTENT,
        ],
    ),
    (
        "translations",
        _("Translations"),
        [
            P.PORTAL_READ_TRANSLATION,
            P.PORTAL_CREATE_TRANSLATION,
            P.PORTAL_UPDATE_TRANSLATION,
            P.PORTAL_DELETE_TRANSLATION,
            P.PORTAL_EDIT_TRANSLATION_CONTENT,
        ],
    ),
    (
        "mushafs",
        _("Mushafs"),
        [P.PORTAL_READ_MUSHAF, P.PORTAL_CREATE_MUSHAF, P.PORTAL_UPDATE_MUSHAF, P.PORTAL_DELETE_MUSHAF],
    ),
    (
        "mushaf_layouts",
        _("Mushaf layouts"),
        [
            P.PORTAL_READ_MUSHAF_LAYOUT,
            P.PORTAL_CREATE_MUSHAF_LAYOUT,
            P.PORTAL_UPDATE_MUSHAF_LAYOUT,
            P.PORTAL_DELETE_MUSHAF_LAYOUT,
        ],
    ),
    ("fonts", _("Fonts"), [P.PORTAL_READ_FONT, P.PORTAL_CREATE_FONT, P.PORTAL_UPDATE_FONT, P.PORTAL_DELETE_FONT]),
    ("review", _("Review and publishing"), [P.PORTAL_REVIEW_CONTENT, P.PORTAL_PUBLISH_CONTENT]),
    (
        "languages_columns",
        _("Languages and columns"),
        [P.PORTAL_ACCESS_ALL_LANGUAGES, P.PORTAL_ADD_ASSET_LANGUAGE, P.PORTAL_MANAGE_ASSET_COLUMNS],
    ),
    (
        "publishers",
        _("Publishers"),
        [P.PORTAL_READ_PUBLISHER, P.PORTAL_CREATE_PUBLISHER, P.PORTAL_UPDATE_PUBLISHER, P.PORTAL_DELETE_PUBLISHER],
    ),
    (
        "members",
        _("Members"),
        [
            P.PORTAL_VIEW_PUBLISHER_MEMBERS,
            P.PORTAL_INVITE_PUBLISHER_MEMBERS,
            P.PORTAL_UPDATE_PUBLISHER_MEMBERS,
            P.PORTAL_DELETE_PUBLISHER_MEMBERS,
        ],
    ),
    ("roles", _("Roles"), [P.PORTAL_READ_GROUP, P.PORTAL_CREATE_GROUP, P.PORTAL_UPDATE_GROUP, P.PORTAL_DELETE_GROUP]),
    (
        "access_requests",
        _("Access requests"),
        [
            P.PORTAL_VIEW_ACCESS_REQUESTS,
            P.PORTAL_ACCEPT_OR_REJECT_ACCESS_REQUESTS,
            P.PORTAL_MANAGE_ACCESS_REQUESTS_SETTINGS,
        ],
    ),
    ("usage", _("Usage statistics"), [P.PORTAL_READ_USAGE]),
    ("packages", _("Packages"), [P.PORTAL_REMOVE_PACKAGE_VERSION]),
]
