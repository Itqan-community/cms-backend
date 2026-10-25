from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils.translation import gettext as _

from apps.content.models import (
    PUBLISHED_VERSION_CATEGORIES,
    REVIEWED_CATEGORIES,
    Asset,
    AssetAccessRequest,
    AssetLanguage,
    AssetVersion,
    CategoryChoice,
)
from apps.core.ninja_utils.errors import ItqanError
from apps.package_manager.repositories.package_registry import PackageRegistryRepository

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser
    from django.db.models import Q, QuerySet

    from apps.users.models import User

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

    # SemVer 2.0.0 §11: numeric identifiers MUST NOT include leading zeros.
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
        # SemVer 2.0.0 §11: numeric identifiers MUST NOT include leading zeros.
        if "-" in raw_version:
            prerelease_part = raw_version.split("-", 1)[1]
            for ident in prerelease_part.split("."):
                if ident.isdigit() and len(ident) > 1 and ident.startswith("0"):
                    raise ValueError(f"Leading zeros not allowed in prerelease identifier: {ident}")
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

# Categories the package manager does not serve: hidden from the catalog,
# rejected by resolve and not downloadable.
NON_INSTALLABLE_CATEGORIES: frozenset[str] = frozenset({CategoryChoice.RECITATION})


@dataclass(frozen=True, slots=True)
class PackageRequest:
    """One manifest entry: an asset slug, a version constraint and, optionally,
    the language rendition (None means the asset's source language)."""

    slug: str
    version: str
    language: str | None = None
    # The manifest's range when ``version`` is a lockfile pin; only used to
    # report the newest version the range allows.
    constraint: str | None = None


class CatalogAccess(StrEnum):
    """The caller's access to a catalog asset."""

    OPEN = "open"
    GRANTED = "granted"
    PENDING = "pending"
    REJECTED = "rejected"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class CatalogLanguage:
    """A language rendition the registry can install, with its newest version."""

    language: str
    is_source: bool
    latest_version: str
    # The version ``latest_version`` names.
    latest: AssetVersion | None = None


class PackageVersionStatus(StrEnum):
    """A committed version's availability in the package manager.

    ``released``: installable and picked by ranges. ``withdrawn``: published
    once, then the publisher rolled back past it; ranges skip it, but an exact
    (lockfile) pin still installs it, with a warning showing the rollback reason.
    ``removed``: an Itqan admin removed it; never installed. ``not_released``:
    a translation, tafsir, mushaf or font version that was never published.
    """

    RELEASED = "released"
    WITHDRAWN = "withdrawn"
    REMOVED = "removed"
    NOT_RELEASED = "not_released"


@dataclass(frozen=True, slots=True)
class PackageVersionState:
    version: AssetVersion
    status: PackageVersionStatus


@dataclass
class ResolvedPackage:
    """Internal resolution result. Fields are intentionally minimal."""

    asset: Asset
    asset_language: AssetLanguage
    asset_version: AssetVersion
    canonical_version: str
    requested_constraint: str
    name: str = ""
    withdrawn: bool = False
    # Newest released version of the rendition, and the newest one the
    # request's range allows (None when the request has no range).
    latest_version: str | None = None
    latest_in_range: str | None = None


