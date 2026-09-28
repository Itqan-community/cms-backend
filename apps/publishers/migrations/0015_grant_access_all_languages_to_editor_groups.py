"""Preserve today's behaviour for today's editors.

Content editing is now scoped to a member's assigned languages. Nobody has
assignments yet, so without this every existing editor would lose access on
deploy. Groups that can already edit content are granted the assignment bypass,
which leaves them exactly as capable as they are today.

Targeting is data-driven rather than by group name: the seeded groups
("Publisher Member", "Publisher Member Admin") hold no content-edit permissions,
so real editors live in custom per-deployment groups that a name-based lookup
would miss. "Itqan Internal" needs no special handling — it is seeded with every
permission by the publishers app's post_migrate hook.

Groups holding only PORTAL_REVIEW_CONTENT are deliberately left alone: reviewers
are already gated by assignment today, and granting them the bypass would widen
their access rather than preserve it.
"""

from django.db import migrations

# Duplicated from apps.core.permissions on purpose: migrations must not import
# runtime code, whose values may change independently of this historical migration.
BYPASS_CODENAME = "portal_access_all_languages"
BYPASS_NAME = "Portal - Access All Languages"
EDIT_CODENAMES = ["portal_update_translation", "portal_update_tafsir"]


def _bypass_permission(apps):
    """The bypass Permission row, created if the sync has not run yet.

    plain_permissions populates permission rows from a post_migrate hook, which
    fires only after every migration has run — so this migration cannot assume
    the row exists. The later sync does an update_or_create on the same natural
    key, so creating it here is safe and simply happens earlier.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    content_type, _ = ContentType.objects.get_or_create(app_label="plain_permissions", model="permission")
    permission, _ = Permission.objects.get_or_create(
        codename=BYPASS_CODENAME,
        content_type=content_type,
        defaults={"name": BYPASS_NAME},
    )
    return permission


def grant_bypass_to_editor_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    permission = _bypass_permission(apps)
    for group in Group.objects.filter(permissions__codename__in=EDIT_CODENAMES).distinct():
        group.permissions.add(permission)


def revoke_bypass_from_editor_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    permission = _bypass_permission(apps)
    for group in Group.objects.filter(permissions__codename__in=EDIT_CODENAMES).distinct():
        group.permissions.remove(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("publishers", "0014_memberlanguage"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(grant_bypass_to_editor_groups, revoke_bypass_from_editor_groups),
    ]
