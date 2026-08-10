from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.db.models import QuerySet

ITQAN_INTERNAL_GROUP = "Itqan Internal"  # For Itqan staff only; holds every permission in the system.


class GroupRepository:
    def create(self, name: str) -> Group:
        return Group.objects.create(name=name)

    def get_by_id(self, group_id: int) -> Group | None:
        return Group.objects.filter(id=group_id).first()

    def assignable_qs(self) -> QuerySet[Group]:
        """Groups that may be listed or assigned through the portal APIs.

        Itqan Internal carries every permission in the system, so it is never
        offered for assignment nor exposed in the groups listing.
        """
        return Group.objects.exclude(name=ITQAN_INTERNAL_GROUP)

    def get_assignable_by_id(self, group_id: int) -> Group | None:
        return self.assignable_qs().filter(id=group_id).first()

    def name_exists(self, name: str, *, exclude_id: int | None = None) -> bool:
        qs = Group.objects.filter(name=name)
        if exclude_id is not None:
            qs = qs.exclude(id=exclude_id)
        return qs.exists()

    def rename(self, group: Group, name: str) -> Group:
        group.name = name
        group.save(update_fields=["name"])
        return group

    def set_permissions(self, group: Group, permissions: list[Permission]) -> Group:
        group.permissions.set(permissions)
        return group

    def delete(self, group: Group) -> None:
        group.delete()
