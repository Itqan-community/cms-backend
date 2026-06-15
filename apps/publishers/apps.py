from django.apps import AppConfig


class PublishersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.publishers"

    def ready(self) -> None:
        from django.db.models.signals import post_migrate

        import apps.publishers.signals  # noqa: F401

        post_migrate.connect(_seed_publisher_member_admin_group, sender=self)


def _seed_publisher_member_admin_group(sender, **kwargs) -> None:
    import logging

    from django.contrib.auth.models import Group, Permission

    from apps.publishers.services.publisher_member_service import PUBLISHER_ADMIN_GROUP

    logger = logging.getLogger(__name__)

    ADMIN_PERMS = [
        "portal_access",
        "portal_view_publisher_members",
        "portal_invite_publisher_members",
        "portal_update_publisher_members",
        "portal_delete_publisher_members",
    ]

    # Runs after plain_permissions' post_migrate sync, so the codenames exist by now.
    group, _ = Group.objects.get_or_create(name=PUBLISHER_ADMIN_GROUP)
    perms = list(Permission.objects.filter(codename__in=ADMIN_PERMS))
    if len(perms) != len(ADMIN_PERMS):
        found = {p.codename for p in perms}
        missing = [codename for codename in ADMIN_PERMS if codename not in found]
        logger.warning("Publisher admin group seeded with missing permissions: %s", missing)
    group.permissions.set(perms)
