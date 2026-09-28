"""End-to-end integration tests for the Itqan CLI commands (install and sync)."""

from pathlib import Path

from click.testing import CliRunner
import pytest
import responses

from apps.package_manager.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@responses.activate
def test_install_command_where_valid_manifest_and_api_responds_should_write_lockfile_and_materialize_assets(
    runner: CliRunner, tmp_path: Path
):
    manifest_path = tmp_path / "itqan-assets.yaml"
    lockfile_path = tmp_path / "itqan-assets.lock"
    assets_dir = tmp_path / "assets"
    registry_url = "https://api.itqan.dev/api"

    manifest_path.write_bytes(b"""schema_version: 1

assets:
  quran-uthmani-hafs:
    version: "^2.1.0"
""")

    # Mock Registry API
    responses.add(
        responses.POST,
        f"{registry_url}/packages/resolve/manifest/",
        json={
            "results": [
                {
                    "slug": "quran-uthmani-hafs",
                    "asset_version_id": 10,
                    "resolved_version": "2.4.1",
                    "asset_name": "Quran Hafs",
                    "download_url": "https://cdn.itqan.dev/assets/quran.pdf",
                }
            ]
        },
        status=200,
    )

    # Mock File Download
    responses.add(
        responses.GET,
        "https://cdn.itqan.dev/assets/quran.pdf",
        body=b"%PDF-1.4 dummy pdf bytes",
        status=200,
    )

    # 1. Run itqan install
    result = runner.invoke(
        cli,
        [
            "install",
            "--manifest",
            str(manifest_path),
            "--lockfile",
            str(lockfile_path),
            "--assets-dir",
            str(assets_dir),
            "--registry-url",
            registry_url,
            "--api-key",
            "test-api-key",
        ],
    )

    assert result.exit_code == 0
    assert "Success!" in result.output
    assert "Updated lockfile" in result.output

    # Verify lockfile written
    assert lockfile_path.is_file()
    lock_content = lockfile_path.read_text(encoding="utf-8")
    assert '"quran-uthmani-hafs":' in lock_content
    assert 'version: "2.4.1"' in lock_content

    # Verify asset file written
    target_asset = assets_dir / "quran-uthmani-hafs" / "quran.pdf"
    assert target_asset.is_file()
    assert target_asset.read_bytes() == b"%PDF-1.4 dummy pdf bytes"

    # 2. Run itqan sync (alias) again -> verify FRESH state & idempotency
    result_sync = runner.invoke(
        cli,
        [
            "sync",
            "--manifest",
            str(manifest_path),
            "--lockfile",
            str(lockfile_path),
            "--assets-dir",
            str(assets_dir),
            "--registry-url",
            registry_url,
            "--api-key",
            "test-api-key",
        ],
    )

    assert result_sync.exit_code == 0
    assert "Lockfile is FRESH" in result_sync.output
    assert "cached (up-to-date)" in result_sync.output


def test_install_command_where_manifest_file_absent_should_exit_with_code_1_and_clear_error(
    runner: CliRunner, tmp_path: Path
):
    non_existent = tmp_path / "itqan-assets.yaml"
    result = runner.invoke(cli, ["install", "--manifest", str(non_existent)])
    assert result.exit_code == 1
    assert "No manifest found" in result.output


@responses.activate
def test_install_command_where_registry_returns_401_should_exit_with_code_1_and_auth_error_message(
    runner: CliRunner, tmp_path: Path
):
    manifest_path = tmp_path / "itqan-assets.yaml"
    manifest_path.write_bytes(b"""schema_version: 1
assets:
  quran-uthmani-hafs:
    version: "^2.1.0"
""")
    registry_url = "https://api.itqan.dev/api"

    responses.add(
        responses.POST,
        f"{registry_url}/packages/resolve/manifest/",
        json={"error_name": "authentication_required", "message": "API key required"},
        status=401,
    )

    result = runner.invoke(
        cli,
        [
            "install",
            "--manifest",
            str(manifest_path),
            "--registry-url",
            registry_url,
        ],
    )
    assert result.exit_code == 1
    assert "Authentication required" in result.output
