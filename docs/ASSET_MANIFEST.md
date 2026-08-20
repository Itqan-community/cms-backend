# Itqan Asset Manifest and Version Pinning

**Status**: Proposed V1 — pending maintainer approval on [#416](https://github.com/Itqan-community/cms-backend/issues/416)
**Manifest schema version**: 1 · **Lockfile version**: 1

This document defines how an application declares which Itqan assets it uses and at which
versions, and how those declarations resolve to concrete `AssetVersion` records.

It is a **contract, not an implementation**. Nothing in this document ships code. The
registry API ([#417](https://github.com/Itqan-community/cms-backend/issues/417)), the CLI
installer ([#422](https://github.com/Itqan-community/cms-backend/issues/422)), artifact
packaging ([#425](https://github.com/Itqan-community/cms-backend/issues/425)) and the
Dependabot-style updater ([#427](https://github.com/Itqan-community/cms-backend/issues/427))
each implement against it.

---

## Table of contents

1. [What this is and why](#1-what-this-is-and-why)
2. [The manifest: `itqan-assets.yaml`](#2-the-manifest-itqan-assetsyaml)
3. [Version constraints](#3-version-constraints)
4. [How a constraint resolves to a concrete version](#4-how-a-constraint-resolves-to-a-concrete-version)
5. [The lockfile: `itqan-assets.lock`](#5-the-lockfile-itqan-assetslock)
6. [Worked resolution walkthrough](#6-worked-resolution-walkthrough)
7. [Prereleases and "update available", in plain language](#7-prereleases-and-update-available-in-plain-language)
8. [What this specification does not cover](#8-what-this-specification-does-not-cover)
9. [Future: publisher-chosen package names](#9-future-publisher-chosen-package-names)
10. [Appendix: current backend behavior](#appendix-current-backend-behavior)

---

## 1. What this is and why

Today, an application that uses an Itqan asset bundles it once and never updates it. There is
no record of *which* assets an app depends on or *which* versions it expects, so there is
nothing to check for updates against. Two files fix that.

**`itqan-assets.yaml` — the manifest.** Human-authored, committed to your repository root.
It says *what you allow*: a list of assets and, for each, the range of versions acceptable to
you. You edit this file by hand.

**`itqan-assets.lock` — the lockfile.** Machine-generated, committed next to the manifest. It
says *what was actually chosen*: the exact version each of those constraints resolved to the
last time resolution ran. You never edit this file by hand; you edit the manifest and
regenerate.

The split is the whole point. The manifest expresses intent that survives new releases
("any 1.2.x is fine"); the lockfile guarantees that your teammate, your CI runner and your
production build all get the *same* bytes you got. Without the lockfile, "any 1.2.x" silently
means something different next week. This is the same manifest/lockfile split you already
know from `pubspec.yaml`/`pubspec.lock` and `package.json`/`package-lock.json`.

Both files live at the **root** of the consuming application's repository. V1 supports
exactly one manifest per repository.

---

## 2. The manifest: `itqan-assets.yaml`

```yaml
schema_version: 1

assets:
  quran-uthmani-hafs:
    version: "^2.1.0"

  # A book doesn't really have a "patch" number. Two numbers is fine —
  # `~1.2` is read as `~1.2.0`.
  mushaf-madinah:
    version: "~1.2"

  # Slugs may be Unicode. They are matched exactly, character for character.
  تفسير-الجلالين:
    version: "3.0"

  # `package` is reserved for future publisher-chosen names.
  # It is validated but has no effect in V1. See §9.
  tajweed-rules:
    version: "^0.4.0"
    package: "itqan/tajweed-rules"
```

### Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | integer | yes | Must be `1`. Identifies the manifest format. |
| `assets` | mapping | yes | Asset slug → entry. May be empty (`assets: {}`). |

Each entry under `assets`:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `version` | string | **yes** | A version constraint — see §3. |
| `package` | string | no | **Reserved.** Non-empty string if present. Inert in V1. |

No other keys are accepted anywhere in the file.

### Asset identity

The key is the asset's `slug` as it exists in the CMS. It is matched **exactly**:
case-sensitive, character-for-character, with no Unicode normalization, case folding, or
whitespace trimming. Arabic and other non-ASCII slugs work and are compared byte-for-byte.

> **A sharp edge worth knowing.** Because the comparison is byte-for-byte, a slug written in a
> different Unicode normalization form than the CMS stores (NFD rather than NFC, say) will not
> match, even though the two render identically on screen. Copy the slug from the CMS rather
> than retyping it. Deliberately normalizing on either side was rejected: it would make the
> identifier's meaning depend on which normalization library each implementation happened to
> use.

### An entry must be a mapping

```yaml
# Correct
quran-uthmani-hafs:
  version: "^2.1.0"

# Rejected — scalar shorthand is not supported
quran-uthmani-hafs: "^2.1.0"
```

There is one shape for an entry, so there is one thing to validate and one thing to extend
later.

### Strict parsing

The manifest and lockfile are both parsed under a strict YAML profile. These are **rejected**,
never coerced or silently accepted:

- UTF-8 with a byte-order mark, or any non-UTF-8 encoding
- more than one YAML document in the file (`---` separators)
- an empty or whitespace-only file
- duplicate mapping keys at any level
- YAML anchors (`&`), aliases (`*`) and merge keys (`<<`)
- custom or language-specific tags (`!custom`, `!!python/object`)
- wrong scalar types — a bool, float or list where an integer or string is required
- scalars resolved under any rules other than the **YAML 1.2 Core Schema**
- unknown fields, at the top level or inside an entry
- a sequence where a mapping or scalar is required
- any silent coercion, trimming, stringification, or normalization of a malformed value

The **single** permitted normalization anywhere in the format is two-component version
canonicalization (expanding `X.Y` to `X.Y.0` as defined in §3); no other trimming, case
folding, or coercion is allowed.

The YAML 1.2 requirement is not pedantry. Under YAML **1.1** — still the default in several
widely used parsers, including PyYAML — the unquoted scalars `on`, `no`, `y` and `off` resolve
to booleans, so an asset whose slug is `on` would be read as a mapping key of type bool by one
implementation and as the string `"on"` by another. Pinning 1.2 Core Schema means every
implementation agrees on what the file says before anyone argues about what it means.

Strictness here is deliberate. A manifest that "mostly parses" produces a build that mostly
works, and the failure shows up somewhere else entirely.

---

## 3. Version constraints

Versions follow [Semantic Versioning 2.0.0](https://semver.org/), with **one** adaptation for
text assets.

### Two numbers is enough

A book, a mushaf or a tafsir does not have "major, minor and patch" in the way software does.
So a version may be written with **two** components, and it is expanded to three by appending
a zero:

```
1.2   →  1.2.0          ^1.2  →  ^1.2.0          ~1.2  →  ~1.2.0
```

This expansion — call it *canonicalization* — happens once, when the string is read, before
any other rule applies. It applies to **both** sides: constraints you write in the manifest,
and version names published in the catalog. A version published as `1.2` **is** the version
`1.2.0`; they are not two different things.

Everything after that point is ordinary SemVer 2.0.0. Publishers who think in two numbers
simply never touch the third.

> **One consequence worth knowing.** Because `1.2` and `1.2.0` are the same version, an asset
> that somehow has two versions named `1.2` and `1.2.0` is ambiguous, and resolution fails
> with a duplicate-version error rather than guessing. See §4.

One-component versions (`2`, `^2`) are **not** accepted — two numbers is the floor as well as
the ceiling.

### Accepted forms

| You write | Read as | Matches |
|---|---|---|
| `1.2.3` | `1.2.3` | exactly `1.2.3` |
| `2.0` | `2.0.0` | exactly `2.0.0` |
| `1.2.3-beta.1` | `1.2.3-beta.1` | exactly `1.2.3-beta.1` (see §7) |
| `^1.2.3` | `^1.2.3` | `>=1.2.3 <2.0.0` |
| `^1.2` | `^1.2.0` | `>=1.2.0 <2.0.0` |
| `^0.2.3` | `^0.2.3` | `>=0.2.3 <0.3.0` |
| `^0.2` | `^0.2.0` | `>=0.2.0 <0.3.0` |
| `^0.0.1` | `^0.0.1` | `>=0.0.1 <0.0.2` |
| `^0.0.0` | `^0.0.0` | `>=0.0.0 <0.0.1` |
| `~1.2.3` | `~1.2.3` | `>=1.2.3 <1.3.0` |
| `~1.2` | `~1.2.0` | `>=1.2.0 <1.3.0` |
| `~0.2.3` | `~0.2.3` | `>=0.2.3 <0.3.0` |
| `~0.0.1` | `~0.0.1` | `>=0.0.1 <0.1.0` |

In short:

- **Exact pin** — one specific version, nothing else.
- **Caret `^`** — "anything that doesn't break me". It holds the leftmost non-zero component
  fixed, which is why `^0.2.3` stops at `0.3.0`: below `1.0.0`, the minor number is where
  breaking changes live.
- **Tilde `~`** — "corrections only". Major and minor stay fixed; only the last number moves.

### Rejected forms

| Rejected | Why |
|---|---|
| `2`, `^2`, `~2` | One component. Write `2.0` or `2.0.0`. |
| `1.2-beta.1` | A prerelease needs all three numbers: `1.2.0-beta.1`. |
| `>=1.0.0`, `<2.0.0` | Comparators are not in the V1 grammar. |
| `*`, `1.2.*` | Wildcards are not in the V1 grammar. |
| `>=1.0.0 <2.0.0` | Compound ranges. |
| `1.2.0 \|\| 1.3.0` | Alternatives. |
| `v1.2.3` | No `v` prefix. |
| `1.2.3+build1` | Build metadata is not allowed in a constraint. |
| `01.2.0` | No leading zeros. |

The grammar is small on purpose. Every form listed above has to mean *exactly* the same thing
to the registry, the CLI and the updater; a form we can add later costs nothing, while a form
we accepted and got wrong is permanent. Assets do not depend on other assets, so there is no
constraint intersection to express and nothing that compound ranges would buy.

Anything rejected produces an error naming the asset and the offending constraint. There is
no "best effort" fallback.

---

## 4. How a constraint resolves to a concrete version

### Which versions are eligible

A version of an asset can be selected **only if all three** hold:

1. it belongs to the requested slug;
2. its name, after canonicalization, is a valid SemVer 2.0.0 version **carrying no build
   metadata** — a version named `draft-2`, `v1.0` or `1.2.3+build1` is skipped, not repaired;
3. it has a `Distribution` record on the `PACKAGE` channel.

Two details about condition 2, since `AssetVersion.name` is a free-text field and anything can
end up in it:

- **Build metadata excludes a version entirely.** SemVer 2.0.0 permits `1.2.3+build1`, but
  ignores everything after the `+` when comparing precedence — so `1.2.3` and `1.2.3+build1`
  would be two selectable versions that are neither equal nor ordered relative to each other.
  Rather than invent a tie-breaker or a matching rule for it, V1 treats a `+` in a published
  version name the same way it treats `draft-2`: the version is not eligible. This mirrors §3,
  which rejects build metadata in constraints.
- **Two-component prereleases are skipped, not expanded.** Canonicalization adds a missing
  third component to plain versions only. A version published as `1.2-beta.1` is *not* read as
  `1.2.0-beta.1`; it is not a valid version name and is skipped. Prereleases need all three
  numbers on both sides — the same rule §3 applies to constraints.

The `PACKAGE` channel is the existing content-model concept for "this version is distributed
as a package". It is a **necessary** condition, not a promise: it does not mean the archive is
built, cached, authorized for you, or downloadable. Those checks belong to the registry (#417)
and artifact packaging (#425).

### Picking a winner

1. Parse and validate the manifest. Any error stops everything.
2. Build the eligible pool for the slug.
3. If two eligible versions canonicalize to the same version (e.g., records named `1.2` and
   `1.2.0`), **fail** with a duplicate version collision error. This is reachable because
   `AssetVersion.name` in the backend is an unvalidated `CharField` (see Appendix). There is
   deliberately no tie-breaker — not creation time, not database id, not row order, not
   response order, and not lexicographical sorting. Any of those would make your build depend
   on arbitrary storage or network ordering.

   This check covers the **whole eligible pool**, before the constraint narrows it. So two
   colliding records on `1.2` and `1.2.0` fail a build pinned to `~4.5.0`, which never comes
   near them. That is deliberate: a collision means the catalog contains an asset whose
   versions do not have unique identities, and resolving *around* it would mean handing out a
   lockfile whose reproducibility depends on the collision staying out of range. The fix is to
   repair the data once, not to route past it on every build.
4. Keep only versions matching the canonicalized constraint, applying the prerelease rule
   (§7).
5. If nothing is left, **fail** with an unsatisfiable-constraint error naming the asset slug,
   the requested constraint, and the available candidate versions.
6. Otherwise select the **single highest** version by SemVer 2.0.0 precedence. Build metadata
   is ignored in precedence comparisons per SemVer 2.0.0 §10. Never select by string or
   lexicographical comparison — `1.10.0` is newer than `1.9.0`, though it sorts earlier as text.

### All or nothing

Resolution is **atomic**. Either every declared asset resolves and a lockfile is written, or
one fails and **no lockfile is produced at all**. A partial lockfile is worse than none: it
looks valid, installs a subset, and the real failure surfaces later and somewhere else.

### Failure modes

| Error | When |
|---|---|
| Unsupported Schema Version | `schema_version` missing or not `1` |
| YAML Profile Violation | any strict-parsing rule in §2 |
| Scalar Shorthand Entry | an entry is a scalar instead of a mapping |
| Unknown Field | any key outside the tables in §2 |
| Missing Required Field | an entry has no `version` |
| Invalid Constraint Syntax | `version` is not in the §3 grammar |
| Invalid Reserved Field | `package` present but not a non-empty string |
| Unknown Asset | the slug matches no asset |
| No Eligible Package Versions | the asset exists but has no SemVer-valid `PACKAGE` version |
| Unsatisfiable Version Constraint | eligible versions exist, none match |
| Duplicate Version Collision | two eligible versions canonicalize to the same version |

Each is a distinct, named error identifying the asset slug involved, the requested constraint,
and observed candidate versions where applicable.

---

## 5. The lockfile: `itqan-assets.lock`

```yaml
lockfile_version: 1
manifest_schema_version: 1

assets:
  "mushaf-madinah":
    constraint: "~1.2"
    version: "1.2.4"
  "quran-uthmani-hafs":
    constraint: "^2.1.0"
    version: "2.4.1"
  "tajweed-rules":
    constraint: "^0.4.0"
    version: "0.4.7"
  "تفسير-الجلالين":
    constraint: "3.0"
    version: "3.0.0"
```

The entries are sorted, and not in the manifest's order — see [the bytes are
specified](#the-bytes-are-specified-not-just-the-fields) below. The Arabic slug sorts last
because its UTF-8 bytes are all above the ASCII range.

| Field | Type | Meaning |
|---|---|---|
| `lockfile_version` | integer | Format version of the lockfile itself. Must be `1`. |
| `manifest_schema_version` | integer | The manifest schema this lockfile was generated against. Must be `1`. |
| `assets` | mapping | Slug → entry. May be empty (`assets: {}`). |

Each entry has exactly two fields:

| Field | Type | Meaning |
|---|---|---|
| `constraint` | string | The manifest's `version` value copied **verbatim** — `~1.2` stays `~1.2`. |
| `version` | string | The resolved version, always in **canonical three-component** form — a version published as `3.0` is recorded as `3.0.0`. |

No other keys are accepted anywhere in the lockfile (the schema is closed).

Two things are deliberately absent. `package` never reaches the lockfile. And there is no
`checksum` or `integrity` field in V1 — artifact identity is owned by #425 and is not yet
defined; adding one later requires a `lockfile_version` bump.

The two version numbers are **decoupled** on purpose: the lockfile format can gain a field
without disturbing the manifest schema, and vice versa.

### The bytes are specified, not just the fields

The lockfile is generated by more than one program — the registry (#417) and the CLI (#422)
both write it, and the updater (#427) puts the result in a pull request for a human to read.
If those programs agree on the resolution but disagree on how to spell it, every PR carries
reformatting noise and the diff stops being reviewable, which is most of what the lockfile is
for. So the serialization is fixed:

| | |
|---|---|
| Encoding | UTF-8, no BOM |
| Line endings | `LF`, with exactly one newline at end of file |
| Indentation | 2 spaces, never tabs |
| Trailing whitespace | none |
| Top-level key order | `lockfile_version`, `manifest_schema_version`, `assets` |
| Asset order | ascending by the slug's UTF-8 **byte** sequence |
| Entry field order | `constraint`, then `version` |
| Collection style | block mappings; `{}` only for an empty `assets` |
| Blank lines | exactly one after `manifest_schema_version`; none between asset entries |
| Quoting | asset keys and all string values double-quoted; the four fixed schema keys plain |
| Comments | never emitted |

Two of those rows are load-bearing beyond tidiness. Asset ordering is by byte sequence, not by
any locale's collation — a locale-aware sort would order `تفسير-الجلالين` differently on
different machines. And asset keys are **always** quoted because `SlugField` permits slugs such
as `true` or `123`, which as bare YAML keys resolve to a bool and an integer even under 1.2
Core; a writer that quoted only "when necessary" would have to reimplement that judgement
identically everywhere, and getting it wrong emits a lockfile that fails its own validation.
Quoting unconditionally removes the judgement call.

Nothing that varies between runs, machines or users belongs in the file: no `generated_at`, no
tool version, no hostname, no absolute paths. A timestamp alone would mean every `install`
produces a diff even when no dependency moved, which is precisely the noise this section
exists to prevent.

The practical test: resolving the same manifest against the same catalog twice, with two
different implementations, must produce byte-identical files.

### Lockfile states

Any tool inspecting the pair reports exactly one of five states, evaluated in this order:

| Order | State | Meaning |
|---|---|---|
| 1 | `ORPHAN` | Lockfile present, manifest absent. |
| 2 | `MISSING` | Manifest present, lockfile absent — resolution has never run. |
| 3 | `INVALID` | Malformed YAML, a strict-profile violation, an unsupported `lockfile_version` or `manifest_schema_version`, a missing/extra/wrong-typed field, or a `version` that is not valid SemVer. |
| 4 | `STALE` | Structurally fine, but no longer matches the manifest. |
| 5 | `FRESH` | Structurally fine and fully matching. |

The order matters. **An unsupported version is `INVALID`, never `STALE`** — a lockfile written
by a newer version of the tooling is not "out of date", it is unreadable, and guessing at it
is worse than refusing it.

A lockfile becomes `STALE` when:

| Sub-state | Condition |
|---|---|
| Schema Version Mismatch | `manifest_schema_version` ≠ the manifest's `schema_version` |
| Asset Key-Set Mismatch | an asset was added to or removed from the manifest |
| Constraint Mismatch | some `constraint` no longer matches the manifest's `version` **text** |
| Constraint Not Satisfied | a locked `version` no longer satisfies its recorded constraint, or violates prerelease isolation |

### What does and does not make a lockfile stale

Freshness **ignores**: comments, whitespace and indentation, quote style, key ordering, and
the presence, absence, or value of the reserved `package` field. Reformatting your manifest or
adding/removing `package` does not invalidate your lockfile.

Freshness **does** compare each `version` constraint as literal text. This is the only string
compared literally, and it has one visible consequence:

> Rewriting `version: "~1.2"` as the equivalent `version: "~1.2.0"` makes the lockfile
> `STALE`, even though the two mean exactly the same range.

That is an accepted trade. Comparing decoded ranges instead would require specifying a
canonical form for ranges and proving that every implementation decodes identically — a lot
of specification to make a cosmetic edit non-staling. And being `STALE` is cheap: it triggers
a re-resolve that produces the identical `version`. Nothing breaks; the file is rewritten.

(Hashing the whole manifest was rejected for the opposite reason: a new comment would stale
the lockfile and generate noisy update PRs.)

### What `FRESH` authorizes

A `FRESH` lockfile means installation tooling **must skip** version resolution entirely and
use the exact locked versions.

It does **not** mean the artifacts exist, are built, are authorized for you, or can be
downloaded. `FRESH` is a statement about your *dependency declaration*, not about the
*artifacts*. Availability, authorization and integrity stay with #417, #422 and #425.

### When a locked version is no longer there

A `FRESH` lockfile names an exact version. If that version has since stopped being eligible —
the `PACKAGE` distribution was removed, the record was deleted, the name was edited into
something that is no longer valid SemVer — installation **fails, naming the asset and the
missing version**.

It does not quietly install the next patch, the previous patch, or the highest version still
matching the constraint. Any of those would mean the lockfile silently stopped describing what
you get, which makes it worse than not having one: a lockfile that lies is discovered in
production, and one that fails is discovered in CI. Recovering is a deliberate act — broaden or
change the constraint in the manifest and re-resolve.

### Published versions do not change underneath you

Everything above rests on one assumption, so it is stated as a rule: once a version of an asset
is distributed on the `PACKAGE` channel, the pair `(slug, version)` is **immutable** — it keeps
identifying the same content forever.

A correction to a published version ships as a **new** version. Replacing the content behind
`2.4.1` would mean two developers, both holding a `FRESH` lockfile pinning `2.4.1`, end up with
different bytes — and neither has any way to notice. Version numbers are how the lockfile
identifies content; if they are reused, it identifies nothing.

This is a publishing-workflow rule rather than something the resolver can check, and nothing in
the backend enforces it today. Enforcing it belongs with artifact identity in #425.

---

## 6. Worked resolution walkthrough

### The catalog

Versions available in the CMS for four assets. `PACKAGE` marks whether a `PACKAGE`
distribution exists:

| Asset slug | Version name | `PACKAGE`? |
|---|---|---|
| `quran-uthmani-hafs` | `2.0.0` | yes |
| `quran-uthmani-hafs` | `2.1.0` | yes |
| `quran-uthmani-hafs` | `2.4.1` | yes |
| `quran-uthmani-hafs` | `2.5.0-rc.1` | yes |
| `quran-uthmani-hafs` | `3.0.0` | **no** |
| `mushaf-madinah` | `1.1.0` | yes |
| `mushaf-madinah` | `1.2.0` | yes |
| `mushaf-madinah` | `1.2.4` | yes |
| `mushaf-madinah` | `1.3.0` | yes |
| `تفسير-الجلالين` | `2.9` | yes |
| `تفسير-الجلالين` | `3.0` | yes |
| `tajweed-rules` | `0.4.0` | yes |
| `tajweed-rules` | `0.4.7` | yes |
| `tajweed-rules` | `0.5.0` | yes |
| `tajweed-rules` | `draft-2` | yes |

### The manifest

The example from §2.

### Entry 1 — `quran-uthmani-hafs: "^2.1.0"`

Constraint is already three-component: `^2.1.0` → `>=2.1.0 <3.0.0`.

| Candidate | Verdict |
|---|---|
| `2.0.0` | eligible, but below `2.1.0` |
| `2.1.0` | **matches** |
| `2.4.1` | **matches** |
| `2.5.0-rc.1` | eligible, in range numerically, but excluded — a stable range never selects a prerelease (§7) |
| `3.0.0` | **not eligible**: no `PACKAGE` distribution. (Even if it were, `<3.0.0` excludes it.) |

Matching: `2.1.0`, `2.4.1`. Highest precedence → **`2.4.1`**.

### Entry 2 — `mushaf-madinah: "~1.2"`

Canonicalize: `~1.2` → `~1.2.0` → `>=1.2.0 <1.3.0`.

| Candidate | Verdict |
|---|---|
| `1.1.0` | below range |
| `1.2.0` | **matches** |
| `1.2.4` | **matches** |
| `1.3.0` | at the upper bound, excluded — tilde holds the minor fixed |

Highest matching → **`1.2.4`**.

Note `1.3.0` exists and is newer. That is not an error; it is an *out-of-range update*, and
§7 explains what happens next.

### Entry 3 — `تفسير-الجلالين: "3.0"`

Both sides canonicalize. The constraint `3.0` → `3.0.0`, an exact pin. The published version
name `3.0` → `3.0.0` as well.

| Candidate | Canonical | Verdict |
|---|---|---|
| `2.9` | `2.9.0` | not the pinned version |
| `3.0` | `3.0.0` | **matches the pin exactly** |

Selected → **`3.0.0`**. The Unicode slug matched exactly, with no normalization.

The lockfile records `constraint: "3.0"` (what was written) and `version: "3.0.0"` (canonical).

### Entry 4 — `tajweed-rules: "^0.4.0"`

`^0.4.0` → `>=0.4.0 <0.5.0`. Zero-major caret holds the *minor* fixed, because below `1.0.0`
that is where breaking changes live.

| Candidate | Verdict |
|---|---|
| `draft-2` | **not eligible**: not a valid version name, skipped |
| `0.4.0` | **matches** |
| `0.4.7` | **matches** |
| `0.5.0` | excluded — `^0.4.0` stops at `0.5.0` |

Highest matching → **`0.4.7`**.

The entry also carries `package: "itqan/tajweed-rules"`. It was validated as a non-empty
string and then ignored: it did not affect eligibility, selection, or the lockfile.

### Result

All four resolved, so the lockfile in §5 is written. Had any one failed, none of it would
have been.

### The failure case

Add a fifth entry to the same manifest:

```yaml
  hadith-core:
    version: "^3.0.0"
```

with only `2.5.0` available on the `PACKAGE` channel:

```
error: unsatisfiable version constraint
  asset:      hadith-core
  constraint: ^3.0.0  (>=3.0.0 <4.0.0)
  available:  2.5.0
  no eligible PACKAGE version satisfies this constraint
```

The other four assets resolved perfectly — and it does not matter. **No lockfile is written,
and any existing lockfile is left untouched.** Fix the constraint, or publish the version, and
re-run.

---

## 7. Prereleases and "update available", in plain language

### What a prerelease is

Sometimes a version is published before it is really finished — a draft for review, a beta for
early testers. SemVer 2.0.0 marks these with an alphanumeric suffix separated by a hyphen:

```
1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-beta < 1.0.0-rc.1 < 1.0.0
```

Everything with a hyphen has lower precedence than the plain release version without a suffix.
Prereleases are "on the way to" the stable release without being it.

### Why ranges never pick one up

If you write `^2.0.0`, you are saying "any 2.x is fine". You mean any *finished* 2.x. You did
not ask to be handed a draft that happens to be numerically in range.

So the rule is: **`^` and `~` never select a prerelease version, ever.** Neither does an exact
stable pin — `2.0.0` matches `2.0.0` and not `2.0.0-beta.1`. There is no flag to turn this on.

If you genuinely want a draft, you name it exactly with a three-component core:

```yaml
app-theme:
  version: "2.0.0-beta.1"    # this exact draft, nothing else
```

If your publishers never publish drafts, this rule simply never comes up. It costs nothing,
and it prevents a draft reaching production on the day someone does publish one.

### What "update available" means

You have two pieces of information: the constraint you *declared* in `itqan-assets.yaml`, and
the version you currently have *locked* in `itqan-assets.lock`. When new versions appear in
the catalog, automated tooling (such as `itqan outdated` or the updater in #427) classifies
the state into one of three discrete categories:

1. **Up to date**: No visible candidate version has higher SemVer precedence than the
   currently locked version.
2. **In-Range Update**: An eligible candidate version exists with higher SemVer precedence
   than the currently locked version, and it **satisfies** the existing manifest constraint.
   This can be applied automatically by regenerating `itqan-assets.lock` alone, leaving
   `itqan-assets.yaml` untouched.
3. **Out-of-Range Update**: An eligible candidate version exists with higher SemVer
   precedence than the currently locked version, but it **does not satisfy** the existing
   manifest constraint. Applying this update requires a human decision to edit
   `itqan-assets.yaml` and broaden or bump the constraint.

### Which versions are even visible to an update check

"Candidate version" above means a version that is eligible per §4 **and** visible under the
prerelease rule, which mirrors resolution:

- **A stable declaration** — an exact stable pin, `^`, or `~` — never sees prereleases. A
  project on `^1.0.0` is not told about `1.5.0-alpha.1`, ever.
- **An exact prerelease pin** sees prereleases sharing its own `X.Y.Z` release core, and all
  stable versions.

So a project pinned to `1.3.0-beta.1` is shown `1.3.0-beta.2` and `1.3.0-rc.1` (its own draft
series progressing), `1.3.0` (the release it is waiting for), and `1.4.0` — but **not**
`2.0.0-alpha.1`. Asking for one specific draft is not a standing subscription to every future
draft series; opting into the beta of the release you are tracking says nothing about wanting
alphas of the next major. Suggesting a jump across prerelease series is a policy #427 may
choose to add on top of this; it is not something V1 does by default.

Note that every update to an exact pin — prerelease or stable — is out-of-range by
construction, since an exact pin matches exactly one version. Visibility decides what gets
*reported*, not what gets applied automatically.

### The update baseline has to be trustworthy

Both classifications compare against "the currently locked version", which presumes there is
one. **Update classification requires a `FRESH` lockfile.** In the other four states there is no
authoritative answer to "what am I on right now":

| State | Why there is no baseline |
|---|---|
| `MISSING` | Resolution has never run; nothing is locked. |
| `STALE` | The locked versions answer a question the manifest no longer asks. |
| `INVALID` | The file cannot be read as a lockfile at all. |
| `ORPHAN` | There is no manifest, so there is no declared intent to compare against. |

Reporting an update from a `STALE` lockfile means computing a diff against a version the
project may already have moved off. What tooling should *do* about a repository in one of these
states — skip it, open a PR that regenerates the lockfile, or report a configuration problem —
is #427's call. What it must not do is treat a non-`FRESH` lockfile as the current state.

### Access does not change the answer

Whether a caller is entitled to a given asset is enforced by the registry (#417) and is
deliberately **not** part of version selection. If resolution selects `2.4.1` and the caller has
no access to it, the request fails; the registry does not filter out the versions you cannot
reach and hand back the highest one you can.

Otherwise the same manifest would resolve differently for different people, and a lockfile
would record which developer's credentials happened to generate it. Access controls what you
may fetch, never which version the constraint means.

### Worked update examples

| Case | Declared manifest `version` | Locked `version` | New catalog version | Classification & Action |
|---|---|---|---|---|
| **Caret in-range** | `^1.2.0` (`>=1.2.0 <2.0.0`) | `1.2.3` | `1.3.0` | **In-Range Update to `1.3.0`**<br>Regenerate `itqan-assets.lock` only; `itqan-assets.yaml` is untouched. |
| **Tilde out-of-range** | `~1.2.0` (`>=1.2.0 <1.3.0`) | `1.2.5` | `1.3.0` | **Out-of-Range Update to `1.3.0`**<br>Requires editing `itqan-assets.yaml` (e.g. to `~1.3.0` or `^1.2.0`) and updating the lockfile. |
| **Exact pin out-of-range** | `1.2.3` (exact `1.2.3`) | `1.2.3` | `1.2.4` | **Out-of-Range Update to `1.2.4`**<br>Exact pins are always out-of-range for newer versions; requires editing `itqan-assets.yaml` to pin `1.2.4`. |
| **Prerelease ignored** | `^1.0.0` (`>=1.0.0 <2.0.0`) | `1.4.0` | `2.0.0-beta.1`, `1.5.0-alpha.1` | **Up to date (No update reported)**<br>Prereleases are excluded by range constraints; no update action is taken. |

This split is exactly what the updater (#427) acts on. An in-range update is a small,
low-risk PR that touches one line of the lockfile. An out-of-range update is a PR that changes
your declared intent, and deserves a real look.

---

## 8. What this specification does not cover

This document defines two file formats and the rules for turning one into the other. It
deliberately says nothing about:

| Concern | Owner |
|---|---|
| Registry HTTP API — endpoints, auth, payload shapes | [#417](https://github.com/Itqan-community/cms-backend/issues/417) |
| `itqan install` — CLI behavior, unpacking, writing files to disk | [#422](https://github.com/Itqan-community/cms-backend/issues/422) |
| Archive packaging, checksums, artifact identity | [#425](https://github.com/Itqan-community/cms-backend/issues/425) |
| GitHub App discovery of repositories | [#426](https://github.com/Itqan-community/cms-backend/issues/426) |
| Opening and refreshing update PRs | [#427](https://github.com/Itqan-community/cms-backend/issues/427) |

It also ships no code. There is no resolver, no validator, no model change and no migration in
this specification — those are consumers of the contract, not part of it.

---

## 9. Future: publisher-chosen package names

V1 identifies an asset by its `slug`. This works today, and it has a known expiry date.

`Asset.slug` is **generated by the CMS**, derived from the asset's name with a numeric suffix
on collision. The publisher does not choose it. A real package ecosystem needs the publisher
to own their package's name.

### A published slug is frozen

Until that day, one rule keeps the identifier usable: **once an asset has been distributed on
the `PACKAGE` channel, its slug must not change.**

The slug is generated only when it is empty (`Asset.save()`), so renaming an asset does not
regenerate it — but nothing stops the field being edited directly. Doing so is invisible from
the CMS and total from outside it: every manifest naming the old slug starts failing with
Unknown Asset, with nothing to indicate the asset still exists under a new name. Renaming a
published asset needs an alias or redirect mechanism, which is a separate piece of work; it is
not something to do by editing the field.

There is no publisher-owned name field on `Asset` today, so V1 cannot use one. What V1 does
instead is reserve the key:

```yaml
tajweed-rules:
  version: "^0.4.0"
  package: "itqan/tajweed-rules"    # accepted, validated, ignored
```

`package` is validated as a non-empty string and has **no** effect on anything — not
eligibility, not selection, not the lockfile, not freshness. Adding, changing or removing it
never makes a lockfile stale.

The migration, when it happens:

1. The backend gains a publisher-owned, immutable, unique package-name field on `Asset` — a
   separate piece of work, not part of this specification.
2. Manifests key entries by that name under `schema_version: 2`, with `package` serving as the
   bridge for manifests written before the change.
3. Until then, `slug` remains the sole resolution identifier.

Reserving the key now costs one validation rule and means the manifest grammar does not have
to break when that day comes.

Extending the constraint grammar, adding manifest fields, or supporting several manifests in a
monorepo would likewise each require a `schema_version` increment.

---

## Appendix: current backend behavior

Verified against `apps/content/models.py`. **This specification changes none of it.**

| Concept here | Backend today |
|---|---|
| Asset identity | `Asset.slug` — `SlugField(allow_unicode=True, unique=True, db_index=True)`, auto-generated in `Asset.save()` from the asset's names, with a numeric suffix on collision. |
| Version string | `AssetVersion.name` — `CharField(max_length=255)`. |
| Package eligibility | `Distribution.channel`, which includes `PACKAGE`; `unique_together = [["asset_version", "channel"]]`, so a version has at most one `PACKAGE` record. |
| Publisher-chosen name | Does not exist. |

**One correction worth stating plainly.** Issue #416 describes `AssetVersion` as already using
SemVer. It does not: `AssetVersion.name` is an unvalidated `CharField` with no SemVer
validator, no normalization and no uniqueness constraint. Nothing currently prevents a version
named `draft-2`, or two versions of one asset named `1.2` and `1.2.0`.

That is why this specification treats SemVer conformance as a **filter the resolver applies**
rather than a guarantee the database provides — non-conforming names are skipped (§4), and
two names that mean the same version are a hard error rather than a coin flip.

Adding a SemVer validator and a canonical-uniqueness constraint to `AssetVersion.name` would
make that error unreachable. It is a sensible follow-up and a separate issue; #416 ships
documentation only.