class PackageRegistryService:
    def __init__(self, repo: PackageRegistryRepository | None = None) -> None:
        self.repo = repo or PackageRegistryRepository()

    def find_asset(self, slug: str) -> Asset:
        """Look up an Asset by slug. Raises 404 if not found or tenant-restricted."""
        asset = self.repo.get_asset_by_slug(slug)
        if asset is None:
            raise ItqanError(
                error_name="asset_not_found",
                message=_("Asset with slug {slug} not found.").format(slug=slug),
                status_code=404,
            )
        return asset

    def resolve_single(
        self,
        slug: str,
        version_constraint: str,
        *,
        language: str | None = None,
        asset: Asset | None = None,
        range_constraint: str | None = None,
    ) -> ResolvedPackage:
        """Resolve a single asset slug + constraint to a concrete AssetVersion.

        Each language rendition has its own version timeline, so resolution is
        scoped to ``language`` (or the asset's source language when None).
        ``range_constraint`` is the manifest's range when ``version_constraint``
        is a lockfile pin; it only sets the result's ``latest_in_range``.

        Raises ItqanError on failure with the appropriate error_name and status_code.
        """
        # 1. Asset lookup (reuse pre-fetched asset when available).
        if asset is None:
            asset = self.repo.get_asset_by_slug(slug)
            if asset is None:
                raise ItqanError(
                    error_name="asset_not_found",
                    message=_("Asset with slug {slug} not found.").format(slug=slug),
                    status_code=404,
                )
        self._ensure_installable(asset)

        # 2. Pick the language rendition whose timeline is resolved.
        asset_language = self.repo.get_available_language(asset, language)
        if asset_language is None:
            raise ItqanError(
                error_name="language_not_found",
                message=_("Language {language} is not available for asset {slug}.").format(
                    language=language or asset.language, slug=slug
                ),
                status_code=404,
            )

        # 3. Obtain eligible versions of that rendition: what an exact pin may
        # install (released or withdrawn); ranges narrow it to released below.
        states = self.version_statuses(asset, asset_language)
        eligible_versions = [
            state.version
            for state in states
            if state.status in (PackageVersionStatus.RELEASED, PackageVersionStatus.WITHDRAWN)
        ]
        withdrawn_ids = {state.version.pk for state in states if state.status == PackageVersionStatus.WITHDRAWN}

        # 4. Parse/canonicalize candidate versions and filter invalid names.
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

        # 5. Canonical collision detection over the WHOLE eligible pool.
        seen_canonicals: dict[str, AssetVersion] = {}
        for av, semver in valid_candidates:
            canon = semver.to_canonical_string()
            if canon in seen_canonicals:
                raise ItqanError(
                    error_name="canonical_version_collision",
                    message=_("Canonical version collision detected for asset {slug}.").format(slug=slug),
                    status_code=422,
                )
            seen_canonicals[canon] = av

        # 6. Parse the requested constraint.
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

        # 7. Filter candidates by constraint.
        matching: list[tuple[AssetVersion, SemVer]] = [
            (av, sv) for av, sv in valid_candidates if _matches_constraint(sv, constraint)
        ]

        released = [(av, sv) for av, sv in valid_candidates if av.pk not in withdrawn_ids]
        latest_version = _newest_stable(released)

        # 8. Exact pin: a removed version -> 410, missing version -> 404.
        if constraint.kind == "exact":
            if not matching:
                self._raise_if_removed(slug, states, constraint.base)
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
                asset_language=asset_language,
                asset_version=best_av,
                canonical_version=constraint.base.to_canonical_string(),
                requested_constraint=version_constraint,
                withdrawn=best_av.pk in withdrawn_ids,
                latest_version=latest_version,
                latest_in_range=_newest_in_range(released, range_constraint),
            )

        # 9. Range constraint: only released versions; no match -> 422.
        matching = [(av, sv) for av, sv in matching if av.pk not in withdrawn_ids]
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

        # 10. Select highest matching by SemVer precedence.
        best_av, _best_sv = max(matching, key=lambda x: x[1]._precedence_key())
        return ResolvedPackage(
            asset=asset,
            asset_language=asset_language,
            asset_version=best_av,
            canonical_version=_best_sv.to_canonical_string(),
            requested_constraint=version_constraint,
            latest_version=latest_version,
            latest_in_range=_best_sv.to_canonical_string(),
        )

    def resolve_manifest(
        self,
        entries: dict[str, PackageRequest],
        *,
        assets: dict[str, Asset] | None = None,
    ) -> list[ResolvedPackage]:
        """Resolve a full manifest dependency set atomically.

        Accepts a mapping of entry name → :class:`PackageRequest`. The name is
        the manifest key; it defaults to the slug, and differs when one manifest
        lists several languages of the same asset. Resolution is
        **all-or-nothing**: if any entry fails the first :class:`ItqanError` is
        raised immediately and no partial result is returned.

        Results are sorted by entry name in ascending UTF-8 byte order so that
        callers (e.g. the lockfile writer) always see a deterministic sequence
        regardless of input dictionary ordering.

        Raises:
            ItqanError: the same error that :meth:`resolve_single` would raise for
                the first failing entry.
        """
        # Sort by UTF-8 byte sequence to match the lockfile ordering rule in
        # docs/ASSET_MANIFEST.md §5.
        ordered_names = sorted(entries.keys(), key=lambda s: s.encode("utf-8"))

        results: list[ResolvedPackage] = []
        for name in ordered_names:
            request = entries[name]
            pre_fetched = assets.get(request.slug) if assets is not None else None
            result = self.resolve_single(
                request.slug,
                request.version,
                language=request.language,
                asset=pre_fetched,
                range_constraint=request.constraint,
            )
            result.name = name
            results.append(result)

        return results

    def list_installable_assets(
        self,
        *,
        open_access: bool | None = None,
        category: str | None = None,
        user: User | AnonymousUser | None = None,
    ) -> QuerySet[Asset]:
        """Installable assets, annotated with ``user``'s access to each (see
        :meth:`catalog_access`)."""
        return self.repo.prefetch_catalog_renditions(
            self.repo.list_installable_assets(
                open_access=open_access,
                category=category,
                exclude_categories=NON_INSTALLABLE_CATEGORIES,
                user=user,
            )
        )

    @staticmethod
    def catalog_access(asset: Asset) -> CatalogAccess:
        """What the caller can do with a catalog asset from
        :meth:`list_installable_assets`: ``open`` and ``granted`` can be
        installed; ``pending``, ``rejected`` and ``none`` need an approved
        access request first."""
        if asset.is_open_access or not settings.ENFORCE_ASSET_ACCESS_ON_PUBLIC_API:
            return CatalogAccess.OPEN
        if getattr(asset, "caller_has_grant", False):
            return CatalogAccess.GRANTED
        status = getattr(asset, "caller_request_status", None)
        if status == AssetAccessRequest.StatusChoice.PENDING:
            return CatalogAccess.PENDING
        if status == AssetAccessRequest.StatusChoice.REJECTED:
            return CatalogAccess.REJECTED
        return CatalogAccess.NONE  # never requested, or an approved grant that has expired

    @staticmethod
    def access_request_url(asset: Asset) -> str | None:
        """The asset's page in the CMS, where access is requested; None for open assets."""
        if asset.is_open_access:
            return None
        return f"{settings.FRONTEND_BASE_URL}/gallery/asset/{asset.pk}"

    def _ensure_installable(self, asset: Asset) -> None:
        """Reject an asset whose category the package manager does not serve."""
        if asset.category in NON_INSTALLABLE_CATEGORIES:
            raise ItqanError(
                error_name="category_not_installable",
                message=_("{category} assets can't be installed with the package manager.").format(
                    category=CategoryChoice(asset.category).label
                ),
                status_code=422,
            )

    def catalog_languages(self, asset: Asset) -> list[CatalogLanguage]:
        """The asset's installable languages (source first), each with the newest
        stable version a ``^`` constraint would pick. Languages with no valid
        SemVer version are left out."""
        languages: list[CatalogLanguage] = []
        for rendition in self.repo.list_catalog_renditions(asset):
            latest = self._published_if_latest(asset, rendition) or _latest_version(
                self.installable_versions(asset, rendition)
            )
            if latest is None:
                continue
            version, semver = latest
            languages.append(
                CatalogLanguage(
                    language=rendition.language,
                    is_source=rendition.is_source,
                    latest_version=semver.to_canonical_string(),
                    latest=version,
                )
            )
        return languages

    def _published_if_latest(self, asset: Asset, rendition: AssetLanguage) -> tuple[AssetVersion, SemVer] | None:
        """The rendition's published version when no released version can beat it,
        else None. Spares the catalog the review check of older versions
        (:meth:`_released_version_ids`): versions committed after the published
        one are never released, so a stable published version is the latest
        unless an older one carries a higher number."""
        published = rendition.published_version
        if asset.category not in PUBLISHED_VERSION_CATEGORIES or published is None:
            return None
        versions = self.repo.get_eligible_package_versions(rendition)
        served = next((v for v in versions if v.pk == published.pk and v.removed_at is None), None)
        semver = _parse_candidate_version(published.name)
        if served is None or semver is None or semver.is_prerelease:
            return None
        cutoff = (published.created_at, published.pk)
        for version, other in _candidates(versions):
            if (version.created_at, version.pk) < cutoff and other._precedence_key() > semver._precedence_key():
                return None
        return served, semver

    def installable_languages(self, asset: Asset) -> list[AssetLanguage]:
        """The renditions the itqan CLI can install for ``asset``, source first:
        the languages the catalog (``GET /packages/``) lists, or none when the
        catalog doesn't list the asset.

        Cheap enough for every asset page view: a published version that is
        installable is always released, so a language whose published version
        qualifies needs no version history. Only a language failing that check
        (say, its published version was removed) gets the catalog's full
        computation.
        """
        if not self.list_installable_assets().filter(pk=asset.pk).exists():
            return []
        published_category = asset.category in PUBLISHED_VERSION_CATEGORIES
        languages: list[AssetLanguage] = []
        for rendition in self.repo.list_available_languages_with_published(asset):
            published = rendition.published_version
            if (
                published_category
                and rendition.published_installable
                and _parse_candidate_version(published.name) is not None
            ):
                languages.append(rendition)
            elif _latest_version_string(self.installable_versions(asset, rendition)) is not None:
                languages.append(rendition)
        return languages

    def version_statuses(self, asset: Asset, rendition: AssetLanguage) -> list[PackageVersionState]:
        """Each committed version of one language rendition that has content to
        serve, newest first, with its :class:`PackageVersionStatus`.

        Published-version categories (translations, tafsirs, mushafs, fonts)
        release what the publisher published, as every other consumer surface
        does: the published version, plus older committed versions (for
        translations / tafsirs, only fully approved ones). A version that was
        published once but no longer qualifies (the publisher rolled back past
        it) is withdrawn, so lockfiles pinned to it keep installing; one never
        published is not released. Other categories release every committed
        version. In both, an Itqan admin may remove a version.
        """
        versions = list(self.repo.get_eligible_package_versions(rendition))
        released_ids = self._released_version_ids(asset, rendition, versions)
        states: list[PackageVersionState] = []
        for version in versions:
            if version.removed_at is not None:
                status = PackageVersionStatus.REMOVED
            elif version.pk in released_ids:
                status = PackageVersionStatus.RELEASED
            elif version.first_published_at is not None:
                status = PackageVersionStatus.WITHDRAWN
            else:
                status = PackageVersionStatus.NOT_RELEASED
            states.append(PackageVersionState(version=version, status=status))
        return states

    def installable_versions(self, asset: Asset, rendition: AssetLanguage) -> list[AssetVersion]:
        """The released versions of one rendition (what a range picks from), newest first."""
        return [
            state.version
            for state in self.version_statuses(asset, rendition)
            if state.status == PackageVersionStatus.RELEASED
        ]

    def _released_version_ids(self, asset: Asset, rendition: AssetLanguage, versions: list[AssetVersion]) -> set[int]:
        if asset.category not in PUBLISHED_VERSION_CATEGORIES:
            return {version.pk for version in versions}
        published = rendition.published_version
        if published is None:
            return set()
        reviewed = asset.category in REVIEWED_CATEGORIES
        pending = self.repo.pending_review_cells_by_version(asset, rendition.language) if reviewed else {}
        cutoff = (published.created_at, published.pk)
        return {
            version.pk
            for version in versions
            if version.pk == published.pk
            or ((version.created_at, version.pk) < cutoff and (not reviewed or pending.get(version.pk) == 0))
        }

    @staticmethod
    def _raise_if_removed(slug: str, states: list[PackageVersionState], requested: SemVer) -> None:
        for state in states:
            if state.status != PackageVersionStatus.REMOVED:
                continue
            semver = _parse_candidate_version(state.version.name)
            if semver is not None and semver.to_canonical_string() == requested.to_canonical_string():
                reason = state.version.removal_reason
                message = _("Version {version} of {slug} was removed by Itqan.").format(
                    version=requested.to_canonical_string(), slug=slug
                )
                raise ItqanError(
                    error_name="version_removed",
                    message=f"{message} {reason}".strip() if reason else message,
                    status_code=410,
                )

    def get_downloadable_version(self, asset_version_id: int) -> AssetVersion:
        """A version the registry serves, or 404."""
        version = self.repo.get_downloadable_version(asset_version_id)
        if version is None or version.asset.category in NON_INSTALLABLE_CATEGORIES or not self._is_pinnable(version):
            raise ItqanError(
                error_name="version_not_found",
                message=_("Package version not found."),
                status_code=404,
            )
        return version

    def _is_pinnable(self, version: AssetVersion) -> bool:
        """Whether an exact pin may install ``version``: released or withdrawn."""
        return self.status_of(version) in (PackageVersionStatus.RELEASED, PackageVersionStatus.WITHDRAWN)

    # -- Publisher / admin controls ------------------------------------------

    def get_portal_version(self, version_id: int, *, publisher_q: Q) -> AssetVersion:
        version = self.repo.get_portal_version(version_id, publisher_q)
        if version is None or version.asset.category in NON_INSTALLABLE_CATEGORIES:
            raise ItqanError(
                error_name="version_not_found",
                message=_("Version not found."),
                status_code=404,
            )
        return version

    def remove_version(self, version: AssetVersion, *, user: User | None, reason: str) -> AssetVersion:
        """Remove ``version`` from the package manager and every consumer surface.
        The version consumers are served can't be removed."""
        if version.removed_at is not None:
            raise ItqanError(
                error_name="version_already_removed",
                message=_("This version was already removed."),
                status_code=400,
            )
        served = version.asset.get_published_version(version.resolved_language)
        if served is not None and served.pk == version.pk:
            raise ItqanError(
                error_name="version_is_served",
                message=_("Consumers are served this version. Publish another version before removing it."),
                status_code=400,
            )
        return self.repo.set_removed(version, user=user, reason=reason)

    def reinstate_version(self, version: AssetVersion, *, reason: str) -> PackageVersionStatus:
        """Undo an admin removal. The version gets back the status the publishing
        rules give it (released, withdrawn or not released), never more."""
        if version.removed_at is None:
            raise ItqanError(
                error_name="version_not_removed",
                message=_("This version is not removed."),
                status_code=400,
            )
        version = self.repo.clear_removed(version, reason=reason)
        return self.status_of(version) or PackageVersionStatus.NOT_RELEASED

    def cached_status(self, version: AssetVersion, cache: dict) -> PackageVersionStatus:
        """``version``'s status, computing its whole language's statuses once per
        ``cache`` (one per request), so a version list does not redo it per row."""
        language = version.resolved_language
        key = (version.asset_id, language)
        if key not in cache:
            rendition = self.repo.get_language(version.asset, language)
            if rendition is None or version.asset.category in NON_INSTALLABLE_CATEGORIES:
                cache[key] = {}
            else:
                cache[key] = {
                    state.version.pk: state.status for state in self.version_statuses(version.asset, rendition)
                }
        return cache[key].get(version.pk, PackageVersionStatus.NOT_RELEASED)

    def status_of(self, version: AssetVersion) -> PackageVersionStatus | None:
        for state in self.version_statuses(version.asset, version.asset_language):
            if state.version.pk == version.pk:
                return state.status
        return None

    def ensure_package_file(self, version: AssetVersion) -> AssetVersion:
        """Return ``version`` with a downloadable file, generating it on first request."""
        if version.file_url:
            return version
        try:
            stored = self.repo.store_generated_package_file(version)
        except ItqanError:
            stored = None  # no content template to build the file with
        if stored is None:
            raise ItqanError(
                error_name="package_content_unavailable",
                message=_("This package version has no downloadable content."),
                status_code=404,
            )
        return stored


