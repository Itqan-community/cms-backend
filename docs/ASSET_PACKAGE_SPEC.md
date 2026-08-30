# Itqan Asset Package Artifact Specification

**Status**: Proposed V1 (addresses ITQ-26)

This document defines the physical artifact format for an Itqan asset, how it maps to the CMS models, how it is generated, and how the CLI installer unpacks it. It is the bridge between the package registry (#417) and the CLI installer (#422).

---

## 1. The Artifact Format

An Itqan asset package is a standard **gzipped tarball (`.tar.gz`)**. 

A tarball is chosen over ZIP because it is streamable, avoids file metadata quirks across operating systems, and natively handles large directories cleanly in CI/CD pipelines.

### Internal Layout

Inside the `.tar.gz`, the package has a strict flat structure at the root (no wrapping top-level directory):

```text
itqan-package.json        # Mandatory metadata and integrity manifest
data/                     # JSON exports for text assets (Tafsir/Translation)
media/                    # Binary files for media assets (Recitation/Mushaf)
```

- **`itqan-package.json`**: Describes the asset identity, semantic version, category, and contains a file-level integrity hash map.
- **`data/`**: Used for textual assets. Contains a structured JSON dump of all `AssetVersionEntry` records associated with this version (e.g., `data/entries.json`).
- **`media/`**: Used for binary/media assets. Contains audio files (`RecitationSurahTrack` files) or font/image files. For recitations, the structure maps to variants, e.g., `media/{folder_slug}/{surah:03}.mp3`.

---

## 2. The Package Manifest (`itqan-package.json`)

The `itqan-package.json` file is the contract between the registry and the application code. It guarantees the integrity of the downloaded files.

```json
{
  "schema_version": 1,
  "asset": {
    "slug": "quran-uthmani-hafs",
    "version": "2.4.1",
    "category": "mushaf",
    "license": "CC-BY"
  },
  "files": {
    "media/page-001.png": {
      "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "size_bytes": 10245
    }
  }
}
```

### Integrity Metadata
The `files` dictionary provides a SHA256 checksum and exact byte size for every file in the package (excluding `itqan-package.json` itself). The installer uses this to verify that no files were corrupted during download or tampered with at rest.

---

## 3. Installer Directory Layout

The CLI installer (`itqan install` / `itqan sync`) reads `itqan-assets.lock` and materializes the packages into the project's filesystem under an `assets/` directory.

### Destination Layout

```text
assets/
  .itqan-installer-state.json
  quran-uthmani-hafs/
    2.4.1/
      itqan-package.json
      media/
        page-001.png
  tajweed-rules/
    0.4.7/
      itqan-package.json
      data/
        entries.json
```

- Packages are nested by `assets/<asset_slug>/<version>/`. This guarantees that multiple versions of the same asset can safely co-exist (e.g., if different app modules rely on different versions).
- **`.itqan-installer-state.json`**: An internal file maintained by the CLI to track the currently materialized assets and their outer tarball checksums.

### Idempotency and Updates
1. The registry API returns the SHA256 checksum of the `.tar.gz` artifact.
2. The installer checks `.itqan-installer-state.json` to see if `assets/<asset_slug>/<version>` exists and its recorded tarball checksum matches the registry.
3. If it matches, the installer **skips** downloading and unpacking entirely (idempotent).
4. If it differs (or is missing), it fetches the tarball, verifies the outer checksum, unpacks it into the versioned directory, and verifies the inner file checksums against `itqan-package.json`.

---

## 4. Mapping to the Backend Model

The package format maps directly to the `PACKAGE` channel of the `Distribution` model.

### 4.1 Prerequisites
For a package to be eligible for resolution via the registry:
1. An `AssetVersion` must exist and its `state` must be `published`.
2. A `Distribution` record must exist linked to this `AssetVersion` with `channel="PACKAGE"`.

### 4.2 Build Task: On-Publish vs On-Demand
Packages MUST be built **asynchronously on-publish**, not on-demand during a registry request.

**Why?**
Recitation assets can contain 114 high-quality MP3 files across multiple folders (e.g., variants for delay, bitrate). Tarballing gigabytes of audio synchronously will time out any standard HTTP request and crash worker nodes. 

**The Build Pipeline:**
1. An admin marks an `AssetVersion` as `published` and adds a `PACKAGE` distribution.
2. A Celery task (e.g., `build_asset_package_artifact`) is triggered.
3. **For Text Assets:** The task queries `AssetVersionEntry` rows, serializing them into a structured `data/entries.json`.
4. **For Media Assets:** The task streams files from R2/S3 into the tarball (`media/...`).
5. The task generates the `itqan-package.json` populated with all internal checksums.
6. The final `.tar.gz` is compressed and uploaded to R2 under a private bucket path (e.g., `packages/{slug}/{version}.tar.gz`).
7. The outer SHA256 checksum of the `.tar.gz` is calculated and saved. *(Note: This will require a new `checksum` field on the `Distribution` model).*
8. Only after this task completes successfully does the registry API expose this version to `itqan install` clients.
