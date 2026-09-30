"""Pull Request updater service for Itqan Dependabot (ITQ-28 / #427).

Automates opening and superseding version-bump PRs across opted-in repositories:
1. Gated by opt-in consent and feature flag.
2. Identifies affected assets in opted-in repositories.
3. Classifies In-Range vs Out-of-Range version updates.
4. Generates deterministic lockfile/manifest updates.
5. Supersedes / refreshes existing open PRs instead of stacking duplicates.
6. References the changed asset, version diff, and release summary in PR body.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from apps.content.models import AssetVersion
from apps.dependabot.models import WatchedRepository
from apps.dependabot.services.github_client import (
    LOCKFILE_PATH,
    MANIFEST_PATH,
    GitHubContentsClient,
    PullRequestSummary,
)
from apps.dependabot.services.github_token import load_github_app_config
from apps.dependabot.services.manifest_discovery import ManifestDiscoveryService
from apps.dependabot.services.manifest_update import (
    serialize_updated_lockfile,
    update_manifest_content,
)
from apps.package_manager.services.package_registry import (
    _parse_candidate_version,
    constraint_satisfied,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpdateResult:
    """The result of evaluating and applying dependabot updates to a repository."""

    action: str  # "created", "superseded", "skipped"
    reason: str | None
    pr: PullRequestSummary | None
    old_version: str | None
    new_version: str | None
    is_in_range: bool | None


class PrUpdaterService:
    """Orchestrates version-bump PR creation and refreshment for watched repositories."""

    def __init__(
        self,
        *,
        github_client: GitHubContentsClient | None = None,
        discovery_service: ManifestDiscoveryService | None = None,
    ) -> None:
        self._github_client = github_client or GitHubContentsClient()
        self._discovery_service = discovery_service or ManifestDiscoveryService(contents_client=self._github_client)

    def process_repository(
        self,
        watched_repo: WatchedRepository,
        asset_version: AssetVersion,
    ) -> UpdateResult:
        """Evaluate and apply a version bump to a watched repository if eligible."""
        if not load_github_app_config().enabled:
            return UpdateResult(
                action="skipped",
                reason="dependabot_disabled",
                pr=None,
                old_version=None,
                new_version=None,
                is_in_range=None,
            )

        if not watched_repo.is_opted_in:
            return UpdateResult(
                action="skipped",
                reason="not_opted_in",
                pr=None,
                old_version=None,
                new_version=None,
                is_in_range=None,
            )

        new_semver = _parse_candidate_version(asset_version.name)
        if new_semver is None:
            return UpdateResult(
                action="skipped",
                reason="invalid_version_name",
                pr=None,
                old_version=None,
                new_version=None,
                is_in_range=None,
            )
        new_version_str = new_semver.to_canonical_string()

        slug = asset_version.asset.slug
        if not slug:
            return UpdateResult(
                action="skipped",
                reason="missing_asset_slug",
                pr=None,
                old_version=None,
                new_version=None,
                is_in_range=None,
            )

        # 1. Run discovery
        discovery = self._discovery_service.discover_watched(watched_repo)
        if discovery.state != "FRESH" or discovery.lockfile is None or discovery.manifest is None:
            logger.info(
                "pr_updater: skipping non-fresh repository [owner=%s, repo=%s, state=%s]",
                watched_repo.owner,
                watched_repo.repository_name,
                discovery.state,
            )
            return UpdateResult(
                action="skipped",
                reason=f"non_fresh_state_{discovery.state.lower()}",
                pr=None,
                old_version=None,
                new_version=new_version_str,
                is_in_range=None,
            )

        # 2. Check if asset is locked in repository
        if slug not in discovery.lockfile.assets:
            return UpdateResult(
                action="skipped",
                reason="asset_not_pinned",
                pr=None,
                old_version=None,
                new_version=new_version_str,
                is_in_range=None,
            )

        current_entry = discovery.lockfile.assets[slug]
        current_semver = discovery.lockfile.versions.get(slug) or _parse_candidate_version(current_entry.version)
        if current_semver is None or new_semver <= current_semver:
            return UpdateResult(
                action="skipped",
                reason="already_up_to_date",
                pr=None,
                old_version=current_entry.version,
                new_version=new_version_str,
                is_in_range=None,
            )

        # 3. Check prerelease on range constraint (§7.4)
        manifest_constraint = discovery.manifest.constraints.get(slug)
        if new_semver.is_prerelease and (manifest_constraint is None or manifest_constraint.kind != "exact"):
            return UpdateResult(
                action="skipped",
                reason="prerelease_ignored_by_range",
                pr=None,
                old_version=current_entry.version,
                new_version=new_version_str,
                is_in_range=None,
            )

        # 4. Classify In-Range vs Out-of-Range
        is_in_range = manifest_constraint is not None and constraint_satisfied(new_semver, manifest_constraint)

        if is_in_range:
            new_lockfile_bytes = serialize_updated_lockfile(
                discovery.lockfile,
                slug=slug,
                new_constraint=current_entry.constraint,
                new_version=new_version_str,
            )
            files = {LOCKFILE_PATH: new_lockfile_bytes}
            title = f"chore(deps): update {slug} to {new_version_str}"
            update_type_desc = "In-Range (lockfile only)"
        else:
            current_manifest_version = discovery.manifest.assets[slug].version
            if current_manifest_version.startswith("^"):
                new_constraint = f"^{new_version_str}"
            elif current_manifest_version.startswith("~"):
                new_constraint = f"~{new_version_str}"
            else:
                new_constraint = new_version_str

            manifest_file = self._github_client.get_file(
                owner=watched_repo.owner,
                repository_name=watched_repo.repository_name,
                installation_id=watched_repo.installation_id,
                path=MANIFEST_PATH,
                ref=discovery.default_branch,
            )
            if manifest_file.content is None:
                return UpdateResult(
                    action="skipped",
                    reason="unreadable_manifest",
                    pr=None,
                    old_version=current_entry.version,
                    new_version=new_version_str,
                    is_in_range=None,
                )

            new_manifest_bytes = update_manifest_content(manifest_file.content, slug, new_constraint)
            new_lockfile_bytes = serialize_updated_lockfile(
                discovery.lockfile,
                slug=slug,
                new_constraint=new_constraint,
                new_version=new_version_str,
            )
            files = {MANIFEST_PATH: new_manifest_bytes, LOCKFILE_PATH: new_lockfile_bytes}
            title = f"chore(deps): bump {slug} from {current_entry.version} to {new_version_str}"
            update_type_desc = "Out-of-Range (manifest & lockfile)"

        # 5. Build PR body
        asset_name = getattr(asset_version.asset, "name", slug)
        asset_category = getattr(asset_version.asset, "category", "")
        summary = asset_version.summary.strip() if asset_version.summary else "No release notes provided."

        body = (
            f"Bumps `{slug}` from `{current_entry.version}` to `{new_version_str}`.\n\n"
            f"### Changes\n"
            f"- **Asset:** {asset_name} (`{slug}`)\n"
            f"- **Category:** {asset_category}\n"
            f"- **Previous Version:** `{current_entry.version}`\n"
            f"- **New Version:** `{new_version_str}`\n"
            f"- **Update Type:** {update_type_desc}\n\n"
            f"### Release Summary\n"
            f"{summary}\n\n"
            f"---\n"
            f"*Automatically generated by [Itqan Dependabot](https://github.com/Itqan-community/cms-backend).*"
        )

        branch_name = f"itqan-dependabot/assets/{slug}"
        commit_msg = f"chore(deps): bump {slug} to {new_version_str}"

        # 6. Check for existing open PRs to prevent downgrading (Race conditions)
        existing_prs = self._github_client.list_pull_requests(
            owner=watched_repo.owner,
            repository_name=watched_repo.repository_name,
            installation_id=watched_repo.installation_id,
            head=branch_name,
            state="open",
        )
        existing_pr = existing_prs[0] if existing_prs else None

        if existing_pr is not None:
            # Extract target version from existing PR title (e.g. "... to 1.4.0")
            target_match = re.search(r"\bto\s+([0-9A-Za-z\.\-\+]+)$", existing_pr.title)
            if target_match:
                existing_pr_version = _parse_candidate_version(target_match.group(1))
                if existing_pr_version is not None and new_semver <= existing_pr_version:
                    logger.info(
                        "pr_updater: skipping version older/equal to existing open PR [owner=%s, repo=%s, pr_number=%d, existing=%s, new=%s]",
                        watched_repo.owner,
                        watched_repo.repository_name,
                        existing_pr.number,
                        existing_pr_version.to_canonical_string(),
                        new_version_str,
                    )
                    return UpdateResult(
                        action="skipped",
                        reason="older_or_equal_to_open_pr",
                        pr=existing_pr,
                        old_version=current_entry.version,
                        new_version=new_version_str,
                        is_in_range=is_in_range,
                    )

        # 7. Commit changes to branch
        self._github_client.commit_files(
            owner=watched_repo.owner,
            repository_name=watched_repo.repository_name,
            installation_id=watched_repo.installation_id,
            branch=branch_name,
            base_branch=discovery.default_branch,
            message=commit_msg,
            files=files,
        )

        # 8. Open or refresh PR (Supersede)
        if existing_pr is not None:
            pr = self._github_client.update_pull_request(
                owner=watched_repo.owner,
                repository_name=watched_repo.repository_name,
                installation_id=watched_repo.installation_id,
                pull_number=existing_pr.number,
                title=title,
                body=body,
            )
            logger.info(
                "pr_updater: superseded existing PR [owner=%s, repo=%s, pr_number=%d, slug=%s, new_version=%s]",
                watched_repo.owner,
                watched_repo.repository_name,
                pr.number,
                slug,
                new_version_str,
            )
            return UpdateResult(
                action="superseded",
                reason=None,
                pr=pr,
                old_version=current_entry.version,
                new_version=new_version_str,
                is_in_range=is_in_range,
            )

        pr = self._github_client.create_pull_request(
            owner=watched_repo.owner,
            repository_name=watched_repo.repository_name,
            installation_id=watched_repo.installation_id,
            title=title,
            body=body,
            head=branch_name,
            base=discovery.default_branch,
        )
        logger.info(
            "pr_updater: opened new PR [owner=%s, repo=%s, pr_number=%d, slug=%s, new_version=%s]",
            watched_repo.owner,
            watched_repo.repository_name,
            pr.number,
            slug,
            new_version_str,
        )
        return UpdateResult(
            action="created",
            reason=None,
            pr=pr,
            old_version=current_entry.version,
            new_version=new_version_str,
            is_in_range=is_in_range,
        )
