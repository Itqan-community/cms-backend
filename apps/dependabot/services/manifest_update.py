"""Manifest and lockfile document update helpers for PR automation.

Strictly preserves user formatting and comments in ``itqan-assets.yaml``,
and generates deterministic, canonical lockfile bytes for ``itqan-assets.lock``
per docs/ASSET_MANIFEST.md §2, §3, and §5.
"""

from __future__ import annotations

from collections.abc import Callable
import re

from apps.dependabot.services.manifest_parse import (
    LockfileEntry,
    ManifestDocumentError,
    ParsedLockfile,
    parse_lockfile_document,
    parse_manifest_document,
)
from apps.package_manager.services.columns_comment import MARKER as COLUMNS_COMMENT_MARKER


def update_manifest_content(
    raw_manifest: bytes,
    slug: str,
    new_constraint: str,
    *,
    columns_comment: Callable[[str], list[str]] | None = None,
) -> bytes:
    """Update the version constraint for an asset in ``itqan-assets.yaml``.

    Preserves comments, whitespace, and surrounding keys. When ``columns_comment``
    is given, it is called with the entry key's indentation and the
    ``# itqan:columns`` lines directly above the entry are replaced by the lines it
    returns (``[]`` removes them); every other comment is left alone. Flow-style
    entries get no block.
    Validates the modified document using :func:`parse_manifest_document`.
    Raises :class:`ManifestDocumentError` if the slug is not found or if the
    resulting document is invalid.
    """
    try:
        text = raw_manifest.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestDocumentError("encoding", "Manifest must be UTF-8 encoded.") from exc

    lines = text.splitlines(keepends=True)
    in_assets_block = False
    in_target_slug = False
    target_indent: int | None = None
    updated = False
    new_lines: list[str] = []

    slug_re = re.compile(r"^(\s*)(?:\"([^\"]+)\"|'([^']+)'|([^\s:]+))\s*:\s*(?:#.*)?$")
    flow_slug_re = re.compile(r"^(\s*)(?:\"([^\"]+)\"|'([^']+)'|([^\s:]+))\s*:\s*\{([^}]*)\}(.*)$")
    flow_ver_re = re.compile(r"""(\bversion\s*:\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,}]+)""")
    version_re = re.compile(r"^(\s*)version\s*:\s*(?:\"[^\"]*\"|'[^']*'|[^\s#]+)(.*)$")

    for line in lines:
        stripped = line.strip()

        # Check for start of assets block
        if not in_assets_block:
            if re.match(r"^assets\s*:\s*(?:#.*)?$", stripped):
                in_assets_block = True
            new_lines.append(line)
            continue

        # If we are in assets block, check indentation of keys
        if not in_target_slug:
            # Check if this line is an inline flow mapping
            m_flow = flow_slug_re.match(line)
            if m_flow:
                key = m_flow.group(2) or m_flow.group(3) or m_flow.group(4)
                if key == slug:
                    flow_content = m_flow.group(5)
                    if flow_ver_re.search(flow_content):
                        line = flow_ver_re.sub(rf'\g<1>"{new_constraint}"', line, count=1)
                        updated = True
                    else:
                        raise ManifestDocumentError("slug_not_found", f"Asset slug '{slug}' has no version field.")
                new_lines.append(line)
                continue

            # Check if this line is a block asset key under assets:
            m = slug_re.match(line)
            if m:
                indent = len(m.group(1))
                key = m.group(2) or m.group(3) or m.group(4)
                if key == slug:
                    in_target_slug = True
                    target_indent = indent
                    if columns_comment is not None:
                        _replace_columns_comment(new_lines, columns_comment(m.group(1)))
            new_lines.append(line)
            continue

        # We are inside the target slug
        # Check if we moved to another key with indent <= target_indent
        m_slug = slug_re.match(line)
        if m_slug:
            indent = len(m_slug.group(1))
            if indent <= (target_indent or 0):
                # We left the target slug without updating version
                in_target_slug = False
                new_lines.append(line)
                continue

        # Check if this is the version line
        m_ver = version_re.match(line)
        if m_ver and not updated:
            v_indent = m_ver.group(1)
            v_comment = m_ver.group(2)
            new_lines.append(
                f'{v_indent}version: "{new_constraint}"{v_comment}\n'
                if line.endswith("\n")
                else f'{v_indent}version: "{new_constraint}"{v_comment}'
            )
            updated = True
            in_target_slug = False
            continue

        new_lines.append(line)

    if not updated:
        raise ManifestDocumentError("slug_not_found", f"Asset slug '{slug}' not found in manifest to update.")

    result_text = "".join(new_lines)
    result_bytes = result_text.encode("utf-8")

    # Strictly validate that the updated manifest is compliant with YAML 1.2 Core Schema & §2
    parse_manifest_document(result_bytes)
    return result_bytes


