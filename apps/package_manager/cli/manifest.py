"""Asset manifest parser and validator adhering to docs/ASSET_MANIFEST.md §2-§3."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml
from yaml.composer import Composer
from yaml.constructor import SafeConstructor
from yaml.parser import Parser
from yaml.reader import Reader
from yaml.resolver import Resolver
from yaml.scanner import Scanner

from apps.package_manager.cli.exceptions import (
    DuplicateAssetEntryError,
    InvalidConstraintSyntaxError,
    MissingRequiredFieldError,
    NonStringAssetKeyError,
    ScalarShorthandEntryError,
    UnknownFieldError,
    UnsupportedSchemaVersionError,
    YamlProfileViolationError,
)
from apps.package_manager.cli.semver import parse_constraint


@dataclass(frozen=True, slots=True)
class AssetManifestEntry:
    """One manifest entry. ``slug`` is the entry's key (its name); ``asset`` is
    the CMS slug it installs, which defaults to the key. ``language`` picks the
    language rendition; None means the asset's source language."""

    slug: str
    version: str
    package: str | None = None
    asset: str = ""
    language: str | None = None

    def to_request(self, version: str | None = None) -> dict[str, str]:
        """Registry request for this entry, optionally pinned to ``version``."""
        request = {"version": version or self.version}
        if self.asset != self.slug:
            request["asset"] = self.asset
        if self.language is not None:
            request["language"] = self.language
        return request


@dataclass(frozen=True, slots=True)
class AssetManifest:
    schema_version: int
    assets: dict[str, AssetManifestEntry]
    assets_dir: str | None = None

    @property
    def raw_constraints(self) -> dict[str, str]:
        """Mapping of entry name -> version constraint string as declared in manifest."""
        return {slug: entry.version for slug, entry in self.assets.items()}

    @property
    def registry_requests(self) -> dict[str, dict[str, str]]:
        """Mapping of entry name -> registry request object."""
        return {slug: entry.to_request() for slug, entry in self.assets.items()}


class _StrictYamlLoader(Reader, Scanner, Parser, Composer, SafeConstructor, Resolver):
    """A strictly conforming YAML loader implementing §2 constraints.

    Rejects:
    - Anchors and aliases
    - Duplicate keys
    """

    def __init__(self, stream: Any) -> None:
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        SafeConstructor.__init__(self)
        Resolver.__init__(self)

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.events.AliasEvent):
            event = self.get_event()
            raise YamlProfileViolationError(f"YAML aliases/anchors are rejected: *{event.anchor}")
        return super().compose_node(parent, index)

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        if not isinstance(node, yaml.MappingNode):
            raise YamlProfileViolationError(f"Expected mapping, got {node.id}")

        mapping: dict[Any, Any] = {}
        seen_keys: set[Any] = set()

        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)

            if key in seen_keys:
                raise YamlProfileViolationError(f"Duplicate mapping key: {key}")
            seen_keys.add(key)

            # Check if an asset key or top-level key was coerced from boolean or int
            # In YAML 1.1 unquoted 'on', 'no', 'true', 123 become bool/int
            if not isinstance(key, str):
                raise NonStringAssetKeyError(f"Mapping key '{key}' must be a string, got {type(key).__name__}.")

            val = self.construct_object(value_node, deep=deep)
            mapping[key] = val

        return mapping


