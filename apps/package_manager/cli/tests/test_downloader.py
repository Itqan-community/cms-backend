"""Tests for AssetDownloader idempotency and atomic materialization."""

from pathlib import Path

import pytest
import responses

from apps.package_manager.cli.client import ResolvedAssetPayload
from apps.package_manager.cli.downloader import AssetDownloader
from apps.package_manager.cli.exceptions import DownloadError


@responses.activate
def test_materialize_asset_where_file_not_yet_present_should_download_then_skip_on_second_call(
    tmp_path: Path,
):
    assets_dir = tmp_path / "assets"
    downloader = AssetDownloader(assets_dir=assets_dir)

    asset = ResolvedAssetPayload(
        slug="quran-uthmani-hafs",
        asset_version_id=1,
        resolved_version="2.4.1",
        asset_name="Quran Hafs",
        download_url="https://cdn.itqan.dev/quran.zip",
    )

    responses.add(
        responses.GET,
        "https://cdn.itqan.dev/quran.zip",
        body=b"dummy zip content here",
        status=200,
    )

    # 1. First run: downloads file
    res1 = downloader.materialize_asset(asset)
    assert res1.downloaded is True
    assert res1.target_path.is_file()
    assert res1.target_path.read_bytes() == b"dummy zip content here"
    assert len(responses.calls) == 1

    # 2. Second run: idempotency (skips download)
    res2 = downloader.materialize_asset(asset)
    assert res2.downloaded is False
    assert len(responses.calls) == 1  # No second HTTP call made!


@responses.activate
def test_materialize_asset_where_server_returns_500_should_raise_download_error_and_leave_no_files(
    tmp_path: Path,
):
    assets_dir = tmp_path / "assets"
    downloader = AssetDownloader(assets_dir=assets_dir)

    asset = ResolvedAssetPayload(
        slug="failing-pkg",
        asset_version_id=2,
        resolved_version="1.0.0",
        asset_name="Failing Asset",
        download_url="https://cdn.itqan.dev/failing.zip",
    )

    responses.add(
        responses.GET,
        "https://cdn.itqan.dev/failing.zip",
        status=500,
    )

    with pytest.raises(DownloadError):
        downloader.materialize_asset(asset)

    # Verify no temp or target file left behind
    slug_dir = assets_dir / "failing-pkg"
    if slug_dir.exists():
        files = list(slug_dir.iterdir())
        assert len(files) == 0
