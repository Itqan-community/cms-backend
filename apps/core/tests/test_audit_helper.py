"""Unit tests for apps.core.audit helpers (ITQ-34 / #432)."""

from django.db.models import F
import pytest

from apps.core.audit import update_with_history
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher


class UpdateWithHistoryHelperTest(BaseTestCase):
    def test_update_with_history_where_empty_queryset_should_return_zero(self):
        # Arrange: empty queryset of a tracked model
        qs = Publisher.objects.none()

        # Act: run update_with_history
        count = update_with_history(qs, name="New Name")

        # Assert: returns 0 and writes no history
        assert count == 0

    def test_update_with_history_where_records_exist_should_update_and_write_history(self):
        # Arrange: create tracked instances
        p1 = Publisher.objects.create(name="Publisher One", slug="pub-1")
        p2 = Publisher.objects.create(name="Publisher Two", slug="pub-2")
        initial_history_count = Publisher.history.count()

        # Act: bulk update via update_with_history
        qs = Publisher.objects.filter(id__in=[p1.id, p2.id])
        count = update_with_history(qs, name="Updated Publisher")

        # Assert: instances updated in default DB
        assert count == 2
        p1.refresh_from_db()
        p2.refresh_from_db()
        assert p1.name == "Updated Publisher"
        assert p2.name == "Updated Publisher"

        # Assert: historical records created in audit DB with update type (~)
        new_history = list(Publisher.history.order_by("-history_date")[:2])
        assert len(new_history) == 2
        assert all(h.history_type == "~" for h in new_history)
        assert all(h.name == "Updated Publisher" for h in new_history)
        assert Publisher.history.count() == initial_history_count + 2

    def test_update_with_history_where_f_expression_passed_should_raise_value_error(self):
        # Arrange: tracked publisher instance and F expression
        p = Publisher.objects.create(name="Publisher F", slug="pub-f")
        qs = Publisher.objects.filter(id=p.id)

        # Act & Assert: raises ValueError when F expression is passed
        with pytest.raises(ValueError, match="Expression values"):
            update_with_history(qs, name=F("name"))
