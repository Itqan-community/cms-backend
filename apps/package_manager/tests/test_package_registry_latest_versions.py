"""`latest_version` and `latest_in_range` on resolve results, which the `itqan`
CLI uses to tell users a newer version of an installed asset exists."""

from apps.content.models import AssetVersion
from apps.content.tests.publishing import publish
from apps.package_manager.tests.test_package_registry_withdrawal import WithdrawalBaseTest


class LatestVersionsTests(WithdrawalBaseTest):
    def _resolve_manifest(self, assets: dict):
        return self.client.post("/packages/resolve/manifest/", data={"assets": assets}, content_type="application/json")

    def _mushaf_versions(self, *names: str) -> list[AssetVersion]:
        return [self._commit(name, asset=self.mushaf) for name in names]

    def test_resolve_package_manifest_where_lockfile_pin_has_constraint_should_report_latest_in_range_and_overall(
        self,
    ):
        # Arrange
        self._mushaf_versions("1.0.0", "1.2.0", "2.0.0")

        # Act
        response = self._resolve_manifest({"m1": {"version": "1.0.0", "constraint": "^1.0.0"}})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        result = response.json()["results"][0]
        self.assertEqual("1.0.0", result["resolved_version"])
        self.assertEqual("1.2.0", result["latest_in_range"])
        self.assertEqual("2.0.0", result["latest_version"])

    def test_resolve_package_manifest_where_range_requested_should_report_resolved_as_latest_in_range(self):
        # Arrange
        self._mushaf_versions("1.0.0", "1.2.0", "2.0.0")

        # Act
        response = self._resolve_manifest({"m1": "^1.0.0"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        result = response.json()["results"][0]
        self.assertEqual("1.2.0", result["resolved_version"])
        self.assertEqual("1.2.0", result["latest_in_range"])
        self.assertEqual("2.0.0", result["latest_version"])

    def test_resolve_package_manifest_where_exact_pin_without_constraint_should_leave_latest_in_range_null(self):
        # Arrange
        self._mushaf_versions("1.0.0", "1.2.0")

        # Act
        response = self._resolve_manifest({"m1": "1.0.0"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        result = response.json()["results"][0]
        self.assertIsNone(result["latest_in_range"])
        self.assertEqual("1.2.0", result["latest_version"])

    def test_resolve_package_manifest_where_constraint_is_invalid_should_still_resolve_with_null_latest_in_range(
        self,
    ):
        # Arrange
        self._mushaf_versions("1.0.0")

        # Act
        response = self._resolve_manifest({"m1": {"version": "1.0.0", "constraint": "not-a-range"}})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNone(response.json()["results"][0]["latest_in_range"])

    def test_resolve_package_manifest_where_newer_versions_were_withdrawn_should_not_report_them_as_latest(self):
        # Arrange
        v1 = publish(self._commit("1.0"))
        publish(self._commit("1.1"))
        publish(self._commit("1.2"))
        self.assertEqual(200, self._roll_back(v1).status_code)
        self.client.logout()

        # Act
        response = self._resolve_manifest({"t1": {"version": "1.0.0", "constraint": "^1.0.0", "language": "fr"}})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        result = response.json()["results"][0]
        self.assertEqual("1.0.0", result["latest_in_range"])
        self.assertEqual("1.0.0", result["latest_version"])

    def test_resolve_package_single_where_range_requested_should_report_latest_versions(self):
        # Arrange
        self._mushaf_versions("1.0.0", "2.0.0")

        # Act
        response = self._resolve("m1", "~1.0")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        result = response.json()["result"]
        self.assertEqual("1.0.0", result["latest_in_range"])
        self.assertEqual("2.0.0", result["latest_version"])
