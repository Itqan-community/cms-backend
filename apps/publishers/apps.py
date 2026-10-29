from django.apps import AppConfig

from apps.core.permissions import PermissionChoice


class PublishersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.publishers"

    def ready(self) -> None:
        from django.db.models.signals import post_migrate

        import apps.publishers.signals  # noqa: F401

        post_migrate.connect(_seed_itqan_internal_group, sender=self)


def _seed_group(group_name: str, codenames: list[str]) -> None:
    import logging

    from django.contrib.auth.models import Group, Permission

    logger = logging.getLogger(__name__)

    # Runs after plain_permissions' post_migrate sync, so the codenames exist by now.
    group, _ = Group.objects.get_or_create(name=group_name)
    perms = list(Permission.objects.filter(codename__in=codenames))
    if len(perms) != len(codenames):
        found = {p.codename for p in perms}
        missing = [codename for codename in codenames if codename not in found]
        logger.warning("Group %r seeded with missing permissions: %s", group_name, missing)
    group.permissions.set(perms)


def _seed_itqan_internal_group(sender, **kwargs) -> None:
    # Publisher roles are not seeded: each publisher's admins define their own groups in the
    # portal, and re-seeding them here on every migrate would wipe those edits each release.
    # Itqan Internal is safe to reset because the portal never exposes it for editing.
    from apps.publishers.services.publisher_member_service import ITQAN_INTERNAL_GROUP

    _seed_group(ITQAN_INTERNAL_GROUP, PermissionChoice.values)  # type: ignore[attr-defined]
