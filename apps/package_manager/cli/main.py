"""Itqan CLI entrypoint implementing `itqan install` and `itqan sync`."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import click

from apps.package_manager.cli.client import RegistryClient, ResolvedAssetPayload
from apps.package_manager.cli.downloader import AssetDownloader
from apps.package_manager.cli.exceptions import ItqanCliError
from apps.package_manager.cli.lockfile import (
    AssetLockfile,
    LockfileEntry,
    LockfileState,
    evaluate_lockfile_state,
    serialize_lockfile,
)


@click.group()
def cli() -> None:
    """Itqan Asset & Package Manager CLI."""


def _run_install(
    manifest_path: str,
    lockfile_path: str,
    assets_dir: str,
    registry_url: str,
    api_key: str | None,
    force: bool,
) -> int:
    m_path = Path(manifest_path)
    l_path = Path(lockfile_path)
    a_dir = Path(assets_dir)

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

    client = RegistryClient(base_url=registry_url, api_key=api_key)
    downloader = AssetDownloader(assets_dir=a_dir)

    resolved_payloads: list[ResolvedAssetPayload] = []

    if state == LockfileState.FRESH and not force:
        assert lockfile is not None
        assert manifest is not None
        click.echo("Lockfile is FRESH. Installing locked versions...")
        # In FRESH mode, we query the registry with the locked exact pins
        locked_constraints = {slug: entry.version for slug, entry in lockfile.assets.items()}
        resolved_payloads = client.resolve_manifest(locked_constraints)
    else:
        # MISSING or STALE or force: Resolve against declared constraints
        assert manifest is not None
        if state == LockfileState.STALE:
            click.echo("Lockfile is STALE. Re-resolving against manifest...")
        else:
            click.echo("Resolving declared assets against package registry...")

        resolved_payloads = client.resolve_manifest(manifest.raw_constraints)

        # Build the new lockfile in memory — do NOT write it yet.
        # We only commit the lockfile after every asset has been downloaded
        # successfully. This ensures the lockfile always reflects reality:
        # if a download fails halfway, the old lockfile is preserved.
        new_lock_entries: dict[str, LockfileEntry] = {}
        for item in resolved_payloads:
            declared_constraint = manifest.assets[item.slug].version
            new_lock_entries[item.slug] = LockfileEntry(
                slug=item.slug,
                constraint=declared_constraint,
                version=item.resolved_version,
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
    default="assets",
    show_default=True,
    help="Target directory for downloaded assets.",
)
@click.option(
    "--registry-url",
    envvar="ITQAN_REGISTRY_URL",
    default="http://localhost:8000/api",
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
    assets_dir: str,
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


if __name__ == "__main__":
    cli()
