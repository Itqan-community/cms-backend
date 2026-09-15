"""Pure Python SemVer 2.0.0 primitives adhering to docs/ASSET_MANIFEST.md §3.

Zero Django / ORM dependencies so it can run headlessly in any environment.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z\-]+(?:\.[0-9A-Za-z\-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z\-]+(?:\.[0-9A-Za-z\-]+)*))?$"
)

_CARET_RE = re.compile(r"^(\^)(?P<version>.+)$")
_TILDE_RE = re.compile(r"^(~)(?P<version>.+)$")
_TWO_COMPONENT_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)$")
_PRERELEASE_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"-(?P<prerelease>[0-9A-Za-z\-]+(?:\.[0-9A-Za-z\-]+)*)$"
)


@dataclass(frozen=True, slots=True)
class SemVer:
    """Immutable SemVer 2.0.0 representation."""

    major: int
    minor: int
    patch: int
    prerelease: str | None = None

    @property
    def is_prerelease(self) -> bool:
        return self.prerelease is not None

    def to_canonical_string(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease is not None:
            base += f"-{self.prerelease}"
        return base

    def _precedence_key(self) -> tuple:
        if self.prerelease is None:
            return (self.major, self.minor, self.patch, 1, "")
        identifiers = self.prerelease.split(".")
        id_keys = []
        for ident in identifiers:
            if ident.isdigit():
                id_keys.append((0, int(ident), ""))
            else:
                id_keys.append((1, 0, ident))
        return (self.major, self.minor, self.patch, 0, id_keys)

    def __lt__(self, other: SemVer) -> bool:
        return self._precedence_key() < other._precedence_key()

    def __le__(self, other: SemVer) -> bool:
        return self._precedence_key() <= other._precedence_key()

    def __gt__(self, other: SemVer) -> bool:
        return self._precedence_key() > other._precedence_key()

    def __ge__(self, other: SemVer) -> bool:
        return self._precedence_key() >= other._precedence_key()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._precedence_key() == other._precedence_key()

    def __hash__(self) -> int:
        return hash(self._precedence_key())


def parse_semver(version_str: str) -> SemVer | None:
    """Parse a canonical SemVer string. Returns None if invalid."""
    m = _SEMVER_RE.match(version_str)
    if m is None:
        return None

    prerelease_raw = m.group("prerelease")
    if prerelease_raw is not None:
        for ident in prerelease_raw.split("."):
            if ident.isdigit() and len(ident) > 1 and ident.startswith("0"):
                return None

    return SemVer(
        major=int(m.group("major")),
        minor=int(m.group("minor")),
        patch=int(m.group("patch")),
        prerelease=prerelease_raw,
    )


def canonicalize_version(version_str: str) -> str:
    """Expand two-component version to three components.

    `1.2` -> `1.2.0`, `1.2.3` -> `1.2.3`.
    """
    if "+" in version_str:
        raise ValueError(f"Build metadata not allowed in version: {version_str}")

    if version_str.startswith("v") or version_str.startswith("V"):
        raise ValueError(f"v prefix not allowed in version: {version_str}")

    m = _TWO_COMPONENT_RE.match(version_str)
    if m is not None:
        return f"{m.group('major')}.{m.group('minor')}.0"

    m = _PRERELEASE_RE.match(version_str)
    if m is not None:
        return version_str

    m = _SEMVER_RE.match(version_str)
    if m is not None:
        if m.group("build"):
            raise ValueError(f"Build metadata not allowed in version: {version_str}")
        return version_str

    raise ValueError(f"Invalid version: {version_str}")


@dataclass(frozen=True)
class VersionConstraint:
    kind: str  # "exact", "caret", "tilde"
    base: SemVer
    upper_exclusive: SemVer | None = None


def parse_constraint(constraint_str: str) -> VersionConstraint:
    """Parse a constraint string into a VersionConstraint.

    Raises ValueError on invalid syntax.
    """
    s = constraint_str.strip()
    if not s:
        raise ValueError("Empty constraint")

    caret_m = _CARET_RE.match(s)
    tilde_m = _TILDE_RE.match(s)

    if caret_m:
        kind = "caret"
        raw_version = caret_m.group("version")
    elif tilde_m:
        kind = "tilde"
        raw_version = tilde_m.group("version")
    else:
        kind = "exact"
        raw_version = s

    if kind != "exact" and "-" in raw_version:
        raise ValueError(f"Ranged prerelease constraints are not allowed: {constraint_str}")

    if "+" in raw_version:
        raise ValueError(f"Build metadata not allowed in constraint: {constraint_str}")

    canonical = canonicalize_version(raw_version)
    semver = parse_semver(canonical)
    if semver is None:
        raise ValueError(f"Invalid version in constraint: {constraint_str}")

    if kind == "exact":
        if "-" in raw_version:
            prerelease_part = raw_version.split("-", 1)[1]
            for ident in prerelease_part.split("."):
                if ident.isdigit() and len(ident) > 1 and ident.startswith("0"):
                    raise ValueError(f"Leading zeros not allowed in prerelease identifier: {ident}")
        return VersionConstraint(kind="exact", base=semver)

    if kind == "caret":
        if semver.major == 0:
            if semver.minor == 0:
                upper = SemVer(0, 0, semver.patch + 1)
            else:
                upper = SemVer(0, semver.minor + 1, 0)
        else:
            upper = SemVer(semver.major + 1, 0, 0)
        return VersionConstraint(kind="caret", base=semver, upper_exclusive=upper)

    if kind == "tilde":
        upper = SemVer(semver.major, semver.minor + 1, 0)
        return VersionConstraint(kind="tilde", base=semver, upper_exclusive=upper)

    raise ValueError(f"Unknown constraint kind: {constraint_str}")


def matches_constraint(version: SemVer, constraint: VersionConstraint) -> bool:
    """Check if a canonical SemVer matches a parsed constraint."""
    if constraint.kind == "exact":
        return version == constraint.base

    if version.is_prerelease:
        return False

    if version < constraint.base:
        return False
    if constraint.upper_exclusive is not None and version >= constraint.upper_exclusive:
        return False
    return True