def _candidates(versions: list[AssetVersion]) -> list[tuple[AssetVersion, SemVer]]:
    """``versions`` whose names are canonical SemVer, with the parsed version."""
    return [(v, semver) for v in versions if (semver := _parse_candidate_version(v.name)) is not None]


def _newest_stable_candidate(
    candidates: list[tuple[AssetVersion, SemVer]],
) -> tuple[AssetVersion, SemVer] | None:
    """The newest stable candidate (newest prerelease when none is stable)."""
    stable = [candidate for candidate in candidates if not candidate[1].is_prerelease] or candidates
    if not stable:
        return None
    return max(stable, key=lambda candidate: candidate[1]._precedence_key())


def _latest_version(versions: list[AssetVersion]) -> tuple[AssetVersion, SemVer] | None:
    """The newest stable SemVer-named version (newest prerelease when none is stable)."""
    return _newest_stable_candidate(_candidates(versions))


def _latest_version_string(versions: list[AssetVersion]) -> str | None:
    """The newest stable SemVer-named version (newest prerelease when none is stable), canonical."""
    return _newest_stable(_candidates(versions))


def _newest_stable(candidates: list[tuple[AssetVersion, SemVer]]) -> str | None:
    """The newest stable version among ``candidates`` (newest prerelease when none is stable), canonical."""
    newest = _newest_stable_candidate(candidates)
    return newest[1].to_canonical_string() if newest else None


