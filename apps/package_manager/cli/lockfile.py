"""Lockfile parser, serializer, and state evaluator adhering to docs/ASSET_MANIFEST.md §5."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from apps.package_manager.cli.exceptions import (
    LockfileError,
    YamlProfileViolationError,
)
from apps.package_manager.cli.manifest import (
    AssetManifest,
    _StrictYamlLoader,
    load_manifest,
)
from apps.package_manager.cli.semver import (
    matches_constraint,
    parse_constraint,
    parse_semver,
)


class LockfileState(str, Enum):
    ABSENT = "ABSENT"
    INVALID = "INVALID"
    ORPHAN = "ORPHAN"
    MISSING = "MISSING"
    STALE = "STALE"
    FRESH = "FRESH"


@dataclass(frozen=True, slots=True)
class LockfileEntry:
    slug: str
    constraint: str
    version: str


@dataclass(frozen=True, slots=True)
class AssetLockfile:
    lockfile_version: int
    manifest_schema_version: int
    assets: dict[str, LockfileEntry]


def parse_lockfile_content(content_bytes: bytes) -> AssetLockfile:
    """Parse raw bytes of a lockfile strictly according to §5."""
    if not content_bytes or not content_bytes.strip():
        raise YamlProfileViolationError("Lockfile is empty or contains only whitespace.")

    if content_bytes.startswith(b"\xef\xbb\xbf"):
        raise YamlProfileViolationError("UTF-8 BOM is rejected in lockfile.")

    try:
        content_str = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise YamlProfileViolationError(f"Lockfile must be valid UTF-8: {exc}") from exc

    loader = _StrictYamlLoader(content_str)
    try:
        node = loader.get_single_node()
    except Exception as exc:
        raise YamlProfileViolationError(f"Invalid YAML syntax in lockfile: {exc}") from exc

    if node is None:
        raise YamlProfileViolationError("Lockfile contains no YAML document.")

    try:
        data = loader.construct_object(node, deep=True)
    except Exception as exc:
        raise YamlProfileViolationError(f"Failed to parse lockfile YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise YamlProfileViolationError("Lockfile root must be a mapping.")

    # Strict schema checking
    allowed_top_keys = {"lockfile_version", "manifest_schema_version", "assets"}
    for k in data.keys():
        if k not in allowed_top_keys:
            raise LockfileError(f"Unknown top-level key in lockfile: '{k}'")

    lockfile_version = data.get("lockfile_version")
    if lockfile_version != 1 or isinstance(lockfile_version, bool):
        raise LockfileError(f"Unsupported lockfile_version {lockfile_version}. Expected 1.")

    manifest_schema_version = data.get("manifest_schema_version")
    if manifest_schema_version != 1 or isinstance(manifest_schema_version, bool):
        raise LockfileError(f"Unsupported manifest_schema_version {manifest_schema_version}. Expected 1.")

    assets_raw = data.get("assets")
    if not isinstance(assets_raw, dict):
        raise LockfileError("'assets' in lockfile must be a mapping.")

    entries: dict[str, LockfileEntry] = {}
    for slug, entry_data in assets_raw.items():
        if not isinstance(slug, str):
            raise LockfileError(f"Lockfile asset slug must be a string, got {type(slug).__name__}.")

        if not isinstance(entry_data, dict):
            raise LockfileError(f"Entry for asset '{slug}' must be a mapping.")

        allowed_entry_keys = {"constraint", "version"}
        for ek in entry_data.keys():
            if ek not in allowed_entry_keys:
                raise LockfileError(f"Unknown key '{ek}' in lockfile entry for '{slug}'.")

        if "constraint" not in entry_data:
            raise LockfileError(f"Missing 'constraint' in lockfile entry for '{slug}'.")
        if "version" not in entry_data:
            raise LockfileError(f"Missing 'version' in lockfile entry for '{slug}'.")

        constraint_val = entry_data["constraint"]
        version_val = entry_data["version"]

        if not isinstance(constraint_val, str):
            raise LockfileError(f"'constraint' for '{slug}' must be a string.")
        if not isinstance(version_val, str):
            raise LockfileError(f"'version' for '{slug}' must be a string.")

        # Canonical SemVer checking without build metadata
        if "+" in version_val:
            raise LockfileError(f"Build metadata not allowed in lockfile version: '{version_val}'")

        semver = parse_semver(version_val)
        if semver is None or version_val != semver.to_canonical_string():
            raise LockfileError(
                f"Version '{version_val}' for '{slug}' is not in canonical three-component SemVer form."
            )

        entries[slug] = LockfileEntry(
            slug=slug,
            constraint=constraint_val,
            version=version_val,
        )

    return AssetLockfile(
        lockfile_version=lockfile_version,
        manifest_schema_version=manifest_schema_version,
        assets=entries,
    )


def serialize_lockfile(lockfile: AssetLockfile) -> bytes:
    """Serialize lockfile to byte-exact deterministic UTF-8 bytes adhering to §5.

    - UTF-8 without BOM
    - LF line endings with exactly one newline at EOF
    - 2 spaces indentation
    - Keys double-quoted with standard escaping
    - Sorted ascending by slug's UTF-8 byte sequence
    """
    lines: list[str] = [
        f"lockfile_version: {lockfile.lockfile_version}",
        f"manifest_schema_version: {lockfile.manifest_schema_version}",
        "",
    ]

    if not lockfile.assets:
        lines.append("assets: {}")
    else:
        lines.append("assets:")
        # Sort by slug UTF-8 byte sequence
        sorted_slugs = sorted(lockfile.assets.keys(), key=lambda s: s.encode("utf-8"))
        for slug in sorted_slugs:
            entry = lockfile.assets[slug]
            # Escape quotes
            escaped_slug = slug.replace("\\", "\\\\").replace('"', '\\"')
            escaped_constraint = entry.constraint.replace("\\", "\\\\").replace('"', '\\"')
            escaped_version = entry.version.replace("\\", "\\\\").replace('"', '\\"')

            lines.append(f'  "{escaped_slug}":')
            lines.append(f'    constraint: "{escaped_constraint}"')
            lines.append(f'    version: "{escaped_version}"')

    lines.append("")  # Ensures single trailing newline
    return "\n".join(lines).encode("utf-8")


def evaluate_lockfile_state(
    manifest_path: Path | str,
    lockfile_path: Path | str,
) -> tuple[LockfileState, AssetManifest | None, AssetLockfile | None]:
    """Evaluate repository state into one of the 6 canonical states per §5.

    Evaluation order:
    1. ABSENT (neither file present)
    2. INVALID (manifest or lockfile invalid)
    3. ORPHAN (valid lockfile present, manifest absent)
    4. MISSING (valid manifest present, lockfile absent)
    5. STALE (manifest and lockfile valid, but mismatched)
    6. FRESH (manifest and lockfile valid and fully matching)
    """
    m_path = Path(manifest_path)
    l_path = Path(lockfile_path)

    m_exists = m_path.is_file()
    l_exists = l_path.is_file()

    # 1. ABSENT
    if not m_exists and not l_exists:
        return LockfileState.ABSENT, None, None

    # Parse and validate lockfile if present (lockfile validation precedes ORPHAN)
    parsed_lockfile: AssetLockfile | None = None
    if l_exists:
        try:
            parsed_lockfile = parse_lockfile_content(l_path.read_bytes())
        except Exception:
            return LockfileState.INVALID, None, None

    # 3. ORPHAN (lockfile valid, manifest absent)
    if not m_exists and l_exists:
        return LockfileState.ORPHAN, None, parsed_lockfile

    # Parse and validate manifest
    parsed_manifest: AssetManifest | None = None
    try:
        parsed_manifest = load_manifest(m_path)
    except Exception:
        # 2. INVALID precedes MISSING
        return LockfileState.INVALID, None, parsed_lockfile

    # 4. MISSING (manifest valid, lockfile absent)
    if m_exists and not l_exists:
        return LockfileState.MISSING, parsed_manifest, None

    assert parsed_lockfile is not None
    assert parsed_manifest is not None

    # Check STALE vs FRESH
    # A. Schema version mismatch
    if parsed_lockfile.manifest_schema_version != parsed_manifest.schema_version:
        return LockfileState.STALE, parsed_manifest, parsed_lockfile

    # B. Asset Key-Set mismatch
    manifest_slugs = set(parsed_manifest.assets.keys())
    lockfile_slugs = set(parsed_lockfile.assets.keys())
    if manifest_slugs != lockfile_slugs:
        return LockfileState.STALE, parsed_manifest, parsed_lockfile

    # C. Constraint text mismatch & satisfaction
    for slug in manifest_slugs:
        m_entry = parsed_manifest.assets[slug]
        l_entry = parsed_lockfile.assets[slug]

        # Literal constraint text must match verbatim
        if m_entry.version != l_entry.constraint:
            return LockfileState.STALE, parsed_manifest, parsed_lockfile

        # Locked version must satisfy the constraint
        try:
            parsed_constraint = parse_constraint(m_entry.version)
            locked_semver = parse_semver(l_entry.version)
            if locked_semver is None or not matches_constraint(locked_semver, parsed_constraint):
                return LockfileState.STALE, parsed_manifest, parsed_lockfile
        except Exception:
            return LockfileState.STALE, parsed_manifest, parsed_lockfile

    # 6. FRESH
    return LockfileState.FRESH, parsed_manifest, parsed_lockfile
