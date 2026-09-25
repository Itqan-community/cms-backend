"""Tests for manifest and lockfile update helpers."""

import pytest

from apps.dependabot.services.manifest_parse import (
    ManifestDocumentError,
    parse_lockfile_document,
    parse_manifest_document,
)
from apps.dependabot.services.manifest_update import (
    serialize_updated_lockfile,
    update_manifest_content,
)

SAMPLE_MANIFEST = b"""# Initial comment
schema_version: 1

assets:
  # Leading comment for hafs
  quran-uthmani-hafs:
    version: "^1.2.0" # inline comment
    package: "itqan/quran"

  tafsir-muyassar:
    version: "1.0.0"
"""

SAMPLE_LOCKFILE = b"""lockfile_version: 1
manifest_schema_version: 1

assets:
  "quran-uthmani-hafs":
    constraint: "^1.2.0"
    version: "1.2.3"
  "tafsir-muyassar":
    constraint: "1.0.0"
    version: "1.0.0"
"""


def test_update_manifest_content_preserves_comments_and_updates_version():
    updated_bytes = update_manifest_content(SAMPLE_MANIFEST, "quran-uthmani-hafs", "^1.3.0")
    text = updated_bytes.decode("utf-8")

    assert "# Initial comment" in text
    assert "# Leading comment for hafs" in text
    assert 'version: "^1.3.0" # inline comment' in text
    assert 'version: "1.0.0"' in text

    # Verify that parse_manifest_document succeeds on it
    parsed = parse_manifest_document(updated_bytes)
    assert parsed.assets["quran-uthmani-hafs"].version == "^1.3.0"
    assert parsed.assets["tafsir-muyassar"].version == "1.0.0"


def test_update_manifest_content_slug_not_found_raises():
    with pytest.raises(ManifestDocumentError) as exc_info:
        update_manifest_content(SAMPLE_MANIFEST, "nonexistent-asset", "2.0.0")
    assert exc_info.value.code == "slug_not_found"


def test_update_manifest_content_supports_inline_flow_mapping():
    manifest = b"""# Inline test
schema_version: 1

assets:
  quran-uthmani-hafs: {version: "^1.2.0", package: "itqan/quran"} # flow style
  tafsir-muyassar: { version: '1.0.0' }
"""
    updated_bytes = update_manifest_content(manifest, "quran-uthmani-hafs", "^2.0.0")
    text = updated_bytes.decode("utf-8")

    assert "# flow style" in text
    assert 'version: "^2.0.0"' in text

    parsed = parse_manifest_document(updated_bytes)
    assert parsed.assets["quran-uthmani-hafs"].version == "^2.0.0"
    assert parsed.assets["tafsir-muyassar"].version == "1.0.0"


def test_serialize_updated_lockfile_updates_target_and_preserves_others():
    parsed_lock = parse_lockfile_document(SAMPLE_LOCKFILE)
    updated_bytes = serialize_updated_lockfile(
        parsed_lock,
        slug="quran-uthmani-hafs",
        new_constraint="^1.3.0",
        new_version="1.3.0",
    )

    reparsed = parse_lockfile_document(updated_bytes)
    assert reparsed.assets["quran-uthmani-hafs"].constraint == "^1.3.0"
    assert reparsed.assets["quran-uthmani-hafs"].version == "1.3.0"
    assert reparsed.assets["tafsir-muyassar"].version == "1.0.0"
