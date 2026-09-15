"""Tests for strict manifest/lockfile parsing and state classification.

Pure-function tests: no database, no network. Factors combine into
:class:`DiscoveredFile` values, so the state matrix exercises
:func:`classify_discovery` exactly as the discovery service calls it.
"""

from __future__ import annotations

import pytest

from apps.dependabot.services.github_client import LOCKFILE_PATH, MANIFEST_PATH, DiscoveredFile
from apps.dependabot.services.manifest_parse import (
    ManifestDocumentError,
    classify_discovery,
    parse_lockfile_document,
    parse_manifest_document,
)

MANIFEST_SHA = "a" * 40
LOCKFILE_SHA = "b" * 40


def _present(path: str, sha: str, text: str) -> DiscoveredFile:
    return DiscoveredFile(path=path, present=True, sha=sha, content=text.encode("utf-8"))


def _absent(path: str) -> DiscoveredFile:
    return DiscoveredFile(path=path, present=False, sha=None, content=None)


def _unreadable(path: str) -> DiscoveredFile:
    return DiscoveredFile(path=path, present=True, sha=None, content=None)


def _manifest(*entries: str) -> bytes:
    body = "\n".join(["schema_version: 1", "", "assets:"] + [f"  {line}" for line in entries])
    return (body + "\n").encode("utf-8")


def _lockfile(*entries: str) -> bytes:
    body = "\n".join(
        ["lockfile_version: 1", "manifest_schema_version: 1", "", "assets:"] + [f"  {line}" for line in entries]
    )
    return (body + "\n").encode("utf-8")


def _classify(manifest_bytes: bytes | None, lockfile_bytes: bytes | None):
    manifest = (
        _absent(MANIFEST_PATH)
        if manifest_bytes is None
        else _present(MANIFEST_PATH, MANIFEST_SHA, manifest_bytes.decode("utf-8"))
    )
    lockfile = (
        _absent(LOCKFILE_PATH)
        if lockfile_bytes is None
        else _present(LOCKFILE_PATH, LOCKFILE_SHA, lockfile_bytes.decode("utf-8"))
    )
    return classify_discovery(manifest=manifest, lockfile=lockfile)


# --- YAML 1.2 Core Schema behavior ---


@pytest.mark.parametrize("slug", ["on", "off", "yes", "no", "y", "n", "On", "OFF", "1_0", "1:30"])
def test_parse_manifest_where_slug_is_yaml11_only_form_stays_string(slug):
    # Underscore numerics and sexagesimal match no YAML 1.2 Core resolver,
    # so they stay strings (unlike stock PyYAML 1.1, which reads 1:30 as 90).
    parsed = parse_manifest_document(_manifest(f"{slug}:", '    version: "1.0.0"'))
    assert slug in parsed.assets


@pytest.mark.parametrize(
    "slug",
    [
        "true",
        "True",
        "TRUE",
        "false",
        "null",
        "Null",
        "123",
        "1.5",
        "0o17",
        "0x1A",
        "010",
        ".inf",
        "-.Inf",
        "+.INF",
        ".nan",
        ".NaN",
        ".NAN",
    ],
)
def test_parse_manifest_where_slug_resolves_non_string_rejected(slug):
    # 010 matches the Core Schema decimal form [-+]?[0-9]+ (spec §10.3.2),
    # exactly like 123: unquoted non-string keys are rejected.
    with pytest.raises(ManifestDocumentError) as exc_info:
        parse_manifest_document(_manifest(f"{slug}:", '    version: "1.0.0"'))
    assert exc_info.value.code == "non_string_key"


def test_parse_manifest_where_schema_version_true_rejected_as_bool():
    with pytest.raises(ManifestDocumentError) as exc_info:
        parse_manifest_document(b"schema_version: true\nassets: {}\n")
    assert exc_info.value.code == "unsupported_version"


@pytest.mark.parametrize(
    "text",
    [
        "schema_version: 1\nassets: {}\n---\nfoo: bar\n",
        "schema_version: 1\nschema_version: 1\nassets: {}\n",
        "   \n",
        "schema_version: 1\nassets:\n  a: &x 1\n",
    ],
)
def test_parse_manifest_where_strict_profile_violated_rejected(text):
    with pytest.raises(ManifestDocumentError):
        parse_manifest_document(text.encode("utf-8"))


def test_parse_manifest_where_bom_rejected():
    with pytest.raises(ManifestDocumentError) as exc_info:
        parse_manifest_document(b"\xef\xbb\xbfschema_version: 1\nassets: {}\n")
    assert exc_info.value.code == "encoding"


def test_parse_manifest_where_non_utf8_rejected():
    with pytest.raises(ManifestDocumentError) as exc_info:
        parse_manifest_document("schema_version: 1\nassets: {}\n".encode("utf-16"))
    assert exc_info.value.code == "encoding"


