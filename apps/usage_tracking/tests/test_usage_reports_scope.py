from datetime import date

from apps.usage_tracking.models import UniqueScope
from apps.usage_tracking.services.usage_reports import ReportFilters, ReportScope, _monthly_scope

WEEK = {"start_date": date(2026, 10, 1), "end_date": date(2026, 10, 7)}


class TestMonthlyScope:
    def test_monthly_scope_where_asset_only_should_use_asset_uniques(self):
        # Act / Assert
        assert _monthly_scope(ReportScope("admin", "a"), ReportFilters(**WEEK, asset_id=5)) == (
            UniqueScope.ASSET,
            (5,),
        )

    def test_monthly_scope_where_asset_and_app_filter_should_have_no_stored_scope(self):
        # Act / Assert
        assert _monthly_scope(ReportScope("admin", "a"), ReportFilters(**WEEK, asset_id=5, app=9)) is None

    def test_monthly_scope_where_asset_in_app_restricted_scope_should_have_no_stored_scope(self):
        # Act / Assert
        assert _monthly_scope(ReportScope("developer", "d", app_ids=(9,)), ReportFilters(**WEEK, asset_id=5)) is None
