from datetime import UTC, datetime

from django.urls import reverse
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.users.admin import UserAdmin
from apps.users.models import User


class UserAdminChangelistTest(BaseTestCase):
    def setUp(self) -> None:
        self.superuser = baker.make(User, email="admin@example.com", is_staff=True, is_superuser=True)
        self.changelist_url = reverse("admin:users_user_changelist")
        # The changelist ?o= index counts the action checkbox column Django prepends.
        self.date_joined_index = UserAdmin.list_display.index("date_joined") + 1

    def _make_user_joined_at(self, email: str, joined_at: datetime) -> User:
        user = baker.make(User, email=email)
        # created_at is auto_now_add, so it can only be backdated after the insert.
        User.objects.filter(pk=user.pk).update(created_at=joined_at)
        return user

    def test_changelist_where_listing_users_should_show_date_joined_column(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)

        # Act
        response = self.client.get(self.changelist_url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertContains(response, "column-date_joined")
        self.assertContains(response, "Date joined")

    def test_changelist_where_ordered_by_date_joined_descending_should_list_newest_first(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)
        User.objects.filter(pk=self.superuser.pk).update(created_at=datetime(2020, 1, 1, tzinfo=UTC))
        oldest = self._make_user_joined_at("oldest@example.com", datetime(2024, 1, 1, tzinfo=UTC))
        newest = self._make_user_joined_at("newest@example.com", datetime(2026, 1, 1, tzinfo=UTC))
        middle = self._make_user_joined_at("middle@example.com", datetime(2025, 1, 1, tzinfo=UTC))

        # Act
        response = self.client.get(self.changelist_url, {"o": f"-{self.date_joined_index}"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        listed = [user.pk for user in response.context["cl"].result_list]
        self.assertEqual([newest.pk, middle.pk, oldest.pk, self.superuser.pk], listed)

    def test_changelist_where_ordered_by_date_joined_ascending_should_list_oldest_first(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)
        User.objects.filter(pk=self.superuser.pk).update(created_at=datetime(2020, 1, 1, tzinfo=UTC))
        newest = self._make_user_joined_at("newest@example.com", datetime(2026, 1, 1, tzinfo=UTC))
        oldest = self._make_user_joined_at("oldest@example.com", datetime(2024, 1, 1, tzinfo=UTC))

        # Act
        response = self.client.get(self.changelist_url, {"o": str(self.date_joined_index)})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        listed = [user.pk for user in response.context["cl"].result_list]
        self.assertEqual([self.superuser.pk, oldest.pk, newest.pk], listed)
