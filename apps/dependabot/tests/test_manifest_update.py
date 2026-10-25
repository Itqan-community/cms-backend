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


QA_BLOCK = [
    "  # itqan:columns CSV, one row per ayah: surah, ayah, question, answer",
    "  # itqan:columns   question: Question",
]


def _block(indent: str) -> list[str]:
    return [line.replace("  ", indent, 1) for line in QA_BLOCK]


def test_update_manifest_content_where_columns_comment_should_insert_block_above_entry():
    manifest = b'schema_version: 1\n\nassets:\n  qa:\n    version: "^1.0.0"\n'

    updated = update_manifest_content(manifest, "qa", "^2.0.0", columns_comment=_block).decode()

    assert updated == (
        "schema_version: 1\n\nassets:\n"
        "  # itqan:columns CSV, one row per ayah: surah, ayah, question, answer\n"
        "  # itqan:columns   question: Question\n"
        '  qa:\n    version: "^2.0.0"\n'
    )


def test_update_manifest_content_where_old_block_and_user_comment_should_replace_block_only():
    manifest = (
        b"schema_version: 1\n\nassets:\n"
        b"  # pinned for the quiz screen\n"
        b"  # itqan:columns CSV, one row per ayah: surah, ayah, question\n"
        b'  qa:\n    version: "^1.0.0"\n'
    )

    updated = update_manifest_content(manifest, "qa", "^1.0.0", columns_comment=_block).decode()

    assert updated == (
        "schema_version: 1\n\nassets:\n"
        "  # pinned for the quiz screen\n"
        "  # itqan:columns CSV, one row per ayah: surah, ayah, question, answer\n"
        "  # itqan:columns   question: Question\n"
        '  qa:\n    version: "^1.0.0"\n'
    )


def test_update_manifest_content_where_columns_comment_returns_nothing_should_remove_block():
    manifest = (
        b"schema_version: 1\n\nassets:\n"
        b"  # itqan:columns CSV, one row per ayah: surah, ayah, question\n"
        b'  qa:\n    version: "^1.0.0"\n'
    )

    updated = update_manifest_content(manifest, "qa", "^1.0.0", columns_comment=lambda indent: []).decode()

    assert updated == 'schema_version: 1\n\nassets:\n  qa:\n    version: "^1.0.0"\n'


def test_update_manifest_content_where_no_columns_comment_should_leave_comments_byte_identical():
    manifest = (
        b"schema_version: 1\n\nassets:\n"
        b"  # itqan:columns CSV, one row per ayah: surah, ayah, question\n"
        b'  qa:\n    version: "^1.0.0"\n'
    )

    updated = update_manifest_content(manifest, "qa", "^1.0.0")

    assert updated == manifest


def test_update_manifest_content_where_columns_comment_on_other_entry_should_not_touch_it():
    manifest = (
        b"schema_version: 1\n\nassets:\n"
        b"  # itqan:columns CSV, one row per ayah: surah, ayah, a, b\n"
        b'  other:\n    version: "^1.0.0"\n'
        b'  qa:\n    version: "^1.0.0"\n'
    )

    updated = update_manifest_content(manifest, "qa", "^1.0.0", columns_comment=_block).decode()

    assert "  # itqan:columns CSV, one row per ayah: surah, ayah, a, b\n  other:" in updated
    assert updated.endswith(
        "  # itqan:columns CSV, one row per ayah: surah, ayah, question, answer\n"
        "  # itqan:columns   question: Question\n"
        '  qa:\n    version: "^1.0.0"\n'
    )


def test_refresh_columns_comment_where_version_unquoted_should_keep_version_line_byte_identical():
    from apps.dependabot.services.manifest_update import refresh_columns_comment

    manifest = b"schema_version: 1\n\nassets:\n  qa:\n    version: ^1.0.0  # pinned\n"

    updated = refresh_columns_comment(manifest, "qa", _block).decode()

    assert updated == (
        "schema_version: 1\n\nassets:\n"
        "  # itqan:columns CSV, one row per ayah: surah, ayah, question, answer\n"
        "  # itqan:columns   question: Question\n"
        "  qa:\n    version: ^1.0.0  # pinned\n"
    )


def test_refresh_columns_comment_where_block_current_should_return_same_bytes():
    from apps.dependabot.services.manifest_update import refresh_columns_comment

    manifest = ("schema_version: 1\n\nassets:\n" + "\n".join(QA_BLOCK) + "\n  qa:\n    version: ^1.0.0\n").encode()

    assert refresh_columns_comment(manifest, "qa", _block) == manifest


def test_refresh_columns_comment_where_manifest_uses_crlf_should_write_block_with_crlf():
    from apps.dependabot.services.manifest_update import refresh_columns_comment

    manifest = b"schema_version: 1\r\n\r\nassets:\r\n  qa:\r\n    version: ^1.0.0\r\n"

    updated = refresh_columns_comment(manifest, "qa", _block)

    assert b"  # itqan:columns   question: Question\r\n  qa:\r\n" in updated
    assert updated.count(b"\n") == updated.count(b"\r\n")
