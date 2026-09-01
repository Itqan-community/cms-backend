from model_bakery import baker

from apps.content.models import Asset, AssetVersion, Distribution, VersionStateChoice
from apps.content.repositories.package_registry import PackageRegistryRepository
from apps.content.services.package_registry import (
    PackageRegistryService,
    _canonicalize_version,
    _constraint_range_desc,
    _matches_constraint,
    _parse_candidate_version,
    _parse_constraint,
)
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_asset(
    publisher: Publisher,
    *,
    slug: str = "test-asset",
    restricted_for_tenant: bool = False,
) -> Asset:
    return Asset.objects.create(
        name="Test Asset",
        slug=slug,
        publisher=publisher,
        category="mushaf",
        license="CC0",
        file_size="1 MB",
        format="pdf",
        description="desc",
        language="en",
        restricted_for_tenant=restricted_for_tenant,
    )


def _make_version(
    asset: Asset,
    *,
    name: str,
    state: str = VersionStateChoice.PUBLISHED,
    with_package_dist: bool = True,
) -> AssetVersion:
    version = baker.make(
        AssetVersion,
        asset=asset,
        name=name,
        state=state,
    )
    if with_package_dist:
        Distribution.objects.create(
            asset_version=version,
            channel=Distribution.ChannelChoice.PACKAGE,
        )
    return version


def _create_asset_with_versions(
    publisher: Publisher,
    slug: str,
    version_names: list[str],
    **kwargs,
) -> Asset:
    asset = _make_asset(publisher, slug=slug, **kwargs)
    for name in version_names:
        _make_version(asset, name=name)
    return asset


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class PackageRegistryRepositoryTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = PackageRegistryRepository()
        self.publisher = baker.make(Publisher)

    # --- get_asset_by_slug ---

    def test_get_asset_by_slug_where_exact_match_should_return_asset(self):
        asset = _make_asset(self.publisher, slug="my-asset")
        result = self.repo.get_asset_by_slug("my-asset")
        self.assertEqual(asset, result)

    def test_get_asset_by_slug_where_case_sensitive_should_respect_case(self):
        _make_asset(self.publisher, slug="My-Asset")
        result = self.repo.get_asset_by_slug("my-asset")
        self.assertIsNone(result)

    def test_get_asset_by_slug_where_restricted_for_tenant_should_be_excluded(self):
        _make_asset(self.publisher, slug="tenant-only", restricted_for_tenant=True)
        result = self.repo.get_asset_by_slug("tenant-only")
        self.assertIsNone(result)

    def test_get_asset_by_slug_where_unknown_slug_should_return_none(self):
        result = self.repo.get_asset_by_slug("nonexistent")
        self.assertIsNone(result)

    # --- get_eligible_package_versions ---

    def test_get_eligible_package_versions_where_published_with_package_should_include(self):
        asset = _make_asset(self.publisher, slug="pkg-asset")
        version = _make_version(asset, name="1.0.0", with_package_dist=True)
        result = list(self.repo.get_eligible_package_versions(asset))
        self.assertEqual([version], result)

    def test_get_eligible_package_versions_where_draft_state_should_be_excluded(self):
        asset = _make_asset(self.publisher, slug="draft-asset")
        baker.make(
            AssetVersion,
            asset=asset,
            name="1.0.0",
            state=VersionStateChoice.DRAFT,
        )
        Distribution.objects.create(
            asset_version=AssetVersion.objects.get(asset=asset, state=VersionStateChoice.DRAFT),
            channel=Distribution.ChannelChoice.PACKAGE,
        )
        result = list(self.repo.get_eligible_package_versions(asset))
        self.assertEqual([], result)

    def test_get_eligible_package_versions_where_no_package_distribution_should_be_excluded(self):
        asset = _make_asset(self.publisher, slug="no-pkg-asset")
        baker.make(
            AssetVersion,
            asset=asset,
            name="1.0.0",
            state=VersionStateChoice.PUBLISHED,
        )
        # No Distribution record
        result = list(self.repo.get_eligible_package_versions(asset))
        self.assertEqual([], result)

    def test_get_eligible_package_versions_where_multiple_versions_returns_all_package(self):
        asset = _make_asset(self.publisher, slug="multi-asset")
        v1 = _make_version(asset, name="1.0.0")
        v2 = _make_version(asset, name="2.0.0")
        result = list(self.repo.get_eligible_package_versions(asset))
        self.assertEqual({v1.pk, v2.pk}, {r.pk for r in result})


