from datetime import UTC, date, datetime
from unittest.mock import patch

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.repositories.traffic import TrafficRepository
from apps.usage_tracking.services.traffic_maintenance import add_months, run_usage_maintenance

NOW = datetime(2026, 1, 15, 3, 30, tzinfo=UTC)


class TestAddMonths:
    def test_add_months_where_crossing_year_should_wrap(self):
        # Act / Assert
        assert add_months(date(2026, 1, 1), -1) == date(2025, 12, 1)
        assert add_months(date(2026, 1, 1), -25) == date(2023, 12, 1)
        assert add_months(date(2025, 12, 1), 1) == date(2026, 1, 1)


class TestRunUsageMaintenance(BaseTestCase):
    def test_run_usage_maintenance_where_run_should_rebuild_two_months_and_purge_by_retention(self):
        # Arrange
        with (
            patch.object(TrafficRepository, TrafficRepository.rebuild_month_uniques.__name__) as rebuild,
            patch.object(TrafficRepository, TrafficRepository.purge_events_before.__name__, return_value=3) as purge,
            self.settings(USAGE_EVENT_RETENTION_MONTHS=25),
        ):
            # Act
            deleted = run_usage_maintenance(NOW)

        # Assert
        assert [call.args[0] for call in rebuild.call_args_list] == [date(2025, 12, 1), date(2026, 1, 1)]
        purge.assert_called_once_with(datetime(2023, 12, 1, tzinfo=UTC))
        assert deleted == 3