def refresh_columns_comment(raw_manifest: bytes, slug: str, columns_comment: Callable[[str], list[str]]) -> bytes:
    """``raw_manifest`` with only the ``# itqan:columns`` block above entry ``slug``
    replaced — every other byte, the version line included, is kept. Returns the
    input unchanged when the block is already current, or when ``slug`` has no
    block-style entry.

    Raises :class:`ManifestDocumentError` if the manifest isn't UTF-8 or the result is invalid.
    """
    try:
        text = raw_manifest.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestDocumentError("encoding", "Manifest must be UTF-8 encoded.") from exc
    lines = text.splitlines(keepends=True)
    key_re = re.compile(r"^(\s*)(?:\"([^\"]+)\"|'([^']+)'|([^\s:]+))\s*:\s*(?:#.*)?$")
    start = next((i for i, line in enumerate(lines) if re.match(r"^assets\s*:\s*(?:#.*)?$", line.strip())), None)
    if start is None:
        return raw_manifest
    for index in range(start + 1, len(lines)):
        match = key_re.match(lines[index].rstrip("\n"))
        if match and (match.group(2) or match.group(3) or match.group(4)) == slug and match.group(1):
            head = lines[:index]
            _replace_columns_comment(head, columns_comment(match.group(1)))
            result = "".join(head + lines[index:]).encode("utf-8")
            if result == raw_manifest:
                return raw_manifest
            parse_manifest_document(result)
            return result
    return raw_manifest


def _replace_columns_comment(lines: list[str], block: list[str]) -> None:
    """Swap the marker lines at the end of ``lines`` (those directly above the
    entry key about to be appended) for ``block``, ending its lines like the
    manifest's (CRLF or LF)."""
    newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
    while lines and lines[-1].lstrip().startswith(COLUMNS_COMMENT_MARKER):
        lines.pop()
    lines.extend(f"{line}{newline}" for line in block)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def serialize_updated_lockfile(lockfile: ParsedLockfile, slug: str, new_constraint: str, new_version: str) -> bytes:
    """Generate byte-exact deterministic lockfile UTF-8 bytes adhering to §5.

    Updates the constraint and version for ``slug``, preserving all other entries.
    Validates output using :func:`parse_lockfile_document`.
    """
    lines = [
        f"lockfile_version: {lockfile.lockfile_version}",
        f"manifest_schema_version: {lockfile.manifest_schema_version}",
        "",
    ]
    assets: dict[str, LockfileEntry] = dict(lockfile.assets)
    current = assets.get(slug)
    assets[slug] = LockfileEntry(
        constraint=new_constraint,
        version=new_version,
        asset=current.asset if current else None,
        language=current.language if current else None,
    )

    lines.append("assets:")
    sorted_slugs = sorted(assets.keys(), key=lambda s: s.encode("utf-8"))
    for s in sorted_slugs:
        entry = assets[s]
        lines.append(f'  "{_escape(s)}":')
        for field in ("asset", "language"):
            value = getattr(entry, field)
            if value is not None:
                lines.append(f'    {field}: "{_escape(value)}"')
        lines.append(f'    constraint: "{_escape(entry.constraint)}"')
        lines.append(f'    version: "{_escape(entry.version)}"')

    lines.append("")
    serialized = "\n".join(lines).encode("utf-8")

    # Strictly validate against §5
    parse_lockfile_document(serialized)
    return serialized
