from django.test import SimpleTestCase
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice


class PermissionClassReprTest(SimpleTestCase):
    def test_permission_class_where_called_should_not_pollute_built_in_permission_reprs(self):
        # Arrange
        repr_before = repr(IsAuthenticated)

        # Act
        permission_class(PermissionChoice.PORTAL_READ_RECITER)
        permission_class(PermissionChoice.PORTAL_CREATE_RECITER)

        # Assert
        self.assertEqual(repr(IsAuthenticated), repr_before)

    def test_permission_class_where_called_should_not_change_allow_any_repr(self):
        # Arrange
        repr_before = repr(AllowAny)

        # Act
        permission_class(PermissionChoice.PORTAL_READ_MUSHAF)

        # Assert
        self.assertEqual(repr(AllowAny), repr_before)

    def test_permission_class_where_created_should_embed_permission_code_in_its_own_name(self):
        # Act
        klass = permission_class(PermissionChoice.PORTAL_READ_RECITER)

        # Assert
        self.assertEqual(klass.__name__, f"Permission({PermissionChoice.PORTAL_READ_RECITER})")
        self.assertIn(f"Permission({PermissionChoice.PORTAL_READ_RECITER})", repr(klass))

    def test_permission_class_where_created_should_keep_permission_code_name_attribute(self):
        # Act
        klass = permission_class(PermissionChoice.PORTAL_READ_RECITER)

        # Assert
        self.assertEqual(klass.permission_code_name, PermissionChoice.PORTAL_READ_RECITER)
