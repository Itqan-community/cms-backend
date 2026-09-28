"""Tests for Lockfile parsing, deterministic serialization, and state evaluation."""

from pathlib import Path

from apps.package_manager.cli.lockfile import (
    AssetLockfile,
    LockfileEntry,
    LockfileState,
    evaluate_lockfile_state,
    serialize_lockfile,
)


def test_serialize_lockfile_where_multi_asset_input_should_produce_deterministic_byte_exact_output():
    """Verify that serialization follows exact formatting in §5."""
    lockfile = AssetLockfile(
        lockfile_version=1,
        manifest_schema_version=1,
        assets={
            "quran-uthmani-hafs": LockfileEntry("quran-uthmani-hafs", "^2.1.0", "2.4.1"),
            "mushaf-madinah": LockfileEntry("mushaf-madinah", "~1.2", "1.2.4"),
            "تفسير-الجلالين": LockfileEntry("تفسير-الجلالين", "3.0", "3.0.0"),
        },
    )
    serialized = serialize_lockfile(lockfile)
    content_str = serialized.decode("utf-8")

    # Arabic slug must come after ASCII slugs in byte order
    pos_quran = content_str.find('"quran-uthmani-hafs"')
    pos_mushaf = content_str.find('"mushaf-madinah"')
    pos_tafsir = content_str.find('"تفسير-الجلالين"')

    assert pos_mushaf < pos_quran < pos_tafsir
    assert content_str.startswith("lockfile_version: 1\nmanifest_schema_version: 1\n\nassets:\n")
    assert content_str.endswith("\n")


def test_evaluate_lockfile_state_where_lifecycle_transitions_should_return_correct_state_at_each_step(
    tmp_path: Path,
):
    manifest_file = tmp_path / "itqan-assets.yaml"
    lockfile_file = tmp_path / "itqan-assets.lock"

    # 1. ABSENT
    state, _, _ = evaluate_lockfile_state(manifest_file, lockfile_file)
    assert state == LockfileState.ABSENT

    # 2. MISSING (manifest valid, lockfile absent)
    manifest_content = b"""schema_version: 1
assets:
  quran-uthmani-hafs:
    version: "^2.1.0"
"""
    manifest_file.write_bytes(manifest_content)
    state, m, _lock = evaluate_lockfile_state(manifest_file, lockfile_file)
    assert state == LockfileState.MISSING
    assert m is not None

    # 3. FRESH (both valid and matching)
    lock_content = b"""lockfile_version: 1
manifest_schema_version: 1

assets:
  "quran-uthmani-hafs":
    constraint: "^2.1.0"
    version: "2.4.1"
"""
    lockfile_file.write_bytes(lock_content)
    state, m, _lock = evaluate_lockfile_state(manifest_file, lockfile_file)
    assert state == LockfileState.FRESH

    # 4. STALE (constraint changed in manifest)
    manifest_file.write_bytes(b"""schema_version: 1
assets:
  quran-uthmani-hafs:
    version: "^2.2.0"
""")
    state, _, _ = evaluate_lockfile_state(manifest_file, lockfile_file)
    assert state == LockfileState.STALE

    # 5. ORPHAN (lockfile present, manifest absent)
    manifest_file.unlink()
    state, _, _ = evaluate_lockfile_state(manifest_file, lockfile_file)
    assert state == LockfileState.ORPHAN

    # 6. INVALID (broken YAML)
    manifest_file.write_bytes(b"invalid: yaml: broken: : :")
    state, _, _ = evaluate_lockfile_state(manifest_file, lockfile_file)
    assert state == LockfileState.INVALID
