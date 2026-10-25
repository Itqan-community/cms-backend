from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import override_settings

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import (
    R2ObjectReadsHourly,
    TrafficChannel,
    TrafficEvent,
    TrafficKind,
    TrafficPlatform,
    TrafficStatusClass,
)
from apps.usage_tracking.services import r2_reads_client, r2_reconciliation
from apps.usage_tracking.services.r2_reads_client import R2ReadsClient
from apps.usage_tracking.services.r2_reconciliation import reconcile_r2_reads

NOW = datetime(2026, 10, 18, 12, 40, tzinfo=UTC)
# Last complete hour reconciled: floor(12:40 - 3 h) = 09:00 is the exclusive end, so 08:00.
H8 = datetime(2026, 10, 18, 8, tzinfo=UTC)
KEY = "media/uploads/assets/13/recitations/091.mp3"


class TestR2ReadsClient:
    def test_fetch_reads_where_groups_returned_should_sum_successful_reads_per_object(self):
        # Arrange
        groups = [
            {"sum": {"requests": 5}, "dimensions": {"objectName": KEY, "actionStatus": "success"}},
            {"sum": {"requests": 2}, "dimensions": {"objectName": KEY, "actionStatus": "userError"}},
        ]
        response = MagicMock()
        response.json.return_value = {"data": {"viewer": {"accounts": [{"r2OperationsAdaptiveGroups": groups}]}}}

        # Act
        with patch.object(r2_reads_client.requests, r2_reads_client.requests.post.__name__, return_value=response):
            reads, truncated = R2ReadsClient("acc", "token").fetch_reads("bucket", H8, H8 + timedelta(hours=1))

        # Assert
        assert (reads, truncated) == ({KEY: 5}, False)


@override_settings(
    ENABLE_USAGE_R2_RECONCILIATION=True,
    CF_ACCOUNT_ID="acc",
    USAGE_ANALYTICS_API_TOKEN="token",
    CLOUDFLARE_R2_BUCKET="assets",
)
class TestReconcile(BaseTestCase):
    def test_reconcile_r2_reads_where_reads_exceed_edge_should_store_both_counts(self):
        # Arrange
        TrafficEvent.objects.create(
            ray_id="r1",
            occurred_at=H8 + timedelta(minutes=5),
            kind=TrafficKind.AUDIO_SURAH,
            asset_id=13,
            surah=91,
            country="SA",
            channel=TrafficChannel.WEB,
            platform=TrafficPlatform.WEB,
            status_class=TrafficStatusClass.FULL,
            listener_id="a" * 64,
            ua_family="browser",
            path="/" + KEY,
        )
        client = MagicMock(spec=R2ReadsClient)
        client.fetch_reads.side_effect = lambda bucket, start, end: (({KEY: 3}, False) if start == H8 else ({}, False))

        # Act
        with patch.object(r2_reconciliation, r2_reconciliation._build_client.__name__, return_value=client):
            result = reconcile_r2_reads(NOW)

        # Assert
        row = R2ObjectReadsHourly.objects.get(hour=H8)
        assert (row.asset_id, row.reads, row.edge_requests) == (13, 3, 1)
        assert result.error == ""
        assert result.hours == 24  # refresh window: the 24 complete hours ending 3 h before now

    def test_reconcile_r2_reads_where_disabled_should_do_nothing(self):
        # Act
        with self.settings(ENABLE_USAGE_R2_RECONCILIATION=False):
            result = reconcile_r2_reads(NOW)

        # Assert
        assert result.hours == 0
