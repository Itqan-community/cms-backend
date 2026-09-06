"""Strict manifest/lockfile parsing and state classification (spec §2/§3/§5).

This module is deliberately NOT the canonical manifest validator/writer
(those belong to the #422 installer): it implements only what discovery
needs to classify a repository into one of the six lockfile states. In
particular it performs no version resolution, writes nothing, and returns
parsed documents only so callers can run the STALE comparisons.

YAML handling follows the contract's strict profile on top of PyYAML:

- Stock PyYAML implements YAML 1.1 (``on``/``no``/``y`` resolve to
  booleans). The contract mandates YAML 1.2 Core Schema, so this module
  installs its own implicit resolvers (bool/null/int/float core forms
  only); everything else stays a string.
- Anchors, aliases, and merge keys are rejected at compose time.
- Duplicate mapping keys are rejected during construction.
- Multi-document files, empty files, BOMs, and non-UTF-8 encodings are
  rejected before/during loading.
- Unknown tags are rejected by the safe constructor.

SemVer grammar checks (§3) reuse the registry's engine through the public
helpers in ``apps.package_manager.services.package_registry`` so discovery
classifies version strings identically to resolution without duplicating
the grammar or touching the database.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass
import re
from typing import Literal

import yaml
from yaml.events import AliasEvent
from yaml.loader import SafeLoader
from yaml.nodes import ScalarNode

from apps.dependabot.services.github_client import DiscoveredFile
from apps.package_manager.services.package_registry import (
    SemVer,
    VersionConstraint,
    constraint_satisfied,
    parse_canonical_version,
    parse_version_constraint,
)

DiscoveryState = Literal["ABSENT", "INVALID", "ORPHAN", "MISSING", "STALE", "FRESH"]

ABSENT: DiscoveryState = "ABSENT"
INVALID: DiscoveryState = "INVALID"
ORPHAN: DiscoveryState = "ORPHAN"
MISSING: DiscoveryState = "MISSING"
STALE: DiscoveryState = "STALE"
FRESH: DiscoveryState = "FRESH"


class ManifestDocumentError(Exception):
    """A manifest/lockfile document failed strict validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# --- YAML 1.2 Core Schema resolvers (applied to plain scalars only) ---
#
# Integer and float spellings follow the documented YAML 1.2 Core Schema
# forms only: decimal ``[-+]?[0-9]+``, octal ``0o[0-7]+``, hexadecimal
# ``0x[0-9a-fA-F]+``, and decimal/scientific floats. Deliberately excluded:
# YAML 1.1 leading-zero octals (``010``), binary ``0b``, underscore
# separators (``1_0``), and sexagesimal (``1:30``) — all of these stay
# strings, which is exactly what asset slugs spelled that way require.
# (PyYAML's constructor would also misread ``010`` as octal 8, so letting
# such spellings resolve as integers would be wrong twice over.)

_CORE_BOOL_RE = r"^(?:true|True|TRUE|false|False|FALSE)$"
_CORE_NULL_RE = r"^(?:~|null|Null|NULL|)$"
_CORE_INT_RE = r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$"
_CORE_FLOAT_RE = r"^(?:[-+]?(?:[0-9]+)(?:\.[0-9]*)?(?:[eE][-+]?[0-9]+)?|\.[0-9]+(?:[eE][-+]?[0-9]+)?)$"


class _StrictLoader(SafeLoader):
    """SafeLoader minus YAML 1.1, minus anchors/aliases."""

    def compose_node(self, parent, index):  # noqa: ANN001, ANN202 - PyYAML signature
        if self.check_event(AliasEvent):
            raise ManifestDocumentError("strict_profile", "Anchors and aliases are not allowed.")
        anchor = getattr(self.peek_event(), "anchor", None)
        if anchor is not None:
            raise ManifestDocumentError("strict_profile", "Anchors and aliases are not allowed.")
        return super().compose_node(parent, index)


_StrictLoader.yaml_implicit_resolvers = {}
for _tag, _regexp, _first in [
    ("tag:yaml.org,2002:bool", _CORE_BOOL_RE, None),
    ("tag:yaml.org,2002:null", _CORE_NULL_RE, None),
    ("tag:yaml.org,2002:int", _CORE_INT_RE, None),
    ("tag:yaml.org,2002:float", _CORE_FLOAT_RE, None),
]:
    _StrictLoader.add_implicit_resolver(_tag, re.compile(_regexp), _first)