def test_parse_manifest_where_custom_tag_rejected():
    with pytest.raises(ManifestDocumentError):
        parse_manifest_document(b"schema_version: !custom 1\nassets: {}\n")


def test_parse_manifest_where_scalar_shorthand_entry_rejected():
    with pytest.raises(ManifestDocumentError) as exc_info:
        parse_manifest_document(_manifest('quran-hafs: "^2.1.0"'))
    assert exc_info.value.code == "entry"


# --- Manifest structural validation ---


def test_parse_manifest_where_valid_with_reserved_package():
    parsed = parse_manifest_document(_manifest("quran-hafs:", '    version: "^2.1.0"', '    package: "itqan/hafs"'))
    assert parsed.schema_version == 1
    assert parsed.assets["quran-hafs"].version == "^2.1.0"
    assert parsed.assets["quran-hafs"].package == "itqan/hafs"


def test_parse_manifest_where_empty_assets_valid():
    assert parse_manifest_document(b"schema_version: 1\nassets: {}\n").assets == {}


@pytest.mark.parametrize(
    "text",
    [
        b"assets: {}\n",
        b"schema_version: 1\n",
        b"schema_version: 2\nassets: {}\n",
        b'schema_version: "1"\nassets: {}\n',
        b"schema_version: 1\nassets: {}\nextra: 1\n",
        b"schema_version: 1\nassets: []\n",
        b"schema_version: 1\nassets:\n  a:\n    package: x\n",
        b"schema_version: 1\nassets:\n  a:\n    version: ^1.0.0\n    bogus: 1\n",
        b"schema_version: 1\nassets:\n  a:\n    version: 1.0.0\n    package: ''\n",
    ],
)
def test_parse_manifest_where_invalid_rejected(text):
    with pytest.raises(ManifestDocumentError):
        parse_manifest_document(text)


@pytest.mark.parametrize(
    "constraint",
    [">=1.0.0", "*", "v1.2.3", "2", "^2", "1.2-beta.1", "^1.2.3-beta.1", "1.2.3+build1", "01.2.0"],
)
def test_parse_manifest_where_constraint_outside_grammar_rejected(constraint):
    with pytest.raises(ManifestDocumentError) as exc_info:
        parse_manifest_document(_manifest("a:", f'    version: "{constraint}"'))
    assert exc_info.value.code == "version"


@pytest.mark.parametrize("constraint", ["1.2.3", "2.0", "1.2.3-beta.1", "^1.2.3", "^0.2", "~1.2", "~0.0.1"])
def test_parse_manifest_where_constraint_in_grammar_accepted(constraint):
    parsed = parse_manifest_document(_manifest("a:", f'    version: "{constraint}"'))
    assert parsed.assets["a"].version == constraint


# --- Lockfile structural validation ---


def test_parse_lockfile_where_valid():
    parsed = parse_lockfile_document(_lockfile('"a":', '    constraint: "^1.0.0"', '    version: "1.2.4"'))
    assert parsed.lockfile_version == 1
    assert parsed.manifest_schema_version == 1
    assert parsed.assets["a"].constraint == "^1.0.0"
    assert parsed.assets["a"].version == "1.2.4"


@pytest.mark.parametrize(
    "version",
    ["3.0", "1.2", "1.2.3+build1", "draft-2", "v1.0.0", "1.2.3.4", ""],
)
def test_parse_lockfile_where_version_not_canonical_rejected(version):
    with pytest.raises(ManifestDocumentError) as exc_info:
        parse_lockfile_document(_lockfile('"a":', '    constraint: "^1.0.0"', f'    version: "{version}"'))
    assert exc_info.value.code == "version"


@pytest.mark.parametrize("version", ["1.2.3", "3.0.0", "1.2.3-beta.1", "0.0.0"])
def test_parse_lockfile_where_canonical_version_accepted(version):
    parsed = parse_lockfile_document(_lockfile('"a":', '    constraint: "^1.0.0"', f'    version: "{version}"'))
    assert parsed.assets["a"].version == version


def test_parse_lockfile_where_constraint_outside_grammar_rejected():
    with pytest.raises(ManifestDocumentError) as exc_info:
        parse_lockfile_document(_lockfile('"a":', '    constraint: ">=1.0.0"', '    version: "1.2.4"'))
    assert exc_info.value.code == "constraint"


# --- State matrix ---


def test_classify_where_neither_file_present_is_absent():
    result = classify_discovery(manifest=_absent(MANIFEST_PATH), lockfile=_absent(LOCKFILE_PATH))
    assert result.state == "ABSENT"
    assert result.manifest is None and result.lockfile is None


