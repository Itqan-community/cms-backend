from __future__ import annotations

from dataclasses import dataclass
import re

from django.utils.translation import gettext as _

from apps.content.models import Asset, AssetVersion
from apps.content.repositories.package_registry import PackageRegistryRepository
from apps.core.ninja_utils.errors import ItqanError

# ---------------------------------------------------------------------------
# SemVer primitives (stdlib-only, no external dependency)
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z\-]+(?:\.[0-9A-Za-z\-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z\-]+(?:\.[0-9A-Za-z\-]+)*))?$"
)

# Allowed constraint prefixes.
_CARET_RE = re.compile(r"^(\^)(?P<version>.+)$")
_TILDE_RE = re.compile(r"^(~)(?P<version>.+)$")

# Two-component version (needs canonicalization to three components).
_TWO_COMPONENT_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)$")

# Prerelease-only forms without build metadata.
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
        """Key for SemVer precedence comparison (§10).

        Prerelease versions have lower precedence than the release version
        of the same major.minor.patch. Within prereleases, each dot-separated
        identifier is compared numerically if numeric, lexicographically otherwise.
        """
        if self.prerelease is None:
            # Stable releases sort after any prerelease of the same core.
            return (self.major, self.minor, self.patch, 1, "")
        # Prerelease: sort before stable (0 < 1), then by identifiers.
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


def _parse_semver(version_str: str) -> SemVer | None:
    """Parse a canonical SemVer string. Returns None if invalid."""
    m = _SEMVER_RE.match(version_str)
    if m is None:
        return None
    return SemVer(
        major=int(m.group("major")),
        minor=int(m.group("minor")),
        patch=int(m.group("patch")),
        prerelease=m.group("prerelease"),
    )


def _canonicalize_version(version_str: str) -> str:
    """Expand a two-component version to three components.

    ``1.2`` -> ``1.2.0``, ``1.2.3`` -> ``1.2.3``.
    Rejects one-component, leading zeros, build metadata, etc.
    """
    # Reject build metadata — spec §4 says versions with +build are skipped.
    if "+" in version_str:
        raise ValueError(f"Build metadata not allowed in version: {version_str}")

    # Reject v-prefix.
    if version_str.startswith("v") or version_str.startswith("V"):
        raise ValueError(f"v prefix not allowed in version: {version_str}")

    # Two-component: expand to three.
    m = _TWO_COMPONENT_RE.match(version_str)
    if m is not None:
        return f"{m.group('major')}.{m.group('minor')}.0"

    # Three-component (with optional prerelease).
    m = _PRERELEASE_RE.match(version_str)
    if m is not None:
        return version_str

    # Try full semver regex (includes build metadata — will fail above, but be safe).
    m = _SEMVER_RE.match(version_str)
    if m is not None:
        if m.group("build"):
            raise ValueError(f"Build metadata not allowed in version: {version_str}")
        return version_str

    raise ValueError(f"Invalid version: {version_str}")


# ---------------------------------------------------------------------------
# Constraint parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VersionConstraint:
    """Parsed version constraint."""

    kind: str  # "exact", "caret", "tilde"
    base: SemVer
    # For caret: upper bound (exclusive) — None means no upper bound.
    upper_exclusive: SemVer | None = None
    # For tilde: upper bound (exclusive) on patch — always set.
    # (Already encoded: tilde holds major.minor fixed, so upper is major.minor.(patch+1))


