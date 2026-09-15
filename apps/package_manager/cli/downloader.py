"""Downloader and artifact materializer ensuring idempotency and atomic writes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
import urllib.parse

import requests

from apps.package_manager.cli.client import ResolvedAssetPayload
from apps.package_manager.cli.exceptions import DownloadError


@dataclass(frozen=True, slots=True)
class DownloadResult:
    slug: str
    version: str
    target_path: Path
    downloaded: bool
    size_bytes: int


class AssetDownloader:
    """Handles streaming download and atomic materialization of asset packages."""

    def __init__(
        self,
        assets_dir: Path | str = "assets",
        session: requests.Session | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.assets_dir = Path(assets_dir)
        self.session = session or requests.Session()
        self.timeout = timeout

    def _determine_target_file(self, asset: ResolvedAssetPayload, target_dir: Path) -> Path:
        """Derive filename from download_url or fall back to slug.archive."""
        if asset.download_url:
            parsed = urllib.parse.urlparse(asset.download_url)
            filename = Path(parsed.path).name
            if filename:
                return target_dir / filename
        return target_dir / f"{asset.slug}.pkg"

    def materialize_asset(
        self,
        asset: ResolvedAssetPayload,
        *,
        force: bool = False,
    ) -> DownloadResult:
        """Materialize a single resolved asset into assets/<slug>/ folder.

        Ensures:
        - Idempotency: skip if already present and non-empty.
        - Atomicity: stream to temp file and rename upon success.
        """
        slug_dir = self.assets_dir / asset.slug
        slug_dir.mkdir(parents=True, exist_ok=True)

        target_file = self._determine_target_file(asset, slug_dir)

        # Version marker file to ensure version integrity
        version_marker = slug_dir / ".itqan_version"

        # Idempotency check: if target file and matching version marker exist
        if not force and target_file.is_file() and target_file.stat().st_size > 0:
            if (
                version_marker.is_file()
                and version_marker.read_text(encoding="utf-8").strip() == asset.resolved_version
            ):
                return DownloadResult(
                    slug=asset.slug,
                    version=asset.resolved_version,
                    target_path=target_file,
                    downloaded=False,
                    size_bytes=target_file.stat().st_size,
                )

        if not asset.download_url:
            raise DownloadError(
                f"Asset '{asset.slug}' (version {asset.resolved_version}) has no download URL in the catalog."
            )

        # Download atomically to a temporary file in the same filesystem
        temp_fd, temp_path_str = tempfile.mkstemp(
            prefix=f"{asset.slug}_",
            suffix=".tmp",
            dir=slug_dir,
        )
        temp_file = Path(temp_path_str)

        try:
            with open(temp_fd, "wb") as f_out:
                with self.session.get(asset.download_url, stream=True, timeout=self.timeout) as resp:
                    if resp.status_code != 200:
                        raise DownloadError(
                            f"Failed to download '{asset.slug}' from {asset.download_url}: HTTP {resp.status_code}"
                        )
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f_out.write(chunk)

            # Atomic rename/move to final destination
            shutil.move(str(temp_file), str(target_file))

            # Write version marker
            version_marker.write_text(asset.resolved_version, encoding="utf-8")

            return DownloadResult(
                slug=asset.slug,
                version=asset.resolved_version,
                target_path=target_file,
                downloaded=True,
                size_bytes=target_file.stat().st_size,
            )

        except Exception as exc:
            # Clean up temp file on failure
            if temp_file.exists():
                temp_file.unlink()
            if isinstance(exc, DownloadError):
                raise
            raise DownloadError(f"Error downloading asset '{asset.slug}': {exc}") from exc