# ---------------------------------------------------------------------------
# Service — canonicalization and constraint parsing
# ---------------------------------------------------------------------------


class CanonicalizationTests(BaseTestCase):
    def test_two_component_canonicalizes_to_three(self):
        self.assertEqual("1.2.0", _canonicalize_version("1.2"))

    def test_three_component_remains_unchanged(self):
        self.assertEqual("1.2.3", _canonicalize_version("1.2.3"))

    def test_one_component_rejected(self):
        with self.assertRaises(ValueError):
            _canonicalize_version("2")

    def test_v_prefix_rejected(self):
        with self.assertRaises(ValueError):
            _canonicalize_version("v1.2.3")

    def test_leading_zeros_rejected(self):
        with self.assertRaises(ValueError):
            _canonicalize_version("01.2.0")

    def test_build_metadata_rejected(self):
        with self.assertRaises(ValueError):
            _canonicalize_version("1.2.3+build1")

    def test_invalid_string_rejected(self):
        with self.assertRaises(ValueError):
            _canonicalize_version("draft-2")


class ConstraintParsingTests(BaseTestCase):
    def test_exact_three_component_parses(self):
        c = _parse_constraint("1.2.3")
        self.assertEqual(c.kind, "exact")
        self.assertEqual(c.base.to_canonical_string(), "1.2.3")

    def test_exact_two_component_canonicalizes(self):
        c = _parse_constraint("1.2")
        self.assertEqual(c.kind, "exact")
        self.assertEqual(c.base.to_canonical_string(), "1.2.0")

    def test_caret_three_component(self):
        c = _parse_constraint("^1.2.3")
        self.assertEqual(c.kind, "caret")
        self.assertEqual(c.base.to_canonical_string(), "1.2.3")
        self.assertEqual(c.upper_exclusive.to_canonical_string(), "2.0.0")

    def test_caret_two_component(self):
        c = _parse_constraint("^1.2")
        self.assertEqual(c.kind, "caret")
        self.assertEqual(c.base.to_canonical_string(), "1.2.0")
        self.assertEqual(c.upper_exclusive.to_canonical_string(), "2.0.0")

    def test_caret_zero_major_minor(self):
        c = _parse_constraint("^0.2.3")
        self.assertEqual(c.upper_exclusive.to_canonical_string(), "0.3.0")

    def test_caret_zero_zero_one(self):
        c = _parse_constraint("^0.0.1")
        self.assertEqual(c.upper_exclusive.to_canonical_string(), "0.0.2")

    def test_caret_zero_zero_zero(self):
        c = _parse_constraint("^0.0.0")
        self.assertEqual(c.upper_exclusive.to_canonical_string(), "0.0.1")

    def test_tilde_three_component(self):
        c = _parse_constraint("~1.2.3")
        self.assertEqual(c.kind, "tilde")
        self.assertEqual(c.base.to_canonical_string(), "1.2.3")
        self.assertEqual(c.upper_exclusive.to_canonical_string(), "1.3.0")

    def test_tilde_two_component(self):
        c = _parse_constraint("~1.2")
        self.assertEqual(c.base.to_canonical_string(), "1.2.0")
        self.assertEqual(c.upper_exclusive.to_canonical_string(), "1.3.0")

    def test_prerelease_exact_pin_parses(self):
        c = _parse_constraint("1.2.3-beta.1")
        self.assertEqual(c.kind, "exact")
        self.assertEqual(c.base.to_canonical_string(), "1.2.3-beta.1")

    def test_ranged_prerelease_rejected(self):
        with self.assertRaises(ValueError):
            _parse_constraint("^1.2.3-beta.1")

    def test_wildcard_rejected(self):
        with self.assertRaises(ValueError):
            _parse_constraint("1.*")

    def test_comparator_rejected(self):
        with self.assertRaises(ValueError):
            _parse_constraint(">=1.0.0")

    def test_compound_range_rejected(self):
        with self.assertRaises(ValueError):
            _parse_constraint(">=1.0.0 <2.0.0")

    def test_one_component_rejected(self):
        with self.assertRaises(ValueError):
            _parse_constraint("2")

    def test_build_metadata_rejected(self):
        with self.assertRaises(ValueError):
            _parse_constraint("1.2.3+build1")


