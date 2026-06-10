from __future__ import annotations

from django.contrib.auth.models import Group, Permission


class GroupRepository:
    def create(self, name: str) -> Group:
        return Group.objects.create(name=name)

    def get_by_id(self, group_id: int) -> Group | None:
        return Group.objects.filter(id=group_id).first()

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
