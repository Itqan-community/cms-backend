from types import SimpleNamespace

from django.test import RequestFactory, override_settings
from model_bakery import baker

from apps.content.models import Asset, AssetVersion, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import TrafficChannel, TrafficEvent, TrafficKind, TrafficSource
from apps.usage_tracking.services.install_events import record_installs


@override_settings(USAGE_IDENTITY_KEY="identity")
class TestRecordInstalls(BaseTestCase):
    def test_record_installs_where_cli_resolves_should_store_one_event_per_package(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.MUSHAF)
        version = baker.make(AssetVersion, asset=asset)
        result = SimpleNamespace(asset=asset, asset_version=version, asset_language=version.asset_language)
        request = RequestFactory().get(
            "/packages/resolve/x/",
            HTTP_USER_AGENT="itqan-cli/0.4.0",
            HTTP_X_ITQAN_INSTALL_ID="u-1",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
            HTTP_CF_IPCOUNTRY="SA",
        )
        request.auth = None

        # Act
        stored = record_installs(request, [result])

        # Assert
        event = TrafficEvent.objects.get()
        assert stored == 1
        assert (event.source, event.kind, event.channel, event.country) == (
            TrafficSource.DJANGO,
            TrafficKind.CLI_INSTALL,
            TrafficChannel.CLI,
            "SA",
        )
        assert (event.asset_id, event.asset_version_id, len(event.install_id)) == (asset.id, version.id, 64)