def _construct_strict_map(loader: _StrictLoader, node: yaml.MappingNode) -> dict:
    result: dict = {}
    for key_node, value_node in node.value:
        if not isinstance(key_node, ScalarNode):
            raise ManifestDocumentError("strict_profile", "Only scalar mapping keys are allowed.")
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str):
            raise ManifestDocumentError(
                "non_string_key", "Mapping keys must resolve to strings under YAML 1.2 Core Schema."
            )
        if key == "<<":
            raise ManifestDocumentError("strict_profile", "Merge keys (<<) are not allowed.")
        if key in result:
            raise ManifestDocumentError("duplicate_key", f"Duplicate mapping key: {key!r}.")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_StrictLoader.add_constructor("tag:yaml.org,2002:map", _construct_strict_map)


def _load_single_mapping(raw: bytes, *, what: str) -> dict:
    if raw.startswith(codecs.BOM_UTF8):
        raise ManifestDocumentError("encoding", f"{what} must be UTF-8 without a byte-order mark.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ManifestDocumentError("encoding", f"{what} must be UTF-8 encoded.") from None
    try:
        documents = list(yaml.load_all(text, Loader=_StrictLoader))
    except ManifestDocumentError:
        raise
    except (yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
        raise ManifestDocumentError("yaml_error", f"{what} is not parseable YAML: {type(exc).__name__}.") from None
    if len(documents) != 1:
        raise ManifestDocumentError("document_count", f"{what} must contain exactly one YAML document.")
    if documents[0] is None:
        raise ManifestDocumentError("empty_document", f"{what} must not be empty.")
    if not isinstance(documents[0], dict):
        raise ManifestDocumentError("top_level", f"{what} must be a mapping at the top level.")
    return documents[0]


def _require_keys(data: dict, *, required: set[str], what: str) -> None:
    missing = required - data.keys()
    if missing:
        raise ManifestDocumentError("missing_field", f"{what} is missing required fields.")
    unknown = set(data.keys()) - required
    if unknown:
        raise ManifestDocumentError("unknown_field", f"{what} contains unknown fields.")


def _require_version_one(value: object, *, field: str, what: str) -> int:
    # ``type() is int`` (not isinstance): bools compare equal to 1 but are
    # the wrong scalar type under the strict profile.
    if type(value) is not int or value != 1:
        raise ManifestDocumentError("unsupported_version", f"{what} {field} must be 1.")
    return 1


# --- Parsed documents ---


@dataclass(frozen=True)
class ManifestEntry:
    version: str
    package: str | None


@dataclass(frozen=True)
class ParsedManifest:
    schema_version: int
    assets: dict[str, ManifestEntry]
    constraints: dict[str, VersionConstraint]


@dataclass(frozen=True)
class LockfileEntry:
    constraint: str
    version: str


@dataclass(frozen=True)
class ParsedLockfile:
    lockfile_version: int
    manifest_schema_version: int
    assets: dict[str, LockfileEntry]
    versions: dict[str, SemVer]


@dataclass(frozen=True)
class DiscoveryClassification:
    state: DiscoveryState
    manifest: ParsedManifest | None
    lockfile: ParsedLockfile | None


def parse_manifest_document(raw: bytes) -> ParsedManifest:
    """Parse and validate ``itqan-assets.yaml`` (§2/§3). Raises ManifestDocumentError."""
    data = _load_single_mapping(raw, what="manifest")
    _require_keys(data, required={"schema_version", "assets"}, what="manifest")
    schema_version = _require_version_one(data["schema_version"], field="schema_version", what="manifest")
    assets_raw = data["assets"]
    if not isinstance(assets_raw, dict):
        raise ManifestDocumentError("assets", "Manifest assets must be a mapping.")
    assets: dict[str, ManifestEntry] = {}
    constraints: dict[str, VersionConstraint] = {}
    for slug, entry_raw in assets_raw.items():
        if not isinstance(entry_raw, dict):
            raise ManifestDocumentError("entry", "Manifest entries must be mappings, not scalar shorthand.")
        unknown = set(entry_raw.keys()) - {"version", "package"}
        if unknown:
            raise ManifestDocumentError("unknown_field", "Manifest entries contain unknown fields.")
        if "version" not in entry_raw:
            raise ManifestDocumentError("missing_field", "Manifest entries require a version.")
        version = entry_raw["version"]
        if not isinstance(version, str):
            raise ManifestDocumentError("version", "Manifest version constraints must be strings.")
        package = entry_raw.get("package")
        if package is not None and (not isinstance(package, str) or not package):
            raise ManifestDocumentError("package", "Reserved package field must be a non-empty string.")
        try:
            constraints[slug] = parse_version_constraint(version)
        except ValueError:
            raise ManifestDocumentError("version", "Manifest version constraint is not in the §3 grammar.") from None
        assets[slug] = ManifestEntry(version=version, package=package)
    return ParsedManifest(schema_version=schema_version, assets=assets, constraints=constraints)


def parse_lockfile_document(raw: bytes) -> ParsedLockfile:
    """Parse and validate ``itqan-assets.lock`` (§5). Raises ManifestDocumentError."""
    data = _load_single_mapping(raw, what="lockfile")
    _require_keys(
        data,
        required={"lockfile_version", "manifest_schema_version", "assets"},
        what="lockfile",
    )
    lockfile_version = _require_version_one(data["lockfile_version"], field="lockfile_version", what="lockfile")
    manifest_schema_version = _require_version_one(
        data["manifest_schema_version"], field="manifest_schema_version", what="lockfile"
    )
    assets_raw = data["assets"]
    if not isinstance(assets_raw, dict):
        raise ManifestDocumentError("assets", "Lockfile assets must be a mapping.")
    assets: dict[str, LockfileEntry] = {}
    versions: dict[str, SemVer] = {}
    for slug, entry_raw in assets_raw.items():
        if not isinstance(entry_raw, dict):
            raise ManifestDocumentError("entry", "Lockfile entries must be mappings.")
        _require_keys(entry_raw, required={"constraint", "version"}, what="entry")
        constraint = entry_raw["constraint"]
        version = entry_raw["version"]
        if not isinstance(constraint, str):
            raise ManifestDocumentError("constraint", "Lockfile constraints must be strings.")
        if not isinstance(version, str):
            raise ManifestDocumentError("version", "Lockfile versions must be strings.")
        try:
            parse_version_constraint(constraint)
        except ValueError:
            raise ManifestDocumentError("constraint", "Lockfile constraint is not in the §3 grammar.") from None
        parsed_version = parse_canonical_version(version)
        if parsed_version is None:
            raise ManifestDocumentError(
                "version", "Lockfile versions must be canonical three-component SemVer without build metadata."
            )
        assets[slug] = LockfileEntry(constraint=constraint, version=version)
        versions[slug] = parsed_version
    return ParsedLockfile(
        lockfile_version=lockfile_version,
        manifest_schema_version=manifest_schema_version,
        assets=assets,
        versions=versions,
    )


def classify_discovery(*, manifest: DiscoveredFile, lockfile: DiscoveredFile) -> DiscoveryClassification:
    """Classify a manifest/lockfile pair into exactly one of the six §5 states.

    Evaluation order is contractual: ABSENT → INVALID → ORPHAN → MISSING →
    STALE → FRESH. Unreadable-but-present files count as present-and-invalid,
    never as absent.
    """
    parsed_manifest: ParsedManifest | None = None
    if manifest.present:
        if manifest.content is None:
            return DiscoveryClassification(state=INVALID, manifest=None, lockfile=None)
        try:
            parsed_manifest = parse_manifest_document(manifest.content)
        except ManifestDocumentError:
            return DiscoveryClassification(state=INVALID, manifest=None, lockfile=None)

    parsed_lockfile: ParsedLockfile | None = None
    if lockfile.present:
        if lockfile.content is None:
            return DiscoveryClassification(state=INVALID, manifest=None, lockfile=None)
        try:
            parsed_lockfile = parse_lockfile_document(lockfile.content)
        except ManifestDocumentError:
            return DiscoveryClassification(state=INVALID, manifest=None, lockfile=None)

    if parsed_manifest is None and parsed_lockfile is None:
        return DiscoveryClassification(state=ABSENT, manifest=None, lockfile=None)
    if parsed_manifest is None:
        return DiscoveryClassification(state=ORPHAN, manifest=None, lockfile=parsed_lockfile)
    if parsed_lockfile is None:
        return DiscoveryClassification(state=MISSING, manifest=parsed_manifest, lockfile=None)

    if parsed_lockfile.manifest_schema_version != parsed_manifest.schema_version:
        return DiscoveryClassification(state=STALE, manifest=parsed_manifest, lockfile=parsed_lockfile)
    if set(parsed_manifest.assets) != set(parsed_lockfile.assets):
        return DiscoveryClassification(state=STALE, manifest=parsed_manifest, lockfile=parsed_lockfile)
    for slug, entry in parsed_manifest.assets.items():
        locked = parsed_lockfile.assets[slug]
        if locked.constraint != entry.version:
            return DiscoveryClassification(state=STALE, manifest=parsed_manifest, lockfile=parsed_lockfile)
        if not constraint_satisfied(parsed_lockfile.versions[slug], parsed_manifest.constraints[slug]):
            return DiscoveryClassification(state=STALE, manifest=parsed_manifest, lockfile=parsed_lockfile)
    return DiscoveryClassification(state=FRESH, manifest=parsed_manifest, lockfile=parsed_lockfile)
