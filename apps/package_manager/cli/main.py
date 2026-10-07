"""Itqan CLI entrypoint implementing `itqan install` and `itqan sync`."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import click

from apps.package_manager.cli.client import RegistryClient, ResolvedAssetPayload
from apps.package_manager.cli.downloader import AssetDownloader
from apps.package_manager.cli.exceptions import ItqanCliError, RegistryApiError
from apps.package_manager.cli.init_template import pick_samples, render_fallback, render_from_catalog
from apps.package_manager.cli.lockfile import (
    AssetLockfile,
    LockfileEntry,
    LockfileState,
    evaluate_lockfile_state,
    serialize_lockfile,
)
from apps.package_manager.cli.manifest import parse_manifest_content, validate_assets_dir

DEFAULT_ASSETS_DIR = "assets"


@click.group()
def cli() -> None:
    """Itqan Asset & Package Manager CLI."""


def _run_install(
    manifest_path: str,
    lockfile_path: str,
    assets_dir: str | None,
    registry_url: str,
    api_key: str | None,
    force: bool,
) -> int:
    m_path = Path(manifest_path)
    l_path = Path(lockfile_path)

    click.echo(f"Evaluating asset declarations in {m_path}...")
    state, manifest, lockfile = evaluate_lockfile_state(m_path, l_path)

    if state == LockfileState.ABSENT:
        click.echo(f"No manifest found at {m_path}. Nothing to install.", err=True)
        return 1

    if state == LockfileState.INVALID:
        click.echo("Error: Manifest or lockfile is invalid or malformed.", err=True)
        return 1

    if state == LockfileState.ORPHAN:
        click.echo(f"Error: Lockfile exists at {l_path} but manifest {m_path} is missing.", err=True)
        return 1

    # --assets-dir wins; otherwise the manifest's assets_dir, else "assets",
    # both relative to the manifest's folder.
    assert manifest is not None
    a_dir = Path(assets_dir) if assets_dir else m_path.parent / (manifest.assets_dir or DEFAULT_ASSETS_DIR)

    client = RegistryClient(base_url=registry_url, api_key=api_key)
    downloader = AssetDownloader(assets_dir=a_dir)

    resolved_payloads: list[ResolvedAssetPayload] = []

    if state == LockfileState.FRESH and not force:
        assert lockfile is not None
        assert manifest is not None
        click.echo("Lockfile is FRESH. Installing locked versions...")
        # In FRESH mode, we query the registry with the locked exact pins
        locked_requests = {
            slug: manifest.assets[slug].to_request(version=entry.version) for slug, entry in lockfile.assets.items()
        }
        resolved_payloads = client.resolve_manifest(locked_requests)
    else:
        # MISSING or STALE or force: Resolve against declared constraints
        assert manifest is not None
        if state == LockfileState.STALE:
            click.echo("Lockfile is STALE. Re-resolving against manifest...")
        else:
            click.echo("Resolving declared assets against package registry...")

        resolved_payloads = client.resolve_manifest(manifest.registry_requests)

        # Build the new lockfile in memory — do NOT write it yet.
        # We only commit the lockfile after every asset has been downloaded
        # successfully. This ensures the lockfile always reflects reality:
        # if a download fails halfway, the old lockfile is preserved.
        new_lock_entries: dict[str, LockfileEntry] = {}
        for item in resolved_payloads:
            declared = manifest.assets[item.entry_name]
            new_lock_entries[item.entry_name] = LockfileEntry(
                slug=item.entry_name,
                constraint=declared.version,
                version=item.resolved_version,
                asset=declared.asset if declared.asset != item.entry_name else None,
                language=declared.language,
            )

        new_lockfile = AssetLockfile(
            lockfile_version=1,
            manifest_schema_version=manifest.schema_version,
            assets=new_lock_entries,
        )
        pending_lockfile_bytes = serialize_lockfile(new_lockfile)

    # --- Materialize assets BEFORE writing the lockfile ---
    # If any download fails, we raise immediately and the lockfile is untouched.
    click.echo(f"Materializing {len(resolved_payloads)} asset(s) into {a_dir}...")
    download_summary = []

    for item in resolved_payloads:
        res = downloader.materialize_asset(item, force=force)
        status_str = "downloaded" if res.downloaded else "cached (up-to-date)"
        click.echo(f"  * {res.slug} [{res.version}]: {status_str} -> {res.target_path}")
        download_summary.append(res)

    # --- All downloads succeeded: now atomically write the lockfile ---
    if state != LockfileState.FRESH or force:
        # Write to a sibling temp file then rename — prevents a partial write
        # from leaving a corrupt lockfile if the process is interrupted.
        tmp_fd, tmp_path_str = __import__("tempfile").mkstemp(
            prefix=".itqan_assets_lock_",
            suffix=".tmp",
            dir=l_path.parent,
        )
        tmp_lock = Path(tmp_path_str)
        try:
            with open(tmp_fd, "wb") as f:
                f.write(pending_lockfile_bytes)
            os.replace(tmp_lock, l_path)
            click.echo(f"Updated lockfile at {l_path}")
        except Exception:
            try:
                tmp_lock.unlink()
            except OSError:
                pass
            raise

    click.echo(f"Success! {len(download_summary)} asset(s) materialized successfully.")
    return 0


@cli.command("install")
@click.option(
    "--manifest",
    "-m",
    "manifest_path",
    default="itqan-assets.yaml",
    show_default=True,
    help="Path to itqan-assets.yaml manifest.",
)
@click.option(
    "--lockfile",
    "-l",
    "lockfile_path",
    default="itqan-assets.lock",
    show_default=True,
    help="Path to itqan-assets.lock lockfile.",
)
@click.option(
    "--assets-dir",
    "-d",
    "assets_dir",
    default=None,
    help="Target directory for downloaded assets. Overrides the manifest's assets_dir "
    f"(default: '{DEFAULT_ASSETS_DIR}' next to the manifest).",
)
@click.option(
    "--registry-url",
    envvar="ITQAN_REGISTRY_URL",
    default="https://cms.itqan.dev",
    show_default=True,
    help="URL of the Itqan Package Registry API.",
)
@click.option(
    "--api-key",
    envvar="ITQAN_API_KEY",
    default=None,
    help="API key for authentication & metrics attribution.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Force re-resolution and re-download of assets.",
)
def install_command(
    manifest_path: str,
    lockfile_path: str,
    assets_dir: str | None,
    registry_url: str,
    api_key: str | None,
    force: bool,
) -> None:
    """Install assets declared in itqan-assets.yaml."""
    try:
        exit_code = _run_install(
            manifest_path=manifest_path,
            lockfile_path=lockfile_path,
            assets_dir=assets_dir,
            registry_url=registry_url,
            api_key=api_key,
            force=force,
        )
        sys.exit(exit_code)
    except ItqanCliError as exc:
        click.echo(f"Error: {exc.message}", err=True)
        sys.exit(exc.exit_code)
    except Exception as exc:
        click.echo(f"Unexpected error: {exc}", err=True)
        sys.exit(1)


# Alias: `itqan sync` runs `install`
cli.add_command(install_command, name="sync")


@cli.command("init")
@click.option(
    "--manifest",
    "-m",
    "manifest_path",
    default="itqan-assets.yaml",
    show_default=True,
    help="Path of the manifest to create.",
)
@click.option(
    "--assets-dir",
    "-d",
    "assets_dir",
    default=DEFAULT_ASSETS_DIR,
    show_default=True,
    help="Folder, relative to the manifest, that `itqan install` downloads into.",
)
@click.option(
    "--registry-url",
    envvar="ITQAN_REGISTRY_URL",
    default="https://cms.itqan.dev",
    show_default=True,
    help="URL of the Itqan Package Registry API.",
)
@click.option(
    "--api-key",
    envvar="ITQAN_API_KEY",
    default=None,
    help="API key; without one, only open-access assets are suggested.",
)
@click.option("--force", "-f", is_flag=True, default=False, help="Overwrite an existing manifest.")
def init_command(manifest_path: str, assets_dir: str, registry_url: str, api_key: str | None, force: bool) -> None:
    """Create itqan-assets.yaml with a few real assets from the registry.

    If the registry can't be reached, writes the same file with commented-out
    example entries instead.
    """
    m_path = Path(manifest_path)
    if m_path.exists() and not force:
        click.echo(f"Error: {m_path} already exists. Use --force to overwrite it.", err=True)
        sys.exit(1)

    try:
        validate_assets_dir(assets_dir)
        client = RegistryClient(base_url=registry_url, api_key=api_key)
        samples = pick_samples(client.list_packages(open_access=None if api_key else True))
        if samples:
            content = render_from_catalog(samples, assets_dir)
        else:
            click.echo("Warning: the registry has no installable assets yet; writing commented examples.", err=True)
            content = render_fallback(assets_dir, reason="The registry had no installable assets,")
    except RegistryApiError as exc:
        click.echo(f"Warning: Could not reach the registry ({exc.message}); writing commented examples.", err=True)
        samples = []
        content = render_fallback(assets_dir, reason="Could not reach the registry,")
    except ItqanCliError as exc:
        click.echo(f"Error: {exc.message}", err=True)
        sys.exit(exc.exit_code)

    parse_manifest_content(content.encode("utf-8"))  # never write a manifest `install` would reject
    m_path.parent.mkdir(parents=True, exist_ok=True)
    m_path.write_text(content, encoding="utf-8")
    click.echo(f"Created {m_path} with {len(samples)} sample asset(s).")
    click.echo("Edit it as needed, then run `itqan install` to download the assets.")


if __name__ == "__main__":
    cli()
