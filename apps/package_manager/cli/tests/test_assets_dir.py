"""`assets_dir` in the manifest: where `itqan install` puts downloaded assets."""

from pathlib import Path

from click.testing import CliRunner
import pytest
import responses

from apps.package_manager.cli.exceptions import UnknownFieldError
from apps.package_manager.cli.main import cli
from apps.package_manager.cli.manifest import parse_manifest_content

REGISTRY = "https://cms.itqan.dev"


def _manifest(assets_dir_line: str = "") -> bytes:
    return f"""schema_version: 1
{assets_dir_line}
assets:
  tafsir:
    version: "^1.0.0"
""".encode()


def _mock_registry() -> None:
    responses.add(
        responses.POST,
        f"{REGISTRY}/packages/resolve/manifest/",
        json={
            "results": [
                {
                    "name": "tafsir",
                    "slug": "tafsir",
                    "language": "ar",
                    "asset_version_id": 1,
                    "resolved_version": "1.0.0",
                    "asset_name": "Tafsir",
                    "download_url": "https://cdn.itqan.dev/tafsir-ar-1.0.csv",
                }
            ]
        },
        status=200,
    )
    responses.add(responses.GET, "https://cdn.itqan.dev/tafsir-ar-1.0.csv", body=b"csv", status=200)


def _install(project: Path, *extra: str):
    return CliRunner().invoke(
        cli,
        [
            "install",
            "-m",
            str(project / "itqan-assets.yaml"),
            "-l",
            str(project / "itqan-assets.lock"),
            "--registry-url",
            REGISTRY,
            *extra,
        ],
    )


def test_parse_manifest_content_where_assets_dir_given_should_keep_it():
    # Arrange / Act
    manifest = parse_manifest_content(_manifest('assets_dir: "src/assets/quran"'))

    # Assert
    assert manifest.assets_dir == "src/assets/quran"


def test_parse_manifest_content_where_assets_dir_omitted_should_be_none():
    # Arrange / Act
    manifest = parse_manifest_content(_manifest())

    # Assert
    assert manifest.assets_dir is None


@pytest.mark.parametrize("value", ['"/etc/assets"', '"../outside"', '"assets/../../outside"', '"C:\\\\assets"', '""'])
def test_parse_manifest_content_where_assets_dir_escapes_project_should_raise(value: str):
    # Arrange
    content = _manifest(f"assets_dir: {value}")

    # Act / Assert
    with pytest.raises(UnknownFieldError, match="assets_dir"):
        parse_manifest_content(content)


def test_parse_manifest_content_where_assets_block_is_empty_should_have_no_assets():
    # Arrange
    content = b"""schema_version: 1
assets:
  # tafsir:
  #   version: "^1.0.0"
"""

    # Act
    manifest = parse_manifest_content(content)

    # Assert
    assert manifest.assets == {}


@responses.activate
def test_install_command_where_manifest_sets_assets_dir_should_install_there(tmp_path: Path):
    # Arrange
    (tmp_path / "itqan-assets.yaml").write_bytes(_manifest('assets_dir: "public/quran"'))
    _mock_registry()

    # Act
    result = _install(tmp_path)

    # Assert
    assert result.exit_code == 0, result.output
    assert (tmp_path / "public" / "quran" / "tafsir" / "tafsir-ar-1.0.csv").read_bytes() == b"csv"


@responses.activate
def test_install_command_where_assets_dir_omitted_should_install_next_to_manifest(tmp_path: Path):
    # Arrange
    (tmp_path / "itqan-assets.yaml").write_bytes(_manifest())
    _mock_registry()

    # Act
    result = _install(tmp_path)

    # Assert
    assert result.exit_code == 0, result.output
    assert (tmp_path / "assets" / "tafsir" / "tafsir-ar-1.0.csv").is_file()


@responses.activate
def test_install_command_where_flag_and_manifest_both_set_should_prefer_flag(tmp_path: Path):
    # Arrange
    (tmp_path / "itqan-assets.yaml").write_bytes(_manifest('assets_dir: "public/quran"'))
    _mock_registry()

    # Act
    result = _install(tmp_path, "--assets-dir", str(tmp_path / "vendor"))

    # Assert
    assert result.exit_code == 0, result.output
    assert (tmp_path / "vendor" / "tafsir" / "tafsir-ar-1.0.csv").is_file()
    assert not (tmp_path / "public").exists()
