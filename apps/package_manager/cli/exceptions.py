"""CLI exceptions adhering to docs/ASSET_MANIFEST.md error taxonomy."""

from __future__ import annotations


class ItqanCliError(Exception):
    """Base exception for all Itqan CLI errors."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class ManifestError(ItqanCliError):
    """Base exception for manifest parsing/validation failures."""


class UnsupportedSchemaVersionError(ManifestError):
    """schema_version is missing or not 1."""


class YamlProfileViolationError(ManifestError):
    """YAML violates the strict profile (BOM, duplicate keys, multiple docs, etc.)."""


class ScalarShorthandEntryError(ManifestError):
    """An entry under assets is a scalar instead of a mapping."""


class NonStringAssetKeyError(ManifestError):
    """An asset key resolves to a non-string scalar (bool, int, float)."""


class UnknownFieldError(ManifestError):
    """Any key outside the accepted schema."""


class MissingRequiredFieldError(ManifestError):
    """An entry has no required 'version' field."""


class InvalidConstraintSyntaxError(ManifestError):
    """Constraint string violates the SemVer grammar."""


class LockfileError(ItqanCliError):
    """Base exception for lockfile operations."""


class LockfileStateError(LockfileError):
    """Lockfile is in an unexpected or invalid state."""


class RegistryApiError(ItqanCliError):
    """Error communicating with the Package Registry API."""

    def __init__(self, message: str, *, status_code: int | None = None, error_name: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_name = error_name


class DownloadError(ItqanCliError):
    """Error downloading or verifying an asset artifact."""
