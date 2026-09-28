"""Tests for Package Registry HTTP Client."""

import pytest
import responses

from apps.package_manager.cli.client import RegistryClient
from apps.package_manager.cli.exceptions import RegistryApiError


@responses.activate
def test_resolve_manifest_where_valid_constraints_should_return_resolved_assets():
    base_url = "https://api.itqan.dev/api"
    responses.add(
        responses.POST,
        f"{base_url}/packages/resolve/manifest/",
        json={
            "results": [
                {
                    "slug": "quran-uthmani-hafs",
                    "asset_version_id": 12,
                    "resolved_version": "2.4.1",
                    "asset_name": "Quran Hafs",
                    "download_url": "https://cdn.itqan.dev/assets/quran.zip",
                    "publisher_id": 1,
                    "publisher_name": "KAFD",
                }
            ]
        },
        status=200,
    )

    client = RegistryClient(base_url=base_url, api_key="secret-test-key")
    results = client.resolve_manifest({"quran-uthmani-hafs": "^2.1.0"})

    assert len(results) == 1
    assert results[0].slug == "quran-uthmani-hafs"
    assert results[0].resolved_version == "2.4.1"
    assert results[0].download_url == "https://cdn.itqan.dev/assets/quran.zip"


@responses.activate
def test_resolve_manifest_where_api_key_missing_should_raise_registry_api_error_401():
    base_url = "https://api.itqan.dev/api"
    responses.add(
        responses.POST,
        f"{base_url}/packages/resolve/manifest/",
        json={"error_name": "authentication_required", "message": "API key required"},
        status=401,
    )

    client = RegistryClient(base_url=base_url)
    with pytest.raises(RegistryApiError) as exc_info:
        client.resolve_manifest({"quran": "1.0.0"})

    assert exc_info.value.status_code == 401
    assert "Authentication required" in exc_info.value.message


@responses.activate
def test_resolve_manifest_where_asset_access_denied_should_raise_registry_api_error_403():
    base_url = "https://api.itqan.dev/api"
    responses.add(
        responses.POST,
        f"{base_url}/packages/resolve/manifest/",
        json={"error_name": "access_denied", "message": "No active license"},
        status=403,
    )

    client = RegistryClient(base_url=base_url, api_key="valid-key")
    with pytest.raises(RegistryApiError) as exc_info:
        client.resolve_manifest({"restricted-asset": "1.0.0"})

    assert exc_info.value.status_code == 403
    assert "Access denied" in exc_info.value.message


@responses.activate
def test_resolve_manifest_where_no_version_satisfies_constraint_should_raise_registry_api_error_422():
    base_url = "https://api.itqan.dev/api"
    responses.add(
        responses.POST,
        f"{base_url}/packages/resolve/manifest/",
        json={"error_name": "unsatisfiable_version_constraint", "message": "No matching version"},
        status=422,
    )

    client = RegistryClient(base_url=base_url)
    with pytest.raises(RegistryApiError) as exc_info:
        client.resolve_manifest({"quran": "^99.0.0"})

    assert exc_info.value.status_code == 422
    assert "Cannot satisfy version constraints" in exc_info.value.message
