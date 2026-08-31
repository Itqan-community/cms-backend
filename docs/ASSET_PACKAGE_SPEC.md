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

- **`itqan-package.json`**: Describes the asset identity, semantic version, category, and contains a file-level integrity hash map. The `asset.version` field in this manifest is the canonical version source for the package. It MUST strictly adhere to a semantic-version (semver) format. Furthermore, the combination of the asset slug and this version MUST be globally unique across the manifest, local filesystem paths (`assets/<asset_slug>/<version>/`), and remote R2 keys to guarantee consistent identity mapping.
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
      "sha256": "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92",
      "size_bytes": 10245
    }
  }
}
```

### Integrity Metadata
The `files` dictionary provides a SHA256 checksum and exact byte size for every file in the package (excluding `itqan-package.json` itself). The installer MUST enforce strict membership between the archive contents and this dictionary: it MUST reject the package if any archive file is missing from the manifest, if any manifest entry is missing from the archive, or if there are duplicate archive member paths. The installer uses this to verify that no files were corrupted during download or tampered with at rest.

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

- Packages are nested by `assets/<asset_slug>/<version>/`. To prevent path traversal attacks, the asset slug and version strings MUST be validated by the create/update APIs as safe, single path components (rejecting `/`, `..`, etc.). The installer MUST independently verify that the resolved extraction path remains strictly contained within the intended `assets/` base directory before any filesystem access occurs.
- **`.itqan-installer-state.json`**: An internal file maintained by the CLI to track the currently materialized assets and their outer tarball checksums.

### Idempotency and Updates
1. The registry API returns the SHA256 checksum of the `.tar.gz` artifact.
2. The installer checks `.itqan-installer-state.json` to see if `assets/<asset_slug>/<version>` exists and its recorded tarball checksum matches the registry.
3. If it matches, the installer MUST revalidate the existing installation before skipping (by verifying the installed manifest and all expected file hashes, or by checking a trusted persisted local verification record). If validation succeeds, it **skips** downloading entirely. If it fails, it repairs the installation by downloading and unpacking again.
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
1. An admin action (e.g., via `AssetContentService.publish_draft()`) triggers publication. The system MUST implement idempotent triggers that queue the build task regardless of whether the `AssetVersion` publication or the `PACKAGE` Distribution creation happens first, ensuring a published package never remains without an artifact.
2. The Celery task (`build_asset_package_artifact`) executes.
3. **For Text Assets:** The task queries `AssetVersionEntry` rows, serializing them into a structured `data/entries.json`.
4. **For Media Assets:** The task streams files from R2/S3 into the tarball (`media/...`).
5. The task generates the `itqan-package.json` populated with all internal checksums.
6. The final `.tar.gz` is compressed and uploaded to R2. The build flow MUST record the artifact's locator (e.g., an S3 object key like `packages/{slug}/{version}.tar.gz`) alongside the checksum. The registry API will use this locator to expose an unambiguous tarball source (e.g., by issuing a short-lived presigned URL, rather than proxying bytes through the Django app).
7. The outer SHA256 checksum of the `.tar.gz` is calculated and saved.
8. The `Distribution` model MUST define an explicit package-readiness predicate (e.g., a `build_state` enum: `pending`, `ready`, `failed`, `stale-checksum`). Readiness depends strictly on artifact availability and checksum alignment. The registry API MUST ONLY expose `ready` distributions to `itqan install` clients, guaranteeing it never returns a checksum from a superseded or incomplete rebuild.
