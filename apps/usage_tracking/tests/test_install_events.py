from types import SimpleNamespace

from django.db import connection
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import Asset, AssetLanguage, AssetVersion, CategoryChoice
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


@override_settings(USAGE_IDENTITY_KEY="identity")
class TestRecordInstallsUpdates(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(Asset, category=CategoryChoice.MUSHAF)
        self.arabic = baker.make(AssetLanguage, asset=self.asset, language="ar")
        self.english = baker.make(AssetLanguage, asset=self.asset, language="en")
        self.v1 = baker.make(AssetVersion, asset=self.asset, asset_language=self.arabic)
        self.v2 = baker.make(AssetVersion, asset=self.asset, asset_language=self.arabic)
        self.en_v1 = baker.make(AssetVersion, asset=self.asset, asset_language=self.english)

    def _resolve(self, version: AssetVersion, install_id: str = "u-1", command: str = "install") -> None:
        headers = {"HTTP_USER_AGENT": "itqan-cli/0.5.0", "HTTP_X_ITQAN_COMMAND": command}
        if install_id:
            headers["HTTP_X_ITQAN_INSTALL_ID"] = install_id
        request = RequestFactory().get("/packages/resolve/manifest/", **headers)
        request.auth = None
        result = SimpleNamespace(asset=self.asset, asset_version=version, asset_language=version.asset_language)
        record_installs(request, [result])

    def _kinds(self) -> list[str]:
        return list(TrafficEvent.objects.order_by("id").values_list("kind", flat=True))

    def test_record_installs_where_installation_had_another_version_should_store_update(self):
        # Arrange
        self._resolve(self.v1)

        # Act
        self._resolve(self.v2)

        # Assert
        assert self._kinds() == [TrafficKind.CLI_INSTALL, TrafficKind.CLI_UPDATE]

    def test_record_installs_where_installation_had_same_version_should_store_install(self):
        # Arrange
        self._resolve(self.v1)

        # Act
        self._resolve(self.v1)

        # Assert
        assert self._kinds() == [TrafficKind.CLI_INSTALL, TrafficKind.CLI_INSTALL]

    def test_record_installs_where_latest_version_matches_after_update_should_store_install(self):
        # Arrange
        self._resolve(self.v1)
        self._resolve(self.v2)

        # Act
        self._resolve(self.v2)

        # Assert
        assert self._kinds() == [TrafficKind.CLI_INSTALL, TrafficKind.CLI_UPDATE, TrafficKind.CLI_INSTALL]

    def test_record_installs_where_other_language_of_asset_should_store_install(self):
        # Arrange
        self._resolve(self.v1)

        # Act
        self._resolve(self.en_v1)

        # Assert
        assert self._kinds() == [TrafficKind.CLI_INSTALL, TrafficKind.CLI_INSTALL]

    def test_record_installs_where_other_installation_should_store_install(self):
        # Arrange
        self._resolve(self.v1, install_id="u-1")

        # Act
        self._resolve(self.v2, install_id="u-2")

        # Assert
        assert self._kinds() == [TrafficKind.CLI_INSTALL, TrafficKind.CLI_INSTALL]

    def test_record_installs_where_no_install_id_should_store_install(self):
        # Arrange
        self._resolve(self.v1, install_id="")

        # Act
        self._resolve(self.v2, install_id="")

        # Assert
        assert self._kinds() == [TrafficKind.CLI_INSTALL, TrafficKind.CLI_INSTALL]

    def test_record_installs_where_outdated_command_should_store_nothing(self):
        # Arrange
        self._resolve(self.v1)

        # Act
        self._resolve(self.v2, command="outdated")

        # Assert
        assert self._kinds() == [TrafficKind.CLI_INSTALL]

    def test_record_installs_where_many_packages_should_use_constant_queries(self):
        # Arrange
        self._resolve(self.v1)
        request = RequestFactory().get(
            "/packages/resolve/manifest/", HTTP_USER_AGENT="itqan-cli/0.5.0", HTTP_X_ITQAN_INSTALL_ID="u-1"
        )
        request.auth = None
        results = [
            SimpleNamespace(asset=self.asset, asset_version=version, asset_language=version.asset_language)
            for version in (self.v2, self.en_v1)
        ]

        # Act
        with CaptureQueriesContext(connection) as queries:
            record_installs(request, results)

        # Assert
        assert len(queries) == 2  # earlier versions of this installation, then one insert
        assert self._kinds() == [TrafficKind.CLI_INSTALL, TrafficKind.CLI_UPDATE, TrafficKind.CLI_INSTALL]
