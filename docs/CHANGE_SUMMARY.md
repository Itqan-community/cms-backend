# Change Summary

This file explains the recent changes currently in the `staging` branch workspace.

## Overview

The updates are primarily **observability and error-handling improvements**. Most changes replace silent exception handling (`pass`) or minimal string logs with structured logging via `logger.warning(...)` / `logger.exception(...)` and contextual `extra` fields.

## What Changed

### 1) Admin flows for content uploads and access requests
Updated: `apps/content/admin.py`

- Added exception logging in recitation JSON sync failures.
- Added warning logs when `durations_json` cannot be decoded (falls back to mutagen duration extraction).
- Added explicit exception logs in direct-upload endpoints:
  - `uploads_start_view`
  - `uploads_sign_part_view`
  - `uploads_finish_view`
  - `uploads_abort_view`
- Added warning logs for unexpected filename validation errors.
- Added exception logs when bulk approve/reject of access requests fails.

### 2) Content model save-time safety logging
Updated: `apps/content/models.py`

- Introduced module logger.
- Added warning logs when automatic file size extraction fails in `RecitationSurahTrack.save`.
- Added warning logs when ayah duration auto-calculation fails in `RecitationAyahTiming.save`.

### 3) Direct multipart upload service hardening
Updated: `apps/content/services/admin/asset_recitation_audio_tracks_direct_upload_service.py`

- Introduced module logger.
- Added warning logs when object metadata lookup fails after multipart completion.
- Added warning logs when fallback MP3 duration extraction fails.
- Improved abort behavior logging:
  - logs unexpected abort errors at error level and re-raises.
  - logs benign missing-upload abort states at warning level.
- Added exception logging around stuck multipart cleanup listing and per-upload abort failures.

### 4) Bulk audio upload service rollback visibility
Updated: `apps/content/services/admin/asset_recitation_audio_tracks_upload_service.py`

- Introduced module logger.
- Replaced silent failures while collecting uploaded file names with warnings.
- Added exception logging for top-level bulk upload failure.
- Added warning logs for rollback cleanup failures and storage import/access failures.

### 5) Bulk ayah timestamps upload diagnostics
Updated: `apps/content/services/admin/asset_recitation_ayah_timestamps_upload_service.py`

- Introduced module logger.
- Added warning logs when a JSON timing file cannot be parsed.
- Added exception logging for transaction-level upload failures.

### 6) Celery task logging standardization
Updated: `apps/content/tasks.py`

- Added helper `_task_extra(task_name, **task_args)` to standardize structured logging context.
- Replaced many string-formatted `logger.error(...)` calls with structured `logger.error(...)` / `logger.exception(...)` calls and contextual metadata.
- Added warning logs for missing assets/publishers during daily analytics aggregation.
- Added warning logs for missing `ResourceVersion` / `AssetVersion` in email tasks.

### 7) File deletion signal visibility
Updated: `apps/core/mixins/storage.py`

- Introduced module logger.
- Replaced silent exception swallowing in `post_delete` cleanup with warning logs including model/field/instance context.

### 8) Test teardown diagnostics
Updated: `apps/core/tests.py`

- Introduced module logger.
- Replaced silent teardown exceptions with warnings for storage override disable and moto stop failures.

### 9) Recitation helper logging
Updated: `apps/mixins/recitations_helpers.py`

- Introduced module logger.
- Added warning logs when file seeking fails before MP3 duration read.
- Added warning logs when MP3 duration extraction fails.

### 10) Auth endpoint exception logging
Updated:
- `apps/users/api/internal/register.py`
- `apps/users/api/internal/token_refresh.py`

- Added module loggers.
- Added `logger.exception(...)` in registration failure and refresh token rotation failure paths, including contextual metadata.

## Behavioral Impact

- Core business logic remains largely unchanged.
- Main impact is improved traceability, debugging, and operational visibility in production.
- Existing fallback behavior is preserved in most places (e.g., defaulting to `0` or continuing processing), but failures are now visible in logs.

## Notes

- This is mostly a non-breaking observability-focused refactor.
- The changes are especially valuable for diagnosing admin upload workflows, Celery task failures, and media/storage edge cases.