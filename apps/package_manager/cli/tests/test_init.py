"""`itqan init`: write a starter itqan-assets.yaml from the live catalog."""

from pathlib import Path

from click.testing import CliRunner
import requests
import responses
from responses import matchers

from apps.package_manager.cli.main import cli
from apps.package_manager.cli.manifest import parse_manifest_content

REGISTRY = "https://cms.itqan.dev"

MULTILINGUAL = {
    "slug": "tafsir-jalalayn",
    "name": "Tafsir al-Jalalayn",
    "category": "tafsir",
    "is_open_access": True,
    "publisher_name": "Publisher",
    "languages": [
        {"language": "ar", "is_source": True, "latest_version": "2.4.0"},
        {"language": "en", "is_source": False, "latest_version": "1.3.0"},
    ],
}
SINGLE = {
    "slug": "mushaf-madinah",
    "name": "Mushaf Madinah",
    "category": "mushaf",
    "is_open_access": True,
    "publisher_name": "Publisher",
    "languages": [{"language": "ar", "is_source": True, "latest_version": "1.0.0"}],
}
TRANSLATION_ONLY = {
    "slug": "true",
    "name": "Only a translation",
    "category": "translation",
    "is_open_access": True,
    "publisher_name": None,
    "languages": [{"language": "fr", "is_source": False, "latest_version": "0.2.0-beta.1"}],
}


def _mock_catalog(results: list[dict], *, query: dict | None = None) -> None:
    responses.add(
        responses.GET,
        f"{REGISTRY}/packages/",
        json={"results": results, "count": len(results)},
        status=200,
        match=[matchers.query_param_matcher(query or {"page_size": "50", "open_access": "true"})],
    )


def _init(project: Path, *extra: str):
    return CliRunner().invoke(
        cli, ["init", "-m", str(project / "itqan-assets.yaml"), "--registry-url", REGISTRY, *extra]
    )


@responses.activate
def test_init_command_where_catalog_has_assets_should_write_entries_with_language_comments(tmp_path: Path):
    # Arrange
    _mock_catalog([SINGLE, MULTILINGUAL])

    # Act
    result = _init(tmp_path)

    # Assert
    assert result.exit_code == 0, result.output
    text = (tmp_path / "itqan-assets.yaml").read_text()
    assert "# Tafsir al-Jalalayn — languages: ar (source, 2.4.0), en (1.3.0)" in text
    assert "# Mushaf Madinah — languages: ar (source, 1.0.0)" in text
    manifest = parse_manifest_content(text.encode())
    assert manifest.assets_dir == "assets"
    assert list(manifest.assets) == ["tafsir-jalalayn", "tafsir-jalalayn-en", "mushaf-madinah"]
    assert manifest.assets["tafsir-jalalayn"].version == "^2.4.0"
    assert manifest.assets["tafsir-jalalayn"].language is None
    english = manifest.assets["tafsir-jalalayn-en"]
    assert (english.asset, english.language, english.version) == ("tafsir-jalalayn", "en", "^1.3.0")
    assert "Created" in result.output
    assert "itqan install" in result.output


@responses.activate
def test_init_command_where_only_a_translation_is_available_should_set_its_language(tmp_path: Path):
    # Arrange
    _mock_catalog([TRANSLATION_ONLY])

    # Act
    result = _init(tmp_path)

    # Assert
    assert result.exit_code == 0, result.output
    manifest = parse_manifest_content((tmp_path / "itqan-assets.yaml").read_bytes())
    entry = manifest.assets["true"]
    assert entry.language == "fr"
    assert entry.version == "0.2.0-beta.1"  # a prerelease is pinned exactly; ^ would never match it


@responses.activate
def test_init_command_where_assets_dir_given_should_write_it(tmp_path: Path):
    # Arrange
    _mock_catalog([SINGLE])

    # Act
    result = _init(tmp_path, "--assets-dir", "public/quran")

    # Assert
    assert result.exit_code == 0, result.output
    manifest = parse_manifest_content((tmp_path / "itqan-assets.yaml").read_bytes())
    assert manifest.assets_dir == "public/quran"


@responses.activate
def test_init_command_where_api_key_given_should_not_limit_to_open_access(tmp_path: Path, monkeypatch):
    # Arrange
    monkeypatch.setenv("ITQAN_API_KEY", "key")
    _mock_catalog([SINGLE], query={"page_size": "50"})

    # Act
    result = _init(tmp_path)

    # Assert
    assert result.exit_code == 0, result.output
    assert responses.calls[0].request.headers["X-API-Key"] == "key"


@responses.activate
def test_init_command_where_registry_unreachable_should_write_commented_template(tmp_path: Path):
    # Arrange
    responses.add(responses.GET, f"{REGISTRY}/packages/", body=requests.ConnectionError("offline"))

    # Act
    result = _init(tmp_path)

    # Assert
    assert result.exit_code == 0, result.output
    assert "Could not reach the registry" in result.output
    text = (tmp_path / "itqan-assets.yaml").read_text()
    assert '#   language: "en"' in text
    manifest = parse_manifest_content(text.encode())
    assert manifest.assets == {}
    assert manifest.assets_dir == "assets"


@responses.activate
def test_init_command_where_catalog_is_empty_should_write_commented_template(tmp_path: Path):
    # Arrange
    _mock_catalog([])

    # Act
    result = _init(tmp_path)

    # Assert
    assert result.exit_code == 0, result.output
    assert "no installable assets" in result.output
    assert parse_manifest_content((tmp_path / "itqan-assets.yaml").read_bytes()).assets == {}


def test_init_command_where_manifest_exists_should_refuse_and_keep_it(tmp_path: Path):
    # Arrange
    manifest_path = tmp_path / "itqan-assets.yaml"
    manifest_path.write_text("original")

    # Act
    result = _init(tmp_path)

    # Assert
    assert result.exit_code == 1
    assert "already exists" in result.output
    assert manifest_path.read_text() == "original"


@responses.activate
def test_init_command_where_manifest_exists_and_force_should_overwrite(tmp_path: Path):
    # Arrange
    manifest_path = tmp_path / "itqan-assets.yaml"
    manifest_path.write_text("original")
    _mock_catalog([SINGLE])

    # Act
    result = _init(tmp_path, "--force")

    # Assert
    assert result.exit_code == 0, result.output
    assert "mushaf-madinah" in parse_manifest_content(manifest_path.read_bytes()).assets


@responses.activate
def test_init_command_where_source_language_code_is_blank_should_describe_it_as_source(tmp_path: Path):
    # Arrange
    _mock_catalog([SINGLE | {"languages": [{"language": "", "is_source": True, "latest_version": "1.3.0"}]}])

    # Act
    result = _init(tmp_path)

    # Assert
    assert result.exit_code == 0, result.output
    assert "# Mushaf Madinah — languages: source (1.3.0)" in (tmp_path / "itqan-assets.yaml").read_text()
