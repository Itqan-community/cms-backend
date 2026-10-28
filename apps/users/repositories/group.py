from __future__ import annotations

import uuid

from django.contrib.auth.models import Group, Permission
from django.db.models import QuerySet

ITQAN_INTERNAL_GROUP = "Itqan Internal"  # For Itqan staff only; holds every permission in the system.


class GroupRepository:
    """Groups come in two kinds: publisher roles (with a ``PublisherGroup`` row, managed in the
    portal) and global groups (Itqan Internal, staff-only, managed in the Django admin)."""

    def create_for_publisher(self, publisher_id: int, name: str) -> Group:
        from apps.publishers.models import PublisherGroup

        # auth.Group.name is globally unique, so the role's own name lives on PublisherGroup.
        group = Group.objects.create(name=f"publisher:{publisher_id}:{uuid.uuid4().hex}")
        PublisherGroup.objects.create(group=group, publisher_id=publisher_id, name=name)
        return group

    def get_by_id(self, group_id: int) -> Group | None:
        return Group.objects.filter(id=group_id).first()

    def assignable_qs(self, publisher_id: int) -> QuerySet[Group]:
        """The roles ``publisher_id`` owns: the only groups listed or assigned through the portal."""
        return Group.objects.filter(publisher_group__publisher_id=publisher_id).select_related("publisher_group")

    def get_assignable_by_id(self, group_id: int, publisher_id: int) -> Group | None:
        return self.assignable_qs(publisher_id).filter(id=group_id).first()

    def name_exists(self, name: str, *, exclude_id: int | None = None, publisher_id: int | None = None) -> bool:
        """Whether ``name`` is taken among ``publisher_id``'s roles, or among all groups when None."""
        if publisher_id is not None:
            from apps.publishers.models import PublisherGroup

            qs = PublisherGroup.objects.filter(publisher_id=publisher_id, name=name)
            if exclude_id is not None:
                qs = qs.exclude(group_id=exclude_id)
            return qs.exists()
        qs = Group.objects.filter(name=name)
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return qs.exists()

    def rename(self, group: Group, name: str) -> Group:
        publisher_group = getattr(group, "publisher_group", None)
        if publisher_group is not None:
            publisher_group.name = name
            publisher_group.save(update_fields=["name"])
        else:
            group.name = name
            group.save(update_fields=["name"])
        return group

    def set_permissions(self, group: Group, permissions: list[Permission]) -> Group:
        group.permissions.set(permissions)
        return group

    def delete(self, group: Group) -> None:
        group.delete()
