from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from apps.publishers.models import Domain, Publisher, PublisherGroup


@receiver(post_save, sender=Domain)
@receiver(post_delete, sender=Domain)
def clear_domain_cache(sender: type[Domain], instance: Domain, **kwargs: object) -> None:
    cache.delete(f"x_tenant-{instance.domain}")


@receiver(post_delete, sender=PublisherGroup)
def delete_auth_group(sender: type[PublisherGroup], instance: PublisherGroup, **kwargs: object) -> None:
    # The auth.Group only backs this publisher role, so it goes with the role. While a publisher
    # is being deleted its members may not be gone yet (they PROTECT the group); the publisher's
    # own post_delete below sweeps those groups once the whole cascade has run.
    Group.objects.filter(id=instance.group_id, publisher_memberships__isnull=True).delete()


@receiver(pre_delete, sender=Publisher)
def remember_publisher_groups(sender: type[Publisher], instance: Publisher, **kwargs: object) -> None:
    instance._publisher_group_ids = list(
        PublisherGroup.objects.filter(publisher=instance).values_list("group_id", flat=True)
    )


@receiver(post_delete, sender=Publisher)
def delete_publisher_auth_groups(sender: type[Publisher], instance: Publisher, **kwargs: object) -> None:
    group_ids = getattr(instance, "_publisher_group_ids", None)
    if group_ids:
        Group.objects.filter(id__in=group_ids).delete()
