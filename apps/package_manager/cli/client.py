"""Package Registry HTTP client for resolving manifests and obtaining download URLs."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from apps.package_manager.cli.exceptions import RegistryApiError


@dataclass(frozen=True, slots=True)
class ResolvedAssetPayload:
    slug: str
    asset_version_id: int
    resolved_version: str
    asset_name: str
    download_url: str | None
    publisher_id: int | None = None
    publisher_name: str | None = None


class RegistryClient:
    """HTTP Client for Itqan Package Registry API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api",
        api_key: str | None = None,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "itqan-cli/1.0",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def resolve_manifest(self, assets: dict[str, str]) -> list[ResolvedAssetPayload]:
        """Call POST /packages/resolve/manifest/ to resolve manifest constraints.

        Args:
            assets: dict of slug -> constraint string (e.g. {"quran": "^2.1.0"})

        Returns:
            list of ResolvedAssetPayload

        Raises:
            RegistryApiError on any failure.
        """
        url = f"{self.base_url}/packages/resolve/manifest/"
        payload = {"assets": assets}

        try:
            response = self.session.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RegistryApiError(f"Failed to connect to package registry at {self.base_url}: {exc}") from exc

        if response.status_code == 200:
            try:
                data = response.json()
                results_raw = data.get("results", [])
                return [
                    ResolvedAssetPayload(
                        slug=item["slug"],
                        asset_version_id=item["asset_version_id"],
                        resolved_version=item["resolved_version"],
                        asset_name=item["asset_name"],
                        download_url=item.get("download_url"),
                        publisher_id=item.get("publisher_id"),
                        publisher_name=item.get("publisher_name"),
                    )
                    for item in results_raw
                ]
            except Exception as exc:
                raise RegistryApiError(f"Failed to parse registry API response: {exc}") from exc

        # Handle API Error responses
        status_code = response.status_code
        error_name: str | None = None
        message = f"Registry request failed with status {status_code}"

        try:
            err_data = response.json()
            if isinstance(err_data, dict):
                error_name = err_data.get("error_name") or err_data.get("error")
                message = err_data.get("message") or err_data.get("detail") or message
        except Exception:
            message = response.text or message

        if status_code == 401:
            friendly_msg = f"Authentication required (API key missing or invalid): {message}"
        elif status_code == 403:
            friendly_msg = f"Access denied for requested assets (license required): {message}"
        elif status_code == 404:
            friendly_msg = f"Asset or version not found in registry: {message}"
        elif status_code == 422:
            friendly_msg = f"Cannot satisfy version constraints: {message}"
        else:
            friendly_msg = f"Registry API error [{status_code}]: {message}"

        raise RegistryApiError(
            friendly_msg,
            status_code=status_code,
            error_name=error_name,
        )
