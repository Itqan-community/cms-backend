# Itqan Asset Package Artifact Specification

**Status**: Proposed V1 (addresses ITQ-26)
**Schema version**: 1

This document defines the physical artifact format for an Itqan asset, how it maps to the CMS models, how it is generated, and how the CLI installer unpacks it. It is the bridge between the package registry (#417) and the CLI installer (#422).

---

## Table of contents

1. [What this is and why](#1-what-this-is-and-why)
2. [The Artifact Format](#2-the-artifact-format)
3. [The Package Manifest: `itqan-package.json`](#3-the-package-manifest-itqan-packagejson)
4. [Data Wire Schema: `entries.json`](#4-data-wire-schema-entriesjson)
5. [Installer Directory Layout and Extraction](#5-installer-directory-layout-and-extraction)
6. [Mapping to the Backend Model](#6-mapping-to-the-backend-model)
7. [The Build Pipeline: Atomicity and Idempotency](#7-the-build-pipeline-atomicity-and-idempotency)

---

## 1. What this is and why

To distribute assets (like text or media) reliably to applications, we package them into physical artifacts. This document specifies what those artifacts look like inside, how the CMS generates them asynchronously to avoid timeouts, and how the CLI installs them safely and atomically.

---

## 2. The Artifact Format

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

## 3. The Package Manifest: `itqan-package.json`

The `itqan-package.json` file is the contract between the registry and the application code. It guarantees the integrity of the downloaded files and the semantic identity of the package.

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

### Identity and Uniqueness
The `asset.version` field in this manifest is the canonical version source for the package. It MUST strictly adhere to a semantic-version (semver) format. Furthermore, the combination of the asset slug and this version MUST be globally unique across the manifest, local filesystem paths (`assets/<asset_slug>/<version>/`), and remote R2 keys to guarantee consistent identity mapping.

### Integrity Metadata
The `files` dictionary provides a SHA256 checksum and exact byte size for every file in the package (excluding `itqan-package.json` itself). 
The installer MUST inspect tar member types before extraction and reject every member that is neither a regular file nor a directory, including symlinks, hardlinks, devices, and FIFOs. 
The installer MUST enforce strict membership between the permitted archive contents and this dictionary: it MUST require exactly one regular `itqan-package.json` member. The archive's regular-file members MUST be compared against the `files` dictionary after excluding `itqan-package.json`. It MUST reject the package if any archive file is missing from the manifest, if any manifest entry is missing from the archive, or if there are duplicate archive member paths. The installer uses this to verify that no files were corrupted during download or tampered with at rest.

---

## 4. Data Wire Schema: `entries.json`

For textual assets, `data/entries.json` MUST use an explicit V1 wire schema with UTF-8 encoding. 
The top-level shape MUST be a JSON array of objects ordered by `sura` then `aya`. 

Each object maps to an `AssetVersionEntry`. The `ayah_id` is a derived database foreign key, not a composite wire key. During asset package publication, the `(sura, aya)` resolution MUST reject any unresolved or out-of-range pair, and require each pair to resolve exactly once instead of silently skipping it. The object fields are:
- `sura` (integer) - Required
- `aya` (integer) - Required
- `text` (string) - Required
- `footnotes` (string) - Optional

Duplicate entries for the same `sura` and `aya` are strictly forbidden.

---

## 5. Installer Directory Layout and Extraction

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
```

- Packages are nested by `assets/<asset_slug>/<version>/`. To prevent path traversal attacks, the asset slug and version strings MUST be validated by the create/update APIs as safe, single path components (rejecting `/`, `..`, etc.).
- **Path Traversal Constraints**: The installer MUST normalize every archive member as a relative path and require it to remain within the exact `assets/<asset_slug>/<version>/` package directory. The installer MUST reject absolute paths and any member containing traversal components such as `..` before performing extraction or filesystem access.
- **`.itqan-installer-state.json`**: An internal file maintained by the CLI to track the currently materialized assets and their outer tarball checksums.

### Idempotency and Updates

1. The registry API returns the SHA256 checksum of the `.tar.gz` artifact.
2. The installer checks `.itqan-installer-state.json` to see if `assets/<asset_slug>/<version>` exists and its recorded tarball checksum matches the registry.
3. If the checksum matches, the installer MUST revalidate the existing installation before skipping. This revalidation MUST enforce canonical regular-file-set equality with the manifest's expected files, excluding the manifest itself (by verifying the installed manifest and all expected file hashes, or by checking a trusted persisted local verification record). Any stale or unexpected file MUST cause validation to fail and trigger repair rather than skipping the download. If validation succeeds, it **skips** downloading entirely. If it fails, it repairs the installation.
4. If it differs (or is missing) or requires repair, the installer fetches the tarball and verifies the outer checksum. 
   - It MUST extract the archive into a fresh staging directory.
   - It MUST validate the complete package and all inner file checksums against `itqan-package.json`.
   - It MUST require that the extracted manifest's `asset.slug` and `asset.version` exactly match the lock-selected asset slug and version.
   - If this identity check or validation fails, it rejects the artifact.
   - Upon success, it atomically replaces the versioned target directory with the staging directory and updates `.itqan-installer-state.json`. This ensures files absent from the new archive are removed and stale installations cannot remain after rebuilds.

---

## 6. Mapping to the Backend Model

The package format maps directly to the `PACKAGE` channel of the `Distribution` model.

### Package Eligibility

For a package to be eligible for resolution via the registry:
1. An `AssetVersion` must exist and its `state` must be `published`.
2. A `Distribution` record must exist linked to this `AssetVersion` with `channel="PACKAGE"`.
3. The `asset.version` MUST be derived from the canonicalized `AssetVersion.name`, excluding names that are not valid SemVer or contain build metadata.
4. Eligibility MUST preserve the published `(slug, version)` pair immutably, aligning with `docs/ASSET_MANIFEST.md` rather than treating every `PACKAGE` distribution as unconditionally eligible.

---

## 7. The Build Pipeline: Atomicity and Idempotency

Packages MUST be built **asynchronously on-publish**, not on-demand during a registry request.

**Why?**
Recitation assets can contain 114 high-quality MP3 files across multiple folders (e.g., variants for delay, bitrate). Tarballing gigabytes of audio synchronously will time out any standard HTTP request and crash worker nodes. 

**The Build Pipeline:**
1. **Idempotent Trigger**: An admin action (e.g., via `AssetContentService.publish_draft()`) triggers publication. The system MUST implement a post-commit, idempotent package-build trigger spanning `AssetContentService.publish_draft()`, `AssetVersion` publication, and `PACKAGE` Distribution creation. The package-build idempotency key MUST be defined as the exact `AssetVersion` identity, which is used for deduplication. Ensure either event queues `build_asset_package_artifact` after the transaction commits, regardless of ordering, while deduplicating repeated triggers and preserving existing publication behavior. The build task MUST re-check that the `AssetVersion` is published and has a `PACKAGE` Distribution before building, including when the distribution is created first. This MUST include the necessary package artifact/readiness state or durable outbox so a published package cannot remain without an artifact.
2. **Build Execution**: The Celery task (`build_asset_package_artifact`) executes. It MUST bind serialization to a captured publication revision, ensuring `AssetVersionEntry` rows cannot change between publication and artifact creation; alternatively, it MUST reject edits to published versions in `update_translation_version`, `update_tafsir_version`, and `replace_entries_from_parsed`. The existing publication and artifact behavior MUST be preserved for unchanged versions.
3. **For Text Assets**: The task queries `AssetVersionEntry` rows, serializing them into a structured `data/entries.json`.
4. **For Media Assets**: The task streams files from R2/S3 into the tarball (`media/...`).
5. **Manifest Generation**: The task generates the `itqan-package.json` populated with all internal checksums.
6. **Atomic Publication**: The final `.tar.gz` is compressed and uploaded to R2. The artifact publication requirement MUST prevent late workers from overwriting bytes referenced by committed metadata. The publication flow MUST use immutable content-addressed object keys with a compare-and-set locator pointer, or hold a lock across upload, verification, and pointer update while rejecting late writers; do NOT rely on compare-and-set metadata alone with the mutable `packages/{slug}/{version}.tar.gz` key. This prevents concurrent or retried builds from exposing mismatched ready metadata and object bytes. The registry API will use this locator to expose an unambiguous tarball source (e.g., by issuing a short-lived presigned URL, rather than proxying bytes through the Django app).
7. The outer SHA256 checksum of the `.tar.gz` is calculated and saved atomically with the locator.
8. **Readiness State**: The `Distribution` model MUST define an explicit package-readiness predicate (e.g., a `build_state` enum: `pending`, `ready`, `failed`). The registry API MUST ONLY expose a readiness record after this atomic binding succeeds, guaranteeing it never returns a checksum from a superseded or incomplete rebuild.
