from django.test import SimpleTestCase
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.core.permission_utils import permission_class


class PermissionClassReprTest(SimpleTestCase):
    def test_permission_class_whereCalled_shouldNotAlterBuiltinPermissionReprs(self):
        # Arrange
        builtin_reprs = {"IsAuthenticated": repr(IsAuthenticated), "AllowAny": repr(AllowAny)}

        # Act
        permission_class("perm.one")
        permission_class("perm.two")

        # Assert: no global side effect on DRF's shared permission classes (see issue #456)
        self.assertEqual(builtin_reprs["IsAuthenticated"], repr(IsAuthenticated))
        self.assertEqual(builtin_reprs["AllowAny"], repr(AllowAny))

    def test_permission_class_whereCalled_shouldNameGeneratedClassAfterPermissionCode(self):
        # Act
        first = permission_class("perm.one")
        second = permission_class("perm.two")

        # Assert: each generated class is readable and distinguishable on its own
        self.assertIn("perm.one", repr(first))
        self.assertIn("perm.two", repr(second))
        self.assertNotEqual(repr(first), repr(second))
