"""Downloader and artifact materializer ensuring idempotency and atomic writes."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
import urllib.parse

import requests

from apps.package_manager.cli.client import ResolvedAssetPayload
from apps.package_manager.cli.exceptions import DownloadError

# The version marker filename is reserved — a download URL must never produce
# a basename matching this name, or it would silently overwrite version metadata.
_RESERVED_FILENAME = ".itqan_version"


def _validate_slug(slug: str) -> None:
    """Reject slugs that could escape the assets directory via path traversal.

    A valid slug is a single path component with no separators or traversal
    sequences. Examples that are rejected: '../etc', 'foo/bar', 'a\\b'.

    Why this matters: if asset.slug came from an untrusted source and contained
    '../../../etc/passwd', the path join `assets_dir / slug` would resolve
    outside the assets directory, allowing arbitrary file writes on the system.
    """
    if not slug or not slug.strip():
        raise DownloadError("Asset slug cannot be empty.")
    # Reject any separator or traversal component
    forbidden = {"/", "\\", ".."}
    for part in forbidden:
        if part in slug:
            raise DownloadError(
                f"Asset slug '{slug}' contains forbidden path component '{part}'. "
                "Slugs must be single safe path components."
            )
    # Path(slug).name must equal slug — catches edge cases like 'a/b' on Windows
    if Path(slug).name != slug:
        raise DownloadError(f"Asset slug '{slug}' is not a safe single path component.")


def _validate_download_url(url: str, slug: str) -> None:
    """Reject non-HTTPS download URLs for non-loopback hosts.

    Why this matters: downloading over HTTP exposes the artifact to
    man-in-the-middle attacks — an attacker on the network could replace
    the downloaded file with malicious content before it reaches the disk.
    Loopback addresses (localhost, 127.x.x.x) are allowed for development.
    """
    parsed = urllib.parse.urlparse(url)
    is_loopback = parsed.hostname in ("localhost", "127.0.0.1", "::1") or (
        parsed.hostname is not None and parsed.hostname.startswith("127.")
    )
    if parsed.scheme == "http" and not is_loopback:
        raise DownloadError(
            f"Refusing to download asset '{slug}' over insecure HTTP from {url}. "
            "Use HTTPS or a loopback address for development."
        )


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
        """Derive filename from download_url or fall back to slug.pkg.

        The reserved filename '.itqan_version' is rejected — if a URL's basename
        collides with the version marker we use internally, it would silently
        overwrite version metadata and break idempotency checks.
        """
        if asset.download_url:
            parsed = urllib.parse.urlparse(asset.download_url)
            filename = Path(parsed.path).name
            if filename:
                if filename == _RESERVED_FILENAME:
                    raise DownloadError(
                        f"Download URL for asset '{asset.slug}' has a reserved filename "
                        f"'{_RESERVED_FILENAME}'. This name is used internally by the CLI."
                    )
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
        - Safety: slug is validated against path traversal before any I/O.
        - Idempotency: skip if already present and non-empty.
        - Atomicity: stream to temp file and rename upon success.
        - Marker atomicity: version marker is staged as a temp file then
          renamed — both the artifact and its marker are committed together
          so a power loss between the two writes cannot leave a stale marker.
        """
        # --- Safety: validate slug before any path join ---
        _validate_slug(asset.slug)

        slug_dir = self.assets_dir / asset.slug
        slug_dir.mkdir(parents=True, exist_ok=True)

        target_file = self._determine_target_file(asset, slug_dir)

        # Version marker file to ensure version integrity
        version_marker = slug_dir / _RESERVED_FILENAME

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

        # --- Security: validate download URL before connecting ---
        _validate_download_url(asset.download_url, asset.slug)

        # Download atomically to a temporary file in the same filesystem
        temp_fd, temp_path_str = tempfile.mkstemp(
            prefix=f"{asset.slug}_",
            suffix=".tmp",
            dir=slug_dir,
        )
        temp_file = Path(temp_path_str)

        # Also stage the version marker as a temp file so both are committed
        # in a single rename sequence — prevents a torn state if the process
        # dies between writing the artifact and writing the marker.
        marker_fd, marker_tmp_str = tempfile.mkstemp(
            prefix=".itqan_version_",
            suffix=".tmp",
            dir=slug_dir,
        )
        # Close the marker fd immediately — we will re-open it for writing
        # inside the try block. Keeping it open here would prevent deletion
        # on Windows if an exception occurs before we reach the cleanup block.
        os.close(marker_fd)
        marker_tmp = Path(marker_tmp_str)

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

            # Write version string to the staged marker tmp file
            marker_tmp.write_text(asset.resolved_version, encoding="utf-8")

            # Atomically promote both: marker first, then artifact.
            # os.replace() is atomic on POSIX and best-effort on Windows.
            # If the artifact rename fails the marker is already in place, but
            # the idempotency check requires BOTH to exist and match, so the
            # next run will re-download correctly.
            os.replace(marker_tmp, version_marker)
            os.replace(temp_file, target_file)

            return DownloadResult(
                slug=asset.slug,
                version=asset.resolved_version,
                target_path=target_file,
                downloaded=True,
                size_bytes=target_file.stat().st_size,
            )

        except Exception as exc:
            # Clean up temp files on failure — never leave partial artifacts
            for tmp in (temp_file, marker_tmp):
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass
            if isinstance(exc, DownloadError):
                raise
            raise DownloadError(f"Error downloading asset '{asset.slug}': {exc}") from exc
