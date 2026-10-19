from datetime import date

import pytest

from apps.core.ninja_utils.errors import ItqanError
from apps.usage_tracking.services.usage_reports import (
    ReportFilters,
    check_metric_kind,
    parse_tz,
    previous_period,
    validate_filters,
)


def _filters(start: date, end: date, **values) -> ReportFilters:
    return ReportFilters(start_date=start, end_date=end, **values)


class TestUsageReportParams:
    def test_validate_filters_where_end_before_start_should_raise_invalid_range(self):
        # Arrange
        filters = _filters(date(2026, 10, 10), date(2026, 10, 9))

        # Act
        with pytest.raises(ItqanError) as error:
            validate_filters(filters, granularity="day")

        # Assert
        assert error.value.error_name == "invalid_range"

    def test_validate_filters_where_range_over_limit_should_raise_range_too_large(self):
        # Arrange
        filters = _filters(date(2010, 1, 1), date(2026, 10, 9))

        # Act
        with pytest.raises(ItqanError) as error:
            validate_filters(filters, granularity="day")

        # Assert
        assert error.value.error_name == "range_too_large"

    def test_validate_filters_where_hourly_over_31_days_should_raise_range_too_large(self):
        # Arrange
        filters = _filters(date(2026, 9, 1), date(2026, 10, 9))

        # Act
        with pytest.raises(ItqanError) as error:
            validate_filters(filters, granularity="hour")

        # Assert
        assert error.value.error_name == "range_too_large"

    def test_validate_filters_where_start_before_2000_should_raise_invalid_range(self):
        # Arrange
        filters = _filters(date(1999, 12, 31), date(2000, 1, 2))

        # Act
        with pytest.raises(ItqanError) as error:
            validate_filters(filters, granularity="day")

        # Assert
        assert error.value.error_name == "invalid_range"

    def test_check_metric_kind_where_plays_for_version_files_should_raise(self):
        # Arrange
        filters = _filters(date(2026, 10, 1), date(2026, 10, 2), kind="version_file")

        # Act
        with pytest.raises(ItqanError) as error:
            check_metric_kind("plays", filters)

        # Assert
        assert error.value.error_name == "invalid_metric_for_kind"

    def test_check_metric_kind_where_requests_with_any_kind_should_pass(self):
        # Arrange
        filters = _filters(date(2026, 10, 1), date(2026, 10, 2), kind="version_file")

        # Act / Assert
        check_metric_kind("requests", filters)
        check_metric_kind("downloads", filters)

    def test_previous_period_where_week_should_return_the_week_before(self):
        # Act
        start, end = previous_period(date(2026, 10, 10), date(2026, 10, 16))

        # Assert
        assert (start, end) == (date(2026, 10, 3), date(2026, 10, 9))

    def test_parse_tz_where_unknown_should_raise_invalid_timezone(self):
        # Act
        with pytest.raises(ItqanError) as error:
            parse_tz("Mars/Base")

        # Assert
        assert error.value.error_name == "invalid_timezone"
        assert str(parse_tz("Asia/Riyadh")) == "Asia/Riyadh"
