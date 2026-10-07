"""CLI support for language renditions: `asset` / `language` manifest fields,
several languages of one asset, and their lockfile and install layout."""

import json
from pathlib import Path

from click.testing import CliRunner
import pytest
import responses

from apps.package_manager.cli.exceptions import DuplicateAssetEntryError, UnknownFieldError
from apps.package_manager.cli.lockfile import (
    AssetLockfile,
    LockfileEntry,
    LockfileState,
    evaluate_lockfile_state,
    parse_lockfile_content,
    serialize_lockfile,
)
from apps.package_manager.cli.main import cli
from apps.package_manager.cli.manifest import parse_manifest_content

TWO_LANGUAGE_MANIFEST = b"""schema_version: 1

assets:
  tafsir:
    version: "^2.0.0"
  tafsir-az:
    asset: tafsir
    language: az
    version: "^1.0.0"
"""


def test_parse_manifest_content_where_entry_sets_asset_and_language_should_parse_them():
    # Arrange / Act
    manifest = parse_manifest_content(TWO_LANGUAGE_MANIFEST)

    # Assert
    assert manifest.assets["tafsir"].asset == "tafsir"
    assert manifest.assets["tafsir"].language is None
    assert manifest.assets["tafsir-az"].asset == "tafsir"
    assert manifest.assets["tafsir-az"].language == "az"


def test_parse_manifest_content_where_two_entries_name_same_asset_and_language_should_raise():
    # Arrange
    content = b"""schema_version: 1
assets:
  tafsir:
    language: az
    version: "^1.0.0"
  tafsir-again:
    asset: tafsir
    language: az
    version: "^1.0.0"
"""

    # Act / Assert
    with pytest.raises(DuplicateAssetEntryError, match="tafsir"):
        parse_manifest_content(content)


def test_parse_manifest_content_where_language_is_empty_should_raise():
    # Arrange
    content = b"""schema_version: 1
assets:
  tafsir:
    language: ""
    version: "^1.0.0"
"""

    # Act / Assert
    with pytest.raises(UnknownFieldError, match="language"):
        parse_manifest_content(content)


def test_serialize_lockfile_where_entry_has_asset_and_language_should_round_trip():
    # Arrange
    lockfile = AssetLockfile(
        lockfile_version=1,
        manifest_schema_version=1,
        assets={
            "tafsir": LockfileEntry(slug="tafsir", constraint="^2.0.0", version="2.0.0"),
            "tafsir-az": LockfileEntry(
                slug="tafsir-az", constraint="^1.0.0", version="1.0.0", asset="tafsir", language="az"
            ),
        },
    )

    # Act
    raw = serialize_lockfile(lockfile)

    # Assert
    assert raw == (
        b"lockfile_version: 1\n"
        b"manifest_schema_version: 1\n"
        b"\n"
        b"assets:\n"
        b'  "tafsir":\n'
        b'    constraint: "^2.0.0"\n'
        b'    version: "2.0.0"\n'
        b'  "tafsir-az":\n'
        b'    asset: "tafsir"\n'
        b'    language: "az"\n'
        b'    constraint: "^1.0.0"\n'
        b'    version: "1.0.0"\n'
    )
    assert parse_lockfile_content(raw) == lockfile


def test_evaluate_lockfile_state_where_manifest_language_changed_should_be_stale(tmp_path: Path):
    # Arrange
    manifest_path = tmp_path / "itqan-assets.yaml"
    lockfile_path = tmp_path / "itqan-assets.lock"
    manifest_path.write_bytes(TWO_LANGUAGE_MANIFEST.replace(b"language: az", b"language: tr"))
    lockfile_path.write_bytes(
        serialize_lockfile(
            AssetLockfile(
                lockfile_version=1,
                manifest_schema_version=1,
                assets={
                    "tafsir": LockfileEntry(slug="tafsir", constraint="^2.0.0", version="2.0.0"),
                    "tafsir-az": LockfileEntry(
                        slug="tafsir-az", constraint="^1.0.0", version="1.0.0", asset="tafsir", language="az"
                    ),
                },
            )
        )
    )

    # Act
    state, _manifest, _lockfile = evaluate_lockfile_state(manifest_path, lockfile_path)

    # Assert
    assert state == LockfileState.STALE


@responses.activate
def test_install_command_where_manifest_lists_two_languages_should_install_each_into_its_own_folder(
    tmp_path: Path,
):
    # Arrange
    registry_url = "https://cms.itqan.dev"
    (tmp_path / "itqan-assets.yaml").write_bytes(TWO_LANGUAGE_MANIFEST)
    responses.add(
        responses.POST,
        f"{registry_url}/packages/resolve/manifest/",
        json={
            "results": [
                {
                    "name": "tafsir",
                    "slug": "tafsir",
                    "language": "ar",
                    "asset_version_id": 1,
                    "resolved_version": "2.0.0",
                    "asset_name": "Tafsir",
                    "download_url": "https://cdn.itqan.dev/tafsir-ar-2.0.csv",
                },
                {
                    "name": "tafsir-az",
                    "slug": "tafsir",
                    "language": "az",
                    "asset_version_id": 2,
                    "resolved_version": "1.0.0",
                    "asset_name": "Tafsir",
                    "download_url": f"{registry_url}/packages/download/2/tafsir-az-1.0.csv/",
                },
            ]
        },
        status=200,
    )
    responses.add(responses.GET, "https://cdn.itqan.dev/tafsir-ar-2.0.csv", body=b"ar", status=200)
    responses.add(responses.GET, f"{registry_url}/packages/download/2/tafsir-az-1.0.csv/", body=b"az", status=200)

    # Act
    result = CliRunner().invoke(
        cli,
        [
            "install",
            "-m",
            str(tmp_path / "itqan-assets.yaml"),
            "-l",
            str(tmp_path / "itqan-assets.lock"),
            "-d",
            str(tmp_path / "assets"),
            "--registry-url",
            registry_url,
        ],
    )

    # Assert
    assert result.exit_code == 0, result.output
    assert "* tafsir-az [1.0.0]: downloaded" in result.output
    assert (tmp_path / "assets" / "tafsir" / "tafsir-ar-2.0.csv").read_bytes() == b"ar"
    assert (tmp_path / "assets" / "tafsir-az" / "tafsir-az-1.0.csv").read_bytes() == b"az"
    sent = json.loads(responses.calls[0].request.body)
    assert sent == {
        "assets": {
            "tafsir": {"version": "^2.0.0"},
            "tafsir-az": {"version": "^1.0.0", "asset": "tafsir", "language": "az"},
        }
    }
    lock = parse_lockfile_content((tmp_path / "itqan-assets.lock").read_bytes())
    assert lock.assets["tafsir-az"].asset == "tafsir"
    assert lock.assets["tafsir-az"].language == "az"
    assert lock.assets["tafsir-az"].version == "1.0.0"