def _parse_constraint(constraint_str: str) -> VersionConstraint:
    """Parse a constraint string into a VersionConstraint.

    Raises ValueError on invalid syntax.
    """
    s = constraint_str.strip()
    if not s:
        raise ValueError("Empty constraint")

    kind: str
    raw_version: str

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

    # Reject ranged prerelease constraints.
    if kind != "exact" and "-" in raw_version:
        raise ValueError(f"Ranged prerelease constraints are not allowed: {constraint_str}")

    # Reject build metadata in constraints.
    if "+" in raw_version:
        raise ValueError(f"Build metadata not allowed in constraint: {constraint_str}")

    # Canonicalize the version part.
    canonical = _canonicalize_version(raw_version)
    semver = _parse_semver(canonical)
    if semver is None:
        raise ValueError(f"Invalid version in constraint: {constraint_str}")

    if kind == "exact":
        return VersionConstraint(kind="exact", base=semver)

    if kind == "caret":
        if semver.major == 0:
            if semver.minor == 0:
                # ^0.0.x -> >=0.0.x <0.0.(x+1)
                upper = SemVer(0, 0, semver.patch + 1)
            else:
                # ^0.x.y -> >=0.x.y <0.(x+1).0
                upper = SemVer(0, semver.minor + 1, 0)
        else:
            # ^x.y.z -> >=x.y.z <(x+1).0.0
            upper = SemVer(semver.major + 1, 0, 0)
        return VersionConstraint(kind="caret", base=semver, upper_exclusive=upper)

    if kind == "tilde":
        # ~x.y.z -> >=x.y.z <x.(y+1).0
        upper = SemVer(semver.major, semver.minor + 1, 0)
        return VersionConstraint(kind="tilde", base=semver, upper_exclusive=upper)

    raise ValueError(f"Unknown constraint kind: {constraint_str}")


def _matches_constraint(version: SemVer, constraint: VersionConstraint) -> bool:
    """Check if a canonical SemVer matches a parsed constraint.

    Prerelease rule (§7): ^ and ~ never select prerelease versions.
    Only an exact prerelease pin selects a prerelease.
    """
    if constraint.kind == "exact":
        return version == constraint.base

    # For ranged constraints, prerelease versions never match.
    if version.is_prerelease:
        return False

    if version < constraint.base:
        return False
    if constraint.upper_exclusive is not None and version >= constraint.upper_exclusive:
        return False
    return True


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@dataclass
class ResolvedPackage:
    """Internal resolution result. Fields are intentionally minimal."""

    asset: Asset
    asset_version: AssetVersion
    canonical_version: str
    requested_constraint: str


