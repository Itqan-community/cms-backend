from datetime import UTC, datetime

from django.db import IntegrityError, transaction
import pytest

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import (
    TrafficChannel,
    TrafficEvent,
    TrafficHourly,
    TrafficKind,
    TrafficPlatform,
    TrafficStatusClass,
)

AT = datetime(2026, 10, 18, 10, 5, tzinfo=UTC)


def _event(ray_id: str) -> TrafficEvent:
    return TrafficEvent(
        ray_id=ray_id,
        occurred_at=AT,
        kind=TrafficKind.AUDIO_SURAH,
        asset_id=13,
        surah=1,
        country="SA",
        channel=TrafficChannel.APP_UNIDENTIFIED,
        platform=TrafficPlatform.ANDROID,
        status_class=TrafficStatusClass.FULL,
        listener_id="a" * 64,
        ua_family="dalvik",
    )


class TestTrafficModels(BaseTestCase):
    def test_traffic_event_where_ray_id_repeats_should_reject_duplicate(self):
        # Arrange
        _event("ray-1").save()

        # Act / Assert
        with pytest.raises(IntegrityError), transaction.atomic():
            _event("ray-1").save()

    def test_traffic_hourly_where_null_dimensions_repeat_should_reject_duplicate(self):
        # Arrange
        values = {
            "hour": AT.replace(minute=0),
            "asset_id": None,
            "kind": TrafficKind.API_CALL,
            "country": "SA",
            "channel": TrafficChannel.SCRIPT,
            "platform": TrafficPlatform.SERVER,
            "endpoint": "/recitations/",
        }
        TrafficHourly.objects.create(**values)

        # Act / Assert
        with pytest.raises(IntegrityError), transaction.atomic():
            TrafficHourly.objects.create(**values)
