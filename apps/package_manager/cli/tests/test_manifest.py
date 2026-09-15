"""Tests for Asset Manifest parser adhering to docs/ASSET_MANIFEST.md §2-§3."""

import pytest

from apps.package_manager.cli.exceptions import (
    InvalidConstraintSyntaxError,
    MissingRequiredFieldError,
    ScalarShorthandEntryError,
    UnknownFieldError,
    UnsupportedSchemaVersionError,
    YamlProfileViolationError,
)
from apps.package_manager.cli.manifest import parse_manifest_content


def test_parse_manifest_content_where_valid_yaml_should_return_manifest_with_all_assets():
    content = b"""schema_version: 1

assets:
  quran-uthmani-hafs:
    version: "^2.1.0"
  mushaf-madinah:
    version: "~1.2"
  "\xd8\xaa\xd9\x81\xd8\xb3\xd9\x8a\xd8\xb1-\xd8\xa7\xd9\x84\xd8\xac\xd9\x84\xd8\xa7\xd9\x84\xd9\x8a\xd9\x86":
    version: "3.0"
  tajweed-rules:
    version: "^0.4.0"
    package: "itqan/tajweed-rules"
"""
    manifest = parse_manifest_content(content)
    assert manifest.schema_version == 1
    assert len(manifest.assets) == 4
    assert manifest.assets["quran-uthmani-hafs"].version == "^2.1.0"
    assert manifest.assets["mushaf-madinah"].version == "~1.2"
    assert manifest.assets["تفسير-الجلالين"].version == "3.0"
    assert manifest.assets["tajweed-rules"].package == "itqan/tajweed-rules"


def test_parse_manifest_content_where_file_is_empty_should_raise_yaml_profile_violation():
    with pytest.raises(YamlProfileViolationError, match="empty or contains only whitespace"):
        parse_manifest_content(b"")


def test_parse_manifest_content_where_file_has_utf8_bom_should_raise_yaml_profile_violation():
    with pytest.raises(YamlProfileViolationError, match="BOM"):
        parse_manifest_content(b"\xef\xbb\xbfschema_version: 1\nassets: {}\n")


def test_parse_manifest_content_where_schema_version_absent_should_raise_unsupported_schema_version():
    with pytest.raises(UnsupportedSchemaVersionError):
        parse_manifest_content(b"assets: {}\n")


def test_parse_manifest_content_where_schema_version_is_unknown_should_raise_unsupported_schema_version():
    with pytest.raises(UnsupportedSchemaVersionError):
        parse_manifest_content(b"schema_version: 2\nassets: {}\n")


def test_parse_manifest_content_where_asset_uses_scalar_shorthand_should_raise_scalar_shorthand_error():
    content = b"""schema_version: 1
assets:
  quran-uthmani-hafs: "^2.1.0"
"""
    with pytest.raises(ScalarShorthandEntryError):
        parse_manifest_content(content)


def test_parse_manifest_content_where_version_field_missing_should_raise_missing_required_field():
    content = b"""schema_version: 1
assets:
  quran-uthmani-hafs:
    package: "foo/bar"
"""
    with pytest.raises(MissingRequiredFieldError):
        parse_manifest_content(content)


def test_parse_manifest_content_where_constraint_uses_unsupported_operator_should_raise_invalid_constraint():
    content = b"""schema_version: 1
assets:
  quran-uthmani-hafs:
    version: ">=1.0.0"
"""
    with pytest.raises(InvalidConstraintSyntaxError):
        parse_manifest_content(content)


def test_parse_manifest_content_where_top_level_unknown_field_present_should_raise_unknown_field():
    content = b"""schema_version: 1
extra_key: "not allowed"
assets: {}
"""
    with pytest.raises(UnknownFieldError):
        parse_manifest_content(content)