def _newest_in_range(candidates: list[tuple[AssetVersion, SemVer]], constraint_text: str | None) -> str | None:
    """The newest of ``candidates`` that ``constraint_text`` allows, canonical; None
    without a constraint or with one that doesn't parse (it is informational only)."""
    if not constraint_text:
        return None
    try:
        constraint = _parse_constraint(constraint_text)
    except ValueError:
        return None
    matching = [semver for _version, semver in candidates if _matches_constraint(semver, constraint)]
    if not matching:
        return None
    return max(matching, key=lambda semver: semver._precedence_key()).to_canonical_string()


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


# ---------------------------------------------------------------------------
# Shared SemVer grammar helpers (spec §3/§5)
# ---------------------------------------------------------------------------
# Public, dependency-free entry points over the same grammar the registry
# resolves with. They exist so other #426/#422 consumers (manifest discovery,
# lockfile freshness checks) classify version strings identically to the
# registry without duplicating the grammar or touching the database.


def parse_version_constraint(constraint_text: str) -> VersionConstraint:
    """Parse a manifest ``version`` constraint per the §3 grammar.

    Accepts exact pins, ``^`` and ``~`` ranges (with two-component
    canonicalization). Raises ``ValueError`` describing why anything else is
    rejected.
    """
    return _parse_constraint(constraint_text)


def parse_canonical_version(version_text: str) -> SemVer | None:
    """Parse a lockfile ``version``. Returns None unless it is canonical.

    Canonical means three components (prerelease suffix allowed) with no
    build metadata — exactly what §5 requires lockfiles to record. A
    two-component string such as ``"3.0"`` parses as a *candidate* elsewhere
    but is NOT canonical, so this returns None for it.
    """
    parsed = _parse_candidate_version(version_text)
    if parsed is None or parsed.to_canonical_string() != version_text:
        return None
    return parsed


def constraint_satisfied(version: SemVer, constraint: VersionConstraint) -> bool:
    """Check a locked version against its recorded constraint (§5 STALE rule).

    Applies prerelease isolation identically to resolution: ``^`` and ``~``
    never match a prerelease; only an exact prerelease pin matches one.
    """
    return _matches_constraint(version, constraint)
