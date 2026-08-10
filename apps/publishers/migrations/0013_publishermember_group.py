import django.db.models.deletion
from django.db import migrations, models

# Names duplicated from apps.publishers.services.publisher_member_service /
# apps.users.services.group on purpose: migrations must not import runtime code,
# whose constants may change independently of this historical migration.
PUBLISHER_MEMBER_GROUP = "Publisher Member"
PUBLISHER_ADMIN_GROUP = "Publisher Member Admin"
ROLE_TO_GROUP = {"admin": PUBLISHER_ADMIN_GROUP, "staff": PUBLISHER_MEMBER_GROUP}


def backfill_group_from_role(apps, schema_editor):
    """Map each member's role label onto the group that role used to grant.

    The seeded groups normally exist by now (publishers' post_migrate seeder), but
    on a fresh database this migration can run first, so create any that are
    missing. The post_migrate seeder attaches the permissions afterwards.
    """
    PublisherMember = apps.get_model("publishers", "PublisherMember")
    Group = apps.get_model("auth", "Group")

    roles_in_use = set(PublisherMember.objects.values_list("role", flat=True).distinct())
    if not roles_in_use:
        return

    group_ids = {}
    for role in roles_in_use:
        # Unknown roles fall back to the least-privileged group rather than failing the deploy.
        name = ROLE_TO_GROUP.get(role, PUBLISHER_MEMBER_GROUP)
        group, _ = Group.objects.get_or_create(name=name)
        group_ids[role] = group.id

    for role, group_id in group_ids.items():
        PublisherMember.objects.filter(role=role).update(group_id=group_id)


def restore_role_from_group(apps, schema_editor):
    PublisherMember = apps.get_model("publishers", "PublisherMember")
    PublisherMember.objects.filter(group__name=PUBLISHER_ADMIN_GROUP).update(role="admin")
    PublisherMember.objects.exclude(group__name=PUBLISHER_ADMIN_GROUP).update(role="staff")


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("publishers", "0012_publisher_auto_accept_access_requests"),
    ]

    operations = [
        # 1. Add nullable so existing rows survive the schema change.
        migrations.AddField(
            model_name="publishermember",
            name="group",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="publisher_memberships",
                to="auth.group",
            ),
        ),
        # 2. Backfill from the role labels before they are dropped.
        migrations.RunPython(backfill_group_from_role, restore_role_from_group),
        # 3. Enforce the real (non-null) shape.
        migrations.AlterField(
            model_name="publishermember",
            name="group",
            field=models.ForeignKey(
                help_text=(
                    "Permission group for this member. Applied to the user's groups on activation; "
                    "per-membership, so a user in several publishers keeps a distinct group for each."
                ),
                on_delete=django.db.models.deletion.PROTECT,
                related_name="publisher_memberships",
                to="auth.group",
            ),
        ),
        # 4. Drop role. Expressed as SeparateDatabaseAndState so that reversing it
        #    re-creates the column as nullable (the pre-0013 state has it NOT NULL
        #    with no default, which would fail against existing rows); the state
        #    operation still restores the original field for later migrations.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE "publishers_publishermember" DROP COLUMN "role"',
                    reverse_sql=('ALTER TABLE "publishers_publishermember" ADD COLUMN "role" varchar(20) NULL'),
                ),
            ],
            state_operations=[migrations.RemoveField(model_name="publishermember", name="role")],
        ),
    ]