def _validate_manifest_dict(data: dict[str, Any]) -> AssetManifest:
    """Validate parsed manifest mapping against the V1 specification."""
    allowed_top_keys = {"schema_version", "assets", "assets_dir"}
    for key in data.keys():
        if key not in allowed_top_keys:
            raise UnknownFieldError(f"Unknown top-level field: '{key}'. Allowed: {allowed_top_keys}")

    if "schema_version" not in data:
        raise UnsupportedSchemaVersionError("Missing required 'schema_version' field.")

    schema_version_val = data["schema_version"]
    if not isinstance(schema_version_val, int) or isinstance(schema_version_val, bool):
        raise UnsupportedSchemaVersionError(
            f"'schema_version' must be an integer, got {type(schema_version_val).__name__}."
        )

    if schema_version_val != 1:
        raise UnsupportedSchemaVersionError(f"Unsupported schema_version {schema_version_val}. Expected 1.")

    if "assets" not in data:
        raise MissingRequiredFieldError("Missing required top-level 'assets' field.")

    assets_raw = data["assets"]
    if assets_raw is None:
        # `assets:` with only comments under it (e.g. a fresh `itqan init` file)
        assets_raw = {}
    if not isinstance(assets_raw, dict):
        raise YamlProfileViolationError(f"'assets' must be a mapping, got {type(assets_raw).__name__}.")

    parsed_assets: dict[str, AssetManifestEntry] = {}
    seen_targets: dict[tuple[str, str | None], str] = {}

    for slug, entry_raw in assets_raw.items():
        if not isinstance(slug, str):
            raise NonStringAssetKeyError(f"Asset slug key '{slug}' must be a string.")

        if not slug.strip():
            raise NonStringAssetKeyError("Asset slug key cannot be empty.")

        if not isinstance(entry_raw, dict):
            raise ScalarShorthandEntryError(
                f"Asset '{slug}' entry must be a mapping with a 'version' key, not a scalar."
            )

        allowed_entry_keys = {"version", "package", "asset", "language"}
        for entry_k in entry_raw.keys():
            if entry_k not in allowed_entry_keys:
                raise UnknownFieldError(f"Unknown field '{entry_k}' in entry for asset '{slug}'.")

        if "version" not in entry_raw:
            raise MissingRequiredFieldError(f"Asset '{slug}' is missing required 'version' field.")

        version_val = entry_raw["version"]
        if not isinstance(version_val, str) or isinstance(version_val, bool):
            raise InvalidConstraintSyntaxError(f"Version for asset '{slug}' must be a string.")

        try:
            parse_constraint(version_val)
        except ValueError as exc:
            raise InvalidConstraintSyntaxError(
                f"Invalid version constraint '{version_val}' for asset '{slug}': {exc}"
            ) from exc

        package_val: str | None = None
        if "package" in entry_raw:
            package_raw = entry_raw["package"]
            if not isinstance(package_raw, str) or not package_raw.strip():
                raise UnknownFieldError(f"Reserved field 'package' for asset '{slug}' must be a non-empty string.")
            package_val = package_raw

        asset_val = _optional_string_field(entry_raw, "asset", slug) or slug
        language_val = _optional_string_field(entry_raw, "language", slug)

        target = (asset_val, language_val)
        if target in seen_targets:
            raise DuplicateAssetEntryError(
                f"Entries '{seen_targets[target]}' and '{slug}' both name asset '{asset_val}'"
                f" in {f'language {language_val!r}' if language_val else 'its source language'}."
            )
        seen_targets[target] = slug

        parsed_assets[slug] = AssetManifestEntry(
            slug=slug,
            version=version_val,
            package=package_val,
            asset=asset_val,
            language=language_val,
        )

    return AssetManifest(
        schema_version=schema_version_val,
        assets=parsed_assets,
        assets_dir=_validate_assets_dir(data["assets_dir"]) if "assets_dir" in data else None,
    )


def _validate_assets_dir(value: Any) -> str:
    """``assets_dir`` must be a relative path that stays inside the project."""
    if not isinstance(value, str) or not value.strip():
        raise UnknownFieldError("'assets_dir' must be a non-empty string.")
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise UnknownFieldError(f"'assets_dir' must be relative to the manifest, got '{value}'.")
    if ".." in posix.parts or ".." in windows.parts:
        raise UnknownFieldError(f"'assets_dir' must stay inside the project, got '{value}'.")
    return value


def _optional_string_field(entry_raw: dict[str, Any], field: str, slug: str) -> str | None:
    if field not in entry_raw:
        return None
    value = entry_raw[field]
    if not isinstance(value, str) or not value.strip():
        raise UnknownFieldError(f"Field '{field}' for asset '{slug}' must be a non-empty string.")
    return value


def parse_manifest_content(content_bytes: bytes) -> AssetManifest:
    """Parse raw bytes of a manifest file strictly according to §2."""
    if not content_bytes or not content_bytes.strip():
        raise YamlProfileViolationError("Manifest file is empty or contains only whitespace.")

    # Check for UTF-8 BOM
    if content_bytes.startswith(b"\xef\xbb\xbf"):
        raise YamlProfileViolationError("UTF-8 BOM is rejected.")

    try:
        content_str = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise YamlProfileViolationError(f"Manifest must be valid UTF-8: {exc}") from exc

    loader = _StrictYamlLoader(content_str)
    try:
        node = loader.get_single_node()
    except Exception as exc:
        raise YamlProfileViolationError(f"Invalid YAML syntax: {exc}") from exc

    if node is None:
        raise YamlProfileViolationError("Manifest contains no YAML document.")

    try:
        data = loader.construct_object(node, deep=True)
    except (YamlProfileViolationError, NonStringAssetKeyError):
        raise
    except Exception as exc:
        raise YamlProfileViolationError(f"Failed to parse YAML structure: {exc}") from exc

    if not isinstance(data, dict):
        raise YamlProfileViolationError(f"Manifest root must be a YAML mapping, got {type(data).__name__}.")

    return _validate_manifest_dict(data)


def load_manifest(path: Path | str) -> AssetManifest:
    """Load and parse manifest from a file path."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Manifest file not found: {p}")
    return parse_manifest_content(p.read_bytes())
