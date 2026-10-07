"""Text of the starter itqan-assets.yaml written by `itqan init`."""

from __future__ import annotations

import json

from apps.package_manager.cli.client import CatalogLanguage, CatalogPackage
from apps.package_manager.cli.semver import parse_semver

SAMPLE_COUNT = 3

_HEADER = """\
# Itqan assets manifest: the Quranic data this project uses.
# Spec: https://github.com/Itqan-community/cms-backend/blob/main/docs/ASSET_MANIFEST.md
#
# After editing, run `itqan install` to download the assets and write
# itqan-assets.lock. Commit both files.

schema_version: 1

# Folder the assets are downloaded into, relative to this file.
assets_dir: {assets_dir}

# Each entry is a name (the asset's slug, unless the entry sets `asset`) and a
# version range:
#   "^1.2.0"  any 1.x from 1.2.0 on    "~1.2"  any 1.2.x    "1.2.0"  exactly 1.2.0
#
# Languages: an entry installs the asset's source language. Add
# `language: <code>` to install another one. To install several languages of
# the same asset, give each its own entry and point it at the asset with
# `asset: <slug>`. Each language has its own version history.
assets:
"""

_FALLBACK_ENTRIES = """\
  # {reason} so these are examples: replace the slugs with real ones
  # from the asset library at https://cms.itqan.dev, then uncomment.
  #
  # "tafsir-example":
  #   version: "^1.0.0"
  #
  # The same asset in English:
  # "tafsir-example-en":
  #   asset: "tafsir-example"
  #   language: "en"
  #   version: "^1.0.0"
"""


def _quote(value: str) -> str:
    """YAML double-quoted scalar; slugs like `true` or `123` must stay strings."""
    return json.dumps(value, ensure_ascii=False)


def _constraint(version: str) -> str:
    """`^latest`, except a prerelease, which only an exact pin can select."""
    semver = parse_semver(version)
    return version if semver is not None and semver.prerelease is not None else f"^{version}"


def _describe(language: CatalogLanguage) -> str:
    if not language.language:  # an asset whose source language code was never set
        return f"source ({language.latest_version})"
    source = "source, " if language.is_source else ""
    return f"{language.language} ({source}{language.latest_version})"


def _entry(name: str, version: str, *, asset: str | None = None, language: str | None = None) -> list[str]:
    lines = [f"  {_quote(name)}:"]
    if asset is not None:
        lines.append(f"    asset: {_quote(asset)}")
    if language is not None:
        lines.append(f"    language: {_quote(language)}")
    lines.append(f"    version: {_quote(_constraint(version))}")
    return lines


def pick_samples(packages: list[CatalogPackage], count: int = SAMPLE_COUNT) -> list[CatalogPackage]:
    """Up to ``count`` packages, leading with one that has several languages so
    the starter file shows a second-language entry."""
    usable = [package for package in packages if package.languages]
    multilingual = next((package for package in usable if len(package.languages) > 1), None)
    ordered = ([multilingual] if multilingual else []) + [package for package in usable if package is not multilingual]
    return ordered[:count]


def render_from_catalog(samples: list[CatalogPackage], assets_dir: str) -> str:
    lines: list[str] = []
    names: set[str] = set()
    for package in samples:
        if lines:
            lines.append("")
        name = " ".join(package.name.split())  # one line, even if the name has newlines
        lines.append(f"  # {name} — languages: {', '.join(_describe(lang) for lang in package.languages)}")
        source = next((lang for lang in package.languages if lang.is_source), None)
        first = source or package.languages[0]
        lines += _entry(package.slug, first.latest_version, language=None if source else first.language)
        names.add(package.slug)
        other = next((lang for lang in package.languages if lang is not first), None)
        entry_name = f"{package.slug}-{other.language}" if other else None
        if other is not None and entry_name not in names:
            lines.append(f"  # The same asset in another language ({other.language}):")
            lines += _entry(entry_name, other.latest_version, asset=package.slug, language=other.language)
            names.add(entry_name)
    return _HEADER.format(assets_dir=_quote(assets_dir)) + "\n".join(lines) + "\n"


def render_fallback(assets_dir: str, reason: str) -> str:
    return _HEADER.format(assets_dir=_quote(assets_dir)) + _FALLBACK_ENTRIES.format(reason=reason)