class PackageRegistryService:
    def __init__(self, repo: PackageRegistryRepository | None = None) -> None:
        self.repo = repo or PackageRegistryRepository()

    def resolve_single(self, slug: str, version_constraint: str) -> ResolvedPackage:
        """Resolve a single asset slug + constraint to a concrete AssetVersion.

        Raises ItqanError on failure with the appropriate error_name and status_code.
        """
        # 1. Asset lookup.
        asset = self.repo.get_asset_by_slug(slug)
        if asset is None:
            raise ItqanError(
                error_name="asset_not_found",
                message=_("Asset with slug {slug} not found.").format(slug=slug),
                status_code=404,
            )

        # 2. Obtain eligible PACKAGE versions.
        eligible_qs = self.repo.get_eligible_package_versions(asset)
        eligible_versions: list[AssetVersion] = list(eligible_qs)

        # 3. Parse/canonicalize candidate versions and filter invalid names.
        valid_candidates: list[tuple[AssetVersion, SemVer]] = []
        for av in eligible_versions:
            semver = _parse_candidate_version(av.name)
            if semver is None:
                continue
            valid_candidates.append((av, semver))

        if not valid_candidates:
            raise ItqanError(
                error_name="no_eligible_package_versions",
                message=_("Asset {slug} has no eligible PACKAGE versions with valid SemVer names.").format(slug=slug),
                status_code=422,
            )

        # 4. Canonical collision detection over the WHOLE eligible pool.
        seen_canonicals: dict[str, AssetVersion] = {}
        for av, semver in valid_candidates:
            canon = semver.to_canonical_string()
            if canon in seen_canonicals:
                raise ItqanError(
                    error_name="canonical_version_collision",
                    message=_(
                        "Canonical version collision for asset {slug}: "
                        "versions '{existing}' and '{duplicate}' both canonicalize to '{canonical}'."
                    ).format(
                        slug=slug,
                        existing=seen_canonicals[canon].name,
                        duplicate=av.name,
                        canonical=canon,
                    ),
                    status_code=422,
                )
            seen_canonicals[canon] = av

        # 5. Parse the requested constraint.
        try:
            constraint = _parse_constraint(version_constraint)
        except ValueError as exc:
            raise ItqanError(
                error_name="invalid_version_constraint",
                message=_("Invalid version constraint '{constraint}': {reason}.").format(
                    constraint=version_constraint, reason=str(exc)
                ),
                status_code=422,
            ) from exc

        # 6. Filter candidates by constraint.
        matching: list[tuple[AssetVersion, SemVer]] = [
            (av, sv) for av, sv in valid_candidates if _matches_constraint(sv, constraint)
        ]

        # 7. Exact pin: missing version -> 404.
        if constraint.kind == "exact":
            if not matching:
                raise ItqanError(
                    error_name="version_not_found",
                    message=_("Version {version} not found for asset {slug}.").format(
                        version=constraint.base.to_canonical_string(), slug=slug
                    ),
                    status_code=404,
                )
            best_av, _best_sv = matching[0]
            return ResolvedPackage(
                asset=asset,
                asset_version=best_av,
                canonical_version=constraint.base.to_canonical_string(),
                requested_constraint=version_constraint,
            )

        # 8. Range constraint: no match -> 422.
        if not matching:
            raise ItqanError(
                error_name="unsatisfiable_version_constraint",
                message=_(
                    "No eligible PACKAGE version for asset {slug} satisfies constraint '{constraint}' ({range_desc})."
                ).format(
                    slug=slug,
                    constraint=version_constraint,
                    range_desc=_constraint_range_desc(constraint),
                ),
                status_code=422,
            )

        # 9. Select highest matching by SemVer precedence.
        best_av, _best_sv = max(matching, key=lambda x: x[1]._precedence_key())
        return ResolvedPackage(
            asset=asset,
            asset_version=best_av,
            canonical_version=_best_sv.to_canonical_string(),
            requested_constraint=version_constraint,
        )

    def resolve_manifest(self, entries: dict[str, str]) -> list[ResolvedPackage]:
        """Resolve a full manifest dependency set atomically.

        Accepts a mapping of asset slug → version constraint and resolves each
        entry via :meth:`resolve_single`.  Resolution is **all-or-nothing**: if any
        entry fails the first :class:`ItqanError` is raised immediately and no
        partial result is returned.

        Results are sorted by slug in ascending UTF-8 byte order so that callers
        (e.g. the lockfile writer) always see a deterministic sequence regardless
        of input dictionary ordering.

        Raises:
            ItqanError: the same error that :meth:`resolve_single` would raise for
                the first failing entry.
        """
        # Sort by UTF-8 byte sequence to match the lockfile ordering rule in
        # docs/ASSET_MANIFEST.md §5.
        ordered_slugs = sorted(entries.keys(), key=lambda s: s.encode("utf-8"))

        results: list[ResolvedPackage] = []
        for slug in ordered_slugs:
            constraint = entries[slug]
            results.append(self.resolve_single(slug, constraint))

        return results


def _parse_candidate_version(name: str) -> SemVer | None:
    """Try to parse an AssetVersion.name as a canonical SemVer.

    Returns None for invalid/ineligible names (build metadata, malformed, etc.).
    Per spec §4, canonicalization applies to both sides: a candidate named '1.2'
    canonicalizes to '1.2.0' and is treated as valid.
    """
    # Reject build metadata — spec §4: versions carrying +build are skipped.
    if "+" in name:
        return None

    # First try direct parse (three-component or three-component-prerelease).
    semver = _parse_semver(name)
    if semver is not None:
        return semver

    # Two-component: expand to three.
    m = _TWO_COMPONENT_RE.match(name)
    if m is not None:
        return SemVer(
            major=int(m.group("major")),
            minor=int(m.group("minor")),
            patch=0,
        )

    return None


def _constraint_range_desc(constraint: VersionConstraint) -> str:
    """Human-readable range description for error messages."""
    if constraint.kind == "exact":
        return constraint.base.to_canonical_string()
    if constraint.kind == "caret":
        upper = f" <{constraint.upper_exclusive.to_canonical_string()}" if constraint.upper_exclusive else ""
        return f">={constraint.base.to_canonical_string()}{upper}"
    if constraint.kind == "tilde":
        if constraint.upper_exclusive:
            return f">={constraint.base.to_canonical_string()} <{constraint.upper_exclusive.to_canonical_string()}"
        return f">={constraint.base.to_canonical_string()}"
    return str(constraint.base)
