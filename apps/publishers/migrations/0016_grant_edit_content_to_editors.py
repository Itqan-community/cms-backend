"""Keep today's content editors able to edit content.

Editing an asset's text (the content editor, uploading or restoring a version)
used to need only ``portal_update_<category>``; it now needs the per-category
``portal_edit_<category>_content``. Every group — and every user granted the
permission directly — that can update a category today is given that category's
content permission, so nobody loses access on deploy. Admins can then take it
away from people who should only edit metadata.
"""

from django.db import migrations

# Duplicated from apps.core.permissions on purpose: migrations must not import
# runtime code, whose values may change independently of this historical migration.
# update codename -> (content codename, content permission name)
CONTENT_FOR_UPDATE = {
    "portal_update_translation": ("portal_edit_translation_content", "Portal - Edit Translation Content"),
    "portal_update_tafsir": ("portal_edit_tafsir_content", "Portal - Edit Tafsir Content"),
}


def _content_permission(apps, codename, name):
    """The content Permission row, created if the post_migrate sync has not run yet
    (it fires only after every migration); the sync later update_or_creates the
    same natural key, so creating it here is safe."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    content_type, _ = ContentType.objects.get_or_create(app_label="plain_permissions", model="permission")
    permission, _ = Permission.objects.get_or_create(
        codename=codename, content_type=content_type, defaults={"name": name}
    )
    return permission


def grant_edit_content(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("users", "User")
    for update_codename, (codename, name) in CONTENT_FOR_UPDATE.items():
        permission = _content_permission(apps, codename, name)
        for group in Group.objects.filter(permissions__codename=update_codename).distinct():
            group.permissions.add(permission)
        for user in User.objects.filter(user_permissions__codename=update_codename).distinct():
            user.user_permissions.add(permission)


def revoke_edit_content(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("users", "User")
    for update_codename, (codename, name) in CONTENT_FOR_UPDATE.items():
        permission = _content_permission(apps, codename, name)
        for group in Group.objects.filter(permissions__codename=update_codename).distinct():
            group.permissions.remove(permission)
        for user in User.objects.filter(user_permissions__codename=update_codename).distinct():
            user.user_permissions.remove(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("publishers", "0015_grant_access_all_languages_to_editor_groups"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("users", "0004_apikey"),
    ]

    operations = [migrations.RunPython(grant_edit_content, revoke_edit_content)]