@pytest.mark.parametrize(
    "manifest_bytes, lockfile_bytes",
    [
        (b"schema_version: true\nassets: {}\n", None),
        (b"schema_version: true\nassets: {}\n", _lockfile('"a":', '    constraint: "1.0.0"', '    version: "1.0.0"')),
        (
            _manifest("a:", '    version: "^1.0.0"'),
            b"lockfile_version: 1\nmanifest_schema_version: 1\nassets: {}\nbad_indent:\n bad",
        ),
        (None, b"not: [valid"),
    ],
)
def test_classify_where_invalid_precedes_all_other_states(manifest_bytes, lockfile_bytes):
    assert _classify(manifest_bytes, lockfile_bytes).state == "INVALID"


def test_classify_where_unreadable_manifest_with_valid_lockfile_is_invalid_not_orphan():
    manifest = _unreadable(MANIFEST_PATH)
    lockfile = _present(
        LOCKFILE_PATH, LOCKFILE_SHA, _lockfile('"a":', '    constraint: "1.0.0"', '    version: "1.0.0"').decode()
    )
    assert classify_discovery(manifest=manifest, lockfile=lockfile).state == "INVALID"


def test_classify_where_valid_lockfile_without_manifest_is_orphan():
    result = _classify(None, _lockfile('"a":', '    constraint: "1.0.0"', '    version: "1.0.0"'))
    assert result.state == "ORPHAN"
    assert result.manifest is None and result.lockfile is not None


def test_classify_where_valid_manifest_without_lockfile_is_missing():
    result = _classify(_manifest("a:", '    version: "^1.0.0"'), None)
    assert result.state == "MISSING"
    assert result.manifest is not None and result.lockfile is None


@pytest.mark.parametrize(
    "manifest_entries, lockfile_entries",
    [
        # Asset key-set mismatch: added.
        (
            ["a:", '    version: "1.0.0"', "b:", '    version: "1.0.0"'],
            ['"a":', '    constraint: "1.0.0"', '    version: "1.0.0"'],
        ),
        # Asset key-set mismatch: removed.
        (
            ["a:", '    version: "1.0.0"'],
            [
                '"a":',
                '    constraint: "1.0.0"',
                '    version: "1.0.0"',
                '"b":',
                '    constraint: "1.0.0"',
                '    version: "1.0.0"',
            ],
        ),
        # Constraint text mismatch (equivalent range, different text).
        (
            ["a:", '    version: "~1.2.0"'],
            ['"a":', '    constraint: "~1.2"', '    version: "1.2.4"'],
        ),
        # Locked version no longer satisfies the recorded constraint.
        (
            ["a:", '    version: "^1.2.0"'],
            ['"a":', '    constraint: "^1.2.0"', '    version: "2.0.0"'],
        ),
        # Prerelease isolation: stable range never selects the locked prerelease.
        (
            ["a:", '    version: "^1.0.0"'],
            ['"a":', '    constraint: "^1.0.0"', '    version: "1.5.0-alpha.1"'],
        ),
    ],
)
def test_classify_where_mismatch_is_stale(manifest_entries, lockfile_entries):
    assert _classify(_manifest(*manifest_entries), _lockfile(*lockfile_entries)).state == "STALE"


@pytest.mark.parametrize(
    "manifest_entries, lockfile_entries",
    [
        (
            ["quran-hafs:", '    version: "^2.1.0"'],
            ['"quran-hafs":', '    constraint: "^2.1.0"', '    version: "2.4.1"'],
        ),
        (
            ["mushaf-madinah:", '    version: "~1.2"'],
            ['"mushaf-madinah":', '    constraint: "~1.2"', '    version: "1.2.4"'],
        ),
        (
            ["tajweed-rules:", '    version: "^0.4.0"', '    package: "itqan/tajweed"'],
            ['"tajweed-rules":', '    constraint: "^0.4.0"', '    version: "0.4.7"'],
        ),
        # Exact prerelease pin matches its own draft.
        (
            ["app-theme:", '    version: "2.0.0-beta.1"'],
            ['"app-theme":', '    constraint: "2.0.0-beta.1"', '    version: "2.0.0-beta.1"'],
        ),
        # Unicode slugs compare byte-for-byte.
        (
            ["تفسير-الجلالين:", '    version: "3.0"'],
            ['"تفسير-الجلالين":', '    constraint: "3.0"', '    version: "3.0.0"'],
        ),
    ],
)
def test_classify_where_matching_pair(manifest_entries, lockfile_entries):
    result = _classify(_manifest(*manifest_entries), _lockfile(*lockfile_entries))
    assert result.state == "FRESH"
    assert result.manifest is not None and result.lockfile is not None


def test_classify_where_empty_manifest_and_empty_lockfile_is_fresh():
    result = _classify(
        b"schema_version: 1\nassets: {}\n", b"lockfile_version: 1\nmanifest_schema_version: 1\nassets: {}\n"
    )
    assert result.state == "FRESH"
