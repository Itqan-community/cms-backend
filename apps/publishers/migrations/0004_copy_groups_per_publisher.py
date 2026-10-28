"""Give every publisher its own copy of each shared group its memberships use.

Groups used to be global, so one "Admin" group could back members of many publishers. Each
(publisher, group) pair now gets a publisher-owned copy with the same name and permissions,
and that publisher's memberships move onto it. The original shared groups are left as they
are. Publisher roles also stop being mirrored into ``user.groups`` (permissions come from the
membership itself), so those links are removed; global groups such as Itqan Internal stay.

The reverse is a no-op: memberships are not moved back onto the shared groups.
"""

import uuid

from django.db import migrations

ITQAN_INTERNAL_GROUP = "Itqan Internal"


def copy_groups_per_publisher(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    PublisherGroup = apps.get_model("publishers", "PublisherGroup")
    PublisherMember = apps.get_model("publishers", "PublisherMember")
    User = apps.get_model("users", "User")

    internal_ids = set(Group.objects.filter(name=ITQAN_INTERNAL_GROUP).values_list("id", flat=True))
    role_group_ids = set(PublisherMember.objects.values_list("group_id", flat=True)) - internal_ids

    pairs = (
        PublisherMember.objects.filter(group_id__in=role_group_ids, group__publisher_group__isnull=True)
        .values_list("publisher_id", "group_id")
        .distinct()
    )
    for publisher_id, group_id in list(pairs):
        shared = Group.objects.get(id=group_id)
        copy = Group.objects.create(name=f"publisher:{publisher_id}:{uuid.uuid4().hex}")
        copy.permissions.set(shared.permissions.all())
        PublisherGroup.objects.create(group=copy, publisher_id=publisher_id, name=shared.name)
        PublisherMember.objects.filter(publisher_id=publisher_id, group_id=group_id).update(group=copy)
        role_group_ids.add(copy.id)

    role_group_ids |= set(PublisherGroup.objects.values_list("group_id", flat=True))
    member_user_ids = PublisherMember.objects.values_list("user_id", flat=True)
    User.groups.through.objects.filter(user_id__in=member_user_ids, group_id__in=role_group_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("publishers", "0003_publishergroup"),
        ("users", "0002_user_preferred_language"),
    ]

    operations = [
        migrations.RunPython(copy_groups_per_publisher, migrations.RunPython.noop),
    ]