# ---------------------------------------------------------------------------
# Service — matching
# ---------------------------------------------------------------------------


class MatchingTests(BaseTestCase):
    def test_exact_match(self):
        c = _parse_constraint("1.2.3")
        self.assertTrue(_matches_constraint(_parse_candidate_version("1.2.3"), c))

    def test_exact_no_match(self):
        c = _parse_constraint("1.2.3")
        self.assertFalse(_matches_constraint(_parse_candidate_version("1.2.4"), c))

    def test_caret_matches_within_range(self):
        c = _parse_constraint("^1.2.0")
        self.assertTrue(_matches_constraint(_parse_candidate_version("1.5.0"), c))
        self.assertTrue(_matches_constraint(_parse_candidate_version("1.2.3"), c))

    def test_caret_excludes_upper_bound(self):
        c = _parse_constraint("^1.2.0")
        self.assertFalse(_matches_constraint(_parse_candidate_version("2.0.0"), c))

    def test_tilde_matches_within_range(self):
        c = _parse_constraint("~1.2.0")
        self.assertTrue(_matches_constraint(_parse_candidate_version("1.2.5"), c))

    def test_tilde_excludes_next_minor(self):
        c = _parse_constraint("~1.2.0")
        self.assertFalse(_matches_constraint(_parse_candidate_version("1.3.0"), c))

    def test_caret_does_not_select_prerelease(self):
        c = _parse_constraint("^1.0.0")
        self.assertFalse(_matches_constraint(_parse_candidate_version("1.0.1-alpha.1"), c))

    def test_tilde_does_not_select_prerelease(self):
        c = _parse_constraint("~1.0.0")
        self.assertFalse(_matches_constraint(_parse_candidate_version("1.0.1-beta.1"), c))

    def test_exact_prerelease_pin_selects_prerelease(self):
        c = _parse_constraint("1.0.0-beta.1")
        self.assertTrue(_matches_constraint(_parse_candidate_version("1.0.0-beta.1"), c))
        self.assertFalse(_matches_constraint(_parse_candidate_version("1.0.0"), c))


# ---------------------------------------------------------------------------
# Service — resolve_single
# ---------------------------------------------------------------------------


class ResolveSingleTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = PackageRegistryService()
        self.publisher = baker.make(Publisher)

    def _create_asset_with_versions(self, slug: str, version_names: list[str], **kwargs):
        asset = _make_asset(self.publisher, slug=slug, **kwargs)
        for name in version_names:
            _make_version(asset, name=name)
        return asset

    # --- unknown asset ---

    def test_resolve_where_unknown_slug_should_return_404(self):
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("nonexistent", "1.0.0")
        self.assertEqual("asset_not_found", ctx.exception.error_name)
        self.assertEqual(404, ctx.exception.status_code)

    # --- no eligible package versions ---

    def test_resolve_where_no_package_distribution_should_return_422(self):
        asset = _make_asset(self.publisher, slug="no-pkg")
        baker.make(
            AssetVersion,
            asset=asset,
            name="1.0.0",
            state=VersionStateChoice.PUBLISHED,
        )
        # No Distribution record
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("no-pkg", "1.0.0")
        self.assertEqual("no_eligible_package_versions", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)

    # --- invalid constraint syntax ---

    def test_resolve_where_invalid_constraint_should_return_422(self):
        _create_asset_with_versions(self.publisher, "valid-slug", ["1.0.0"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("valid-slug", ">=1.0.0")
        self.assertEqual("invalid_version_constraint", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)

    # --- exact pin not found ---

    def test_resolve_where_exact_pin_missing_should_return_404(self):
        _create_asset_with_versions(self.publisher, "missing-pin", ["1.0.0"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("missing-pin", "2.0.0")
        self.assertEqual("version_not_found", ctx.exception.error_name)
        self.assertEqual(404, ctx.exception.status_code)

    # --- exact two-component pin ---

    def test_resolve_where_two_component_exact_pin_should_resolve(self):
        _create_asset_with_versions(self.publisher, "two-cmp", ["1.2"])
        result = self.service.resolve_single("two-cmp", "1.2")
        self.assertEqual("1.2.0", result.canonical_version)
        self.assertEqual(result.asset_version.name, "1.2")

    # --- exact stable pin ---

    def test_resolve_where_exact_stable_pin_should_resolve(self):
        _create_asset_with_versions(self.publisher, "exact-stable", ["1.0.0", "2.0.0"])
        result = self.service.resolve_single("exact-stable", "2.0.0")
        self.assertEqual("2.0.0", result.canonical_version)

    # --- exact prerelease pin ---

    def test_resolve_where_exact_prerelease_pin_should_resolve(self):
        _create_asset_with_versions(self.publisher, "exact-pre", ["1.0.0-beta.1"])
        result = self.service.resolve_single("exact-pre", "1.0.0-beta.1")
        self.assertEqual("1.0.0-beta.1", result.canonical_version)

    # --- caret resolution ---

    def test_resolve_where_caret_should_return_highest_matching(self):
        _create_asset_with_versions(self.publisher, "caret-test", ["1.0.0", "1.2.0", "1.3.0"])
        result = self.service.resolve_single("caret-test", "^1.2.0")
        self.assertEqual("1.3.0", result.canonical_version)

    def test_resolve_where_caret_zero_major_selects_highest_in_range(self):
        _create_asset_with_versions(self.publisher, "caret-zero", ["0.2.0", "0.2.5", "0.3.0"])
        result = self.service.resolve_single("caret-zero", "^0.2.3")
        self.assertEqual("0.2.5", result.canonical_version)

    def test_resolve_where_caret_zero_zero_selects_highest_in_range(self):
        _create_asset_with_versions(self.publisher, "caret-zz", ["0.0.1", "0.0.2"])
        result = self.service.resolve_single("caret-zz", "^0.0.1")
        # ^0.0.1 -> >=0.0.1 <0.0.2, so 0.0.2 is excluded
        self.assertEqual("0.0.1", result.canonical_version)

    # --- tilde resolution ---

    def test_resolve_where_tilde_should_return_highest_patch(self):
        _create_asset_with_versions(self.publisher, "tilde-test", ["1.2.0", "1.2.3", "1.3.0"])
        result = self.service.resolve_single("tilde-test", "~1.2")
        self.assertEqual("1.2.3", result.canonical_version)

    # --- unsatisfiable constraint ---

    def test_resolve_where_unsatisfiable_range_should_return_422(self):
        _create_asset_with_versions(self.publisher, "unsat", ["1.0.0"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("unsat", "^2.0.0")
        self.assertEqual("unsatisfiable_version_constraint", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)

    # --- draft versions excluded ---

    def test_resolve_where_draft_version_excluded(self):
        asset = _make_asset(self.publisher, slug="draft-excl")
        baker.make(
            AssetVersion,
            asset=asset,
            name="1.0.0",
            state=VersionStateChoice.DRAFT,
        )
        _make_version(asset, name="2.0.0", state=VersionStateChoice.PUBLISHED)
        # ^2.0.0 matches 2.0.0 (>=2.0.0 <3.0.0); ^1.0.0 would exclude 2.0.0
        result = self.service.resolve_single("draft-excl", "^2.0.0")
        self.assertEqual("2.0.0", result.canonical_version)

    # --- non-SemVer names skipped ---

    def test_resolve_where_invalid_version_names_skipped(self):
        asset = _make_asset(self.publisher, slug="invalid-names")
        baker.make(
            AssetVersion,
            asset=asset,
            name="draft-2",
            state=VersionStateChoice.PUBLISHED,
        )
        Distribution.objects.create(
            asset_version=AssetVersion.objects.get(asset=asset, name="draft-2"),
            channel=Distribution.ChannelChoice.PACKAGE,
        )
        _make_version(asset, name="1.0.0")
        result = self.service.resolve_single("invalid-names", "1.0.0")
        self.assertEqual("1.0.0", result.canonical_version)

    # --- build metadata in version name skipped ---

    def test_resolve_where_build_metadata_version_skipped(self):
        asset = _make_asset(self.publisher, slug="build-meta")
        baker.make(
            AssetVersion,
            asset=asset,
            name="1.0.0+build1",
            state=VersionStateChoice.PUBLISHED,
        )
        Distribution.objects.create(
            asset_version=AssetVersion.objects.get(asset=asset, name="1.0.0+build1"),
            channel=Distribution.ChannelChoice.PACKAGE,
        )
        _make_version(asset, name="1.0.0")
        result = self.service.resolve_single("build-meta", "1.0.0")
        self.assertEqual("1.0.0", result.canonical_version)

    # --- two-component prerelease candidate skipped ---

    def test_resolve_where_two_component_prerelease_skipped(self):
        asset = _make_asset(self.publisher, slug="two-cmp-pre")
        baker.make(
            AssetVersion,
            asset=asset,
            name="1.2-beta.1",
            state=VersionStateChoice.PUBLISHED,
        )
        Distribution.objects.create(
            asset_version=AssetVersion.objects.get(asset=asset, name="1.2-beta.1"),
            channel=Distribution.ChannelChoice.PACKAGE,
        )
        _make_version(asset, name="1.0.0")
        result = self.service.resolve_single("two-cmp-pre", "1.0.0")
        self.assertEqual("1.0.0", result.canonical_version)

    # --- canonical collision ---

    def test_resolve_where_canonical_collision_returns_422(self):
        asset = _make_asset(self.publisher, slug="collision")
        _make_version(asset, name="1.2")
        _make_version(asset, name="1.2.0")
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("collision", "~4.5.0")
        self.assertEqual("canonical_version_collision", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)

    def test_resolve_where_collision_detected_even_out_of_range(self):
        """Collision over whole pool, not just matching versions."""
        asset = _make_asset(self.publisher, slug="collision-out-of-range")
        _make_version(asset, name="1.2")
        _make_version(asset, name="1.2.0")
        _make_version(asset, name="4.5.0")
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("collision-out-of-range", "~4.5.0")
        self.assertEqual("canonical_version_collision", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)

    # --- restricted_for_tenant ---

    def test_resolve_where_restricted_for_tenant_returns_404(self):
        asset = _make_asset(self.publisher, slug="tenant-only", restricted_for_tenant=True)
        _make_version(asset, name="1.0.0")
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("tenant-only", "1.0.0")
        self.assertEqual("asset_not_found", ctx.exception.error_name)
        self.assertEqual(404, ctx.exception.status_code)

    # --- prerelease exclusion from ranges ---

    def test_resolve_where_prerelease_excluded_from_caret_range(self):
        _create_asset_with_versions(self.publisher, "pre-caret", ["1.0.0", "1.0.1-alpha.1"])
        result = self.service.resolve_single("pre-caret", "^1.0.0")
        self.assertEqual("1.0.0", result.canonical_version)

    def test_resolve_where_prerelease_excluded_from_tilde_range(self):
        _create_asset_with_versions(self.publisher, "pre-tilde", ["1.0.0", "1.0.1-beta.1"])
        result = self.service.resolve_single("pre-tilde", "~1.0")
        self.assertEqual("1.0.0", result.canonical_version)

    # --- SemVer precedence (not lexicographic) ---

    def test_resolve_where_semver_precedence_selects_1_10_over_1_9(self):
        _create_asset_with_versions(self.publisher, "semver-precedence", ["1.9.0", "1.10.0"])
        result = self.service.resolve_single("semver-precedence", "^1.0.0")
        self.assertEqual("1.10.0", result.canonical_version)


# ---------------------------------------------------------------------------
# Service — canonicalization edge cases
# ---------------------------------------------------------------------------


class CanonicalizationEdgeCasesTests(BaseTestCase):
    def test_one_component_version_rejected(self):
        with self.assertRaises(ValueError):
            _canonicalize_version("2")

    def test_two_component_prerelease_not_expanded(self):
        """1.2-beta.1 is NOT expanded to 1.2.0-beta.1 — it is invalid."""
        semver = _parse_candidate_version("1.2-beta.1")
        self.assertIsNone(semver)

    def test_three_component_prerelease_parsed(self):
        semver = _parse_candidate_version("1.2.3-beta.1")
        self.assertIsNotNone(semver)
        self.assertEqual("1.2.3-beta.1", semver.to_canonical_string())


# ---------------------------------------------------------------------------
# Service — zero-major caret boundaries
# ---------------------------------------------------------------------------


class ZeroMajorCaretTests(BaseTestCase):
    def test_caret_0_2_3_excludes_0_3_0(self):
        c = _parse_constraint("^0.2.3")
        self.assertTrue(_matches_constraint(_parse_candidate_version("0.2.3"), c))
        self.assertTrue(_matches_constraint(_parse_candidate_version("0.2.9"), c))
        self.assertFalse(_matches_constraint(_parse_candidate_version("0.3.0"), c))

    def test_caret_0_0_1_excludes_0_0_2(self):
        c = _parse_constraint("^0.0.1")
        self.assertTrue(_matches_constraint(_parse_candidate_version("0.0.1"), c))
        self.assertTrue(_matches_constraint(_parse_candidate_version("0.0.1"), c))
        self.assertFalse(_matches_constraint(_parse_candidate_version("0.0.2"), c))

    def test_caret_0_0_0_range(self):
        c = _parse_constraint("^0.0.0")
        self.assertTrue(_matches_constraint(_parse_candidate_version("0.0.0"), c))
        self.assertFalse(_matches_constraint(_parse_candidate_version("0.0.1"), c))


# ---------------------------------------------------------------------------
# Constraint range description
# ---------------------------------------------------------------------------


class ConstraintRangeDescTests(BaseTestCase):
    def test_exact_range_desc(self):
        c = _parse_constraint("1.2.3")
        self.assertEqual("1.2.3", _constraint_range_desc(c))

    def test_caret_range_desc(self):
        c = _parse_constraint("^1.2.0")
        desc = _constraint_range_desc(c)
        self.assertIn(">=1.2.0", desc)
        self.assertIn("<2.0.0", desc)

    def test_tilde_range_desc(self):
        c = _parse_constraint("~1.2.0")
        desc = _constraint_range_desc(c)
        self.assertIn(">=1.2.0", desc)
        self.assertIn("<1.3.0", desc)


# ---------------------------------------------------------------------------
# Service — resolve_manifest (atomic batch resolution)
# ---------------------------------------------------------------------------


class ResolveManifestTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = PackageRegistryService()
        self.publisher = baker.make(Publisher)

    def _make_entries(self, slug_version_pairs: list[tuple[str, str]]) -> dict[str, str]:
        """Build a manifest dict from (slug, constraint) pairs."""
        return dict(slug_version_pairs)

    def test_resolve_manifest_where_all_entries_valid_returns_all(self):
        _create_asset_with_versions(self.publisher, "asset-alpha", ["1.0.0", "1.1.0"])
        _create_asset_with_versions(self.publisher, "asset-beta", ["2.0.0"])
        results = self.service.resolve_manifest({"asset-alpha": "^1.0.0", "asset-beta": "~2.0"})
        self.assertEqual(2, len(results))
        self.assertEqual("1.1.0", results[0].canonical_version)
        self.assertEqual("2.0.0", results[1].canonical_version)

    def test_resolve_manifest_where_second_asset_unknown_raises_asset_not_found(self):
        _create_asset_with_versions(self.publisher, "known-asset", ["1.0.0"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_manifest({"known-asset": "1.0.0", "unknown-asset": "1.0.0"})
        self.assertEqual("asset_not_found", ctx.exception.error_name)
        self.assertEqual(404, ctx.exception.status_code)

    def test_resolve_manifest_where_second_constraint_unsatisfiable_raises_422(self):
        _create_asset_with_versions(self.publisher, "aaa-known", ["1.0.0"])
        _create_asset_with_versions(self.publisher, "zzz-other", ["1.0.0"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_manifest({"aaa-known": "1.0.0", "zzz-other": "^9.0.0"})
        self.assertEqual("unsatisfiable_version_constraint", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)

    def test_resolve_manifest_returns_no_partial_result_on_failure(self):
        """If any entry fails, no results should be returned."""
        _create_asset_with_versions(self.publisher, "first", ["1.0.0"])
        with self.assertRaises(ItqanError):
            self.service.resolve_manifest({"first": "1.0.0", "missing": "1.0.0"})
        # The partial result list should not leak out — the exception propagates.

    def test_resolve_manifest_reuses_exact_pin_404_semantics(self):
        _create_asset_with_versions(self.publisher, "x", ["1.0.0"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_manifest({"x": "2.0.0", "y": "1.0.0"})
        self.assertEqual("version_not_found", ctx.exception.error_name)
        self.assertEqual(404, ctx.exception.status_code)

    def test_resolve_manifest_detects_collision_in_one_asset(self):
        """Collision in any entry aborts the whole resolution."""
        asset = _make_asset(self.publisher, slug="colliding")
        _make_version(asset, name="1.2")
        _make_version(asset, name="1.2.0")
        _make_version(asset, name="2.0.0")
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_manifest({"colliding": "~2.0", "safe-asset": "1.0.0"})
        self.assertEqual("canonical_version_collision", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)

    def test_resolve_manifest_handles_mixed_exact_caret_tilde_constraints(self):
        _create_asset_with_versions(self.publisher, "exact-pkg", ["3.0.0"])
        _create_asset_with_versions(self.publisher, "caret-pkg", ["1.0.0", "1.5.0"])
        _create_asset_with_versions(self.publisher, "tilde-pkg", ["2.1.0", "2.2.0"])
        results = self.service.resolve_manifest(
            {
                "exact-pkg": "3.0.0",
                "caret-pkg": "^1.0.0",
                "tilde-pkg": "~2.1",
            }
        )
        self.assertEqual(3, len(results))
        names = {r.canonical_version for r in results}
        self.assertEqual({"3.0.0", "1.5.0", "2.1.0"}, names)

    def test_resolve_manifest_with_empty_dependency_set_returns_empty_list(self):
        """An empty manifest has no dependencies and resolves cleanly."""
        results = self.service.resolve_manifest({})
        self.assertEqual([], results)

    def test_resolve_manifest_ordering_is_deterministic_by_slug(self):
        """Results must be ordered by slug byte sequence regardless of input order."""
        _create_asset_with_versions(self.publisher, "zebra", ["1.0.0"])
        _create_asset_with_versions(self.publisher, "alpha", ["1.0.0"])
        _create_asset_with_versions(self.publisher, "middle", ["1.0.0"])
        results = self.service.resolve_manifest(
            {
                "zebra": "1.0.0",
                "alpha": "1.0.0",
                "middle": "1.0.0",
            }
        )
        self.assertEqual(["alpha", "middle", "zebra"], [r.asset.slug for r in results])

    def test_resolve_manifest_preserves_exact_slug_identity(self):
        """Slugs are matched exactly — no trimming or case folding."""
        _create_asset_with_versions(self.publisher, "Exact-Slug", ["1.0.0"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_manifest({"exact-slug": "1.0.0"})
        self.assertEqual("asset_not_found", ctx.exception.error_name)

    def test_resolve_manifest_restricted_for_tenant_entry_returns_404(self):
        asset = _make_asset(self.publisher, slug="tenant-only", restricted_for_tenant=True)
        _make_version(asset, name="1.0.0")
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_manifest({"tenant-only": "1.0.0", "other": "1.0.0"})
        self.assertEqual("asset_not_found", ctx.exception.error_name)
        self.assertEqual(404, ctx.exception.status_code)

    def test_resolve_manifest_invalid_constraint_in_one_entry_aborts_whole_resolution(self):
        _create_asset_with_versions(self.publisher, "aaa-good", ["1.0.0"])
        _create_asset_with_versions(self.publisher, "zzz-bad", ["1.0.0"])
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_manifest({"aaa-good": "1.0.0", "zzz-bad": ">=2.0.0"})
        self.assertEqual("invalid_version_constraint", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)


# ---------------------------------------------------------------------------
# Service — edge cases: only-invalid-candidates + numeric precedence in resolve
# ---------------------------------------------------------------------------


class ResolveManifestEdgeCasesTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = PackageRegistryService()
        self.publisher = baker.make(Publisher)

    def test_resolve_manifest_where_all_candidates_have_invalid_semver_should_return_422(self):
        """When every PACKAGE version is invalid SemVer, the manifest fails."""
        asset = _make_asset(self.publisher, slug="all-invalid")
        _make_version(asset, name="draft-2")
        _make_version(asset, name="1.0.0+build1")
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_manifest({"all-invalid": "1.0.0"})
        self.assertEqual("no_eligible_package_versions", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)

    def test_resolve_manifest_prerelease_numeric_precedence_in_exact_pin(self):
        """An exact prerelease pin must select the highest matching SemVer."""
        _create_asset_with_versions(self.publisher, "pre-versioned", ["1.0.0-alpha.2", "1.0.0-alpha.10"])
        result = self.service.resolve_single("pre-versioned", "1.0.0-alpha.10")
        self.assertEqual("1.0.0-alpha.10", result.canonical_version)
