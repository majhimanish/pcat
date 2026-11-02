# Pattern Catalog (`pcat`)

An organization-specific catalog of **verified Python code patterns**.

Code written by people or AI agents drifts: every prompt produces a slightly
different binary search, retry loop or slugifier. Instead, common code shapes
are written once, reviewed by engineers, and stored here. Each pattern is a
self-contained function with metadata and tests, plus a **fingerprint** of its
canonical form, so tools can tell when a piece of code *is* a catalog pattern
no matter how its variables are named or commented.

v1 (this repository) is the catalog and its review workflow: the file format,
the canonicalizer, the `pcat` CLI, validation and CI. Mining, an MCP server
and a linter are planned next (see [Planned extensions](#planned-extensions)).

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate     # Python 3.11+
pip install -e .[dev]
pytest                  # tests for the tool (also validates the seed catalog)
pcat validate           # all catalog checks, including every pattern's tests
pcat show search.binary_search.iterative
```

## Concepts

| Term | Meaning |
|---|---|
| Pattern | One verified function (plus helpers it calls) with `pattern.yaml`, `impl.py`, `test_impl.py`. |
| Variant | A separate pattern per behavior-relevant difference, e.g. `search.binary_search.iterative` vs `.recursive`. Variants share `variant_of` and must differ in `behavior`. |
| Canonical form | `impl.py` with docstrings, comments, formatting and local names removed: functions become `f0, f1, …` (entry point is `f0`), constants `c0, c1, …`, parameters/locals `v0, v1, …` per function. Imports are sorted. |
| Fingerprint | SHA-256 of the canonical form. Same code with different names/comments ⇒ same fingerprint. |
| Name map | Placeholder → real name (`{"f0": "binary_search", "v0": "items", "f1.v0": …, "c0": …}`). Canonical form + name map renders readable code. |

Try it: `pcat canonical some_file.py --entry my_function`.

### Canonicalization rules (version 2)

`canonical.CANONICAL_VERSION` (recorded in `index.json`) names the rule set.

- Output: sorted, one-name-per-line imports; then literal constants in source
  order; then the entry point `f0`; then helpers in source order.
- Renamed: top-level functions (`fN`), literal constants (`cN`), and each
  function's parameters and locals (`vM`, restarting per function).
- Never renamed: builtins and other free names, imported names, attribute
  names, `self`/`cls`, dunder names, and keyword-argument names at call sites —
  **except at calls to functions defined in the pattern**, where keywords
  follow the callee's parameter placeholders (`f1(v0, v2=True)`), so canonical
  text is runnable and custom renders keep calls working. A keyword that matches
  no named parameter (it goes into `**kwargs`) is left alone.
- Allowed at top level: imports, functions (incl. async), and literal
  constants `NAME = <literal>` / `NAME: T = <literal>` (anything
  `ast.literal_eval` accepts). Everything else is rejected with a clear error.

## Layout

```
catalog/index.json                       generated; the interface for future tools
catalog/<category>/<pattern_id>/         version 1
catalog/<category>/<pattern_id>@v2/      version 2, and so on
    pattern.yaml  impl.py  test_impl.py
```

`<pattern_id>` is the id without its category: `search.binary_search.iterative`
lives in `catalog/search/binary_search.iterative/`.

## Adding a pattern

**From scratch**

```bash
pcat new text.truncate.word_boundary     # scaffolds the folder with templates
# edit impl.py, test_impl.py and pattern.yaml (summary, behavior, owner)
pcat fingerprint text.truncate.word_boundary --write
pcat index
pcat validate text.truncate.word_boundary
```

**From existing code** — copies the function, every top-level helper it calls
(transitively) and the imports they use; comments are kept:

```bash
pcat add path/to/module.py --function top_words --id text.top_words.counter
# write real tests in test_impl.py, fill in behavior, then:
pcat index && pcat validate text.top_words.counter
```

`pcat add` also copies every literal constant those functions use. If a used
module-level name is anything else (e.g. `PATTERN = re.compile(...)`), it fails
and names it; move that value into the function or make it a literal.

The templates deliberately fail validation (failing test, `TODO` fields) until
you finish them. Rules for `impl.py`: only imports, functions and literal
constants at top level (no classes); the entry point is named in `entry_point`.

Other commands:

| Command | Purpose |
|---|---|
| `pcat canonical <file.py> [--entry NAME] [--no-annotations]` | print canonical form |
| `pcat fingerprint <id> [--write]` | print / store fingerprint |
| `pcat validate [<id>…] [--skip-tests] [--base REF]` | run all checks |
| `pcat index` | regenerate `catalog/index.json` |
| `pcat show <id>` | metadata + rendered code |
| `pcat render <id> --names f0=find_user v0=users` | render with your own names |
| `pcat find <file.py>` | which pattern (if any) each top-level function in a file is |
| `pcat migrate-fingerprints` | recompute all fingerprints after a rules change (see below) |

A bare `<id>` means its highest version; use `<id>@v<N>` for a specific one.

## Review workflow

- **One pattern per pull request.** CI (`.github/workflows/validate.yml`) runs
  `pytest tests/`, `pcat validate`, and on PRs `pcat validate --base
  origin/<base>` which fails if any already-approved version changed.
- **CODEOWNERS** requires review from the owning team for `catalog/`.
- **Merged to `main` = approved.** There is no separate approval state.
  Protect `main` (require PRs, passing `validate`, and code-owner review).

To change the reviewers, edit `CODEOWNERS`: replace the placeholder
`@platform-team` with a real team such as `@your-org/platform-engineering`
(GitHub ignores owners that do not exist). You can add narrower lines per
category, e.g. `/catalog/retry/ @your-org/sre`.

### Other CI systems

The workflow is four shell commands after checkout with full history:

```bash
pip install -e .[dev]
pytest tests/
pcat validate
pcat validate --skip-tests --base origin/main     # pull requests only
```

Port them to GitLab CI, Jenkins, Buildkite, etc. as-is. Use Python 3.11 in CI
(see `KNOWN_GAPS.md` on Python versions).

## Versioning

Approved patterns are **immutable**. Editing `impl.py` of an existing version
changes its fingerprint and fails check 4, and in CI the `--base` check fails on
*any* byte change to an approved `impl.py` (even a comment). To change code or
behavior:

1. Copy `catalog/<category>/<pattern_id>/` to `<pattern_id>@v2/` and set
   `version: 2`; make the change; `pcat fingerprint <id>@v2 --write`.
2. In the old version set `status: deprecated` and `replaced_by: <id>` (or
   `<id>@v2`). Only `status` and `replaced_by` may change on an approved version.
3. `pcat index`, `pcat validate`, open a PR.

Comment-only or docstring-only edits do not change fingerprints (they pass
check 4), but they are still rejected by `--base` for approved versions.

### Changing the canonicalization rules

A rule change can alter fingerprints of untouched patterns, so it is explicit:

1. Change `src/pcat/canonical.py` and bump `CANONICAL_VERSION`.
2. Run `pcat migrate-fingerprints`: it recomputes every fingerprint, rewrites
   the changed `pattern.yaml` lines, regenerates `index.json` and prints an
   `id / old / new` table for the PR description.
3. In CI, `--base` accepts the changed fingerprints only because
   `CANONICAL_VERSION` went up and every approved `impl.py` is byte-identical.

## Validation checks

`pcat validate` reports one line per problem, tagged with its check number:

1. `pattern.yaml` matches the schema (unknown keys are errors); `id`/`version` match the folder
2. `impl.py` parses and contains only imports, functions and literal constants at top level
3. `entry_point` exists in `impl.py`
4. stored `fingerprint` equals the computed fingerprint
5. no two active patterns share a fingerprint
6. no two active variants of one family have identical `behavior`
7. deprecated patterns have a `replaced_by` that resolves to another pattern
8. `test_impl.py` exists and passes (each pattern in its own pytest process)
9. idempotence: `canonicalize(render(canonical, name_map)) == canonical`
10. `catalog/index.json` is up to date

Plus `immutable` problems when `--base` is given.

## Planned extensions

All future tools read **only `catalog/index.json`**: `{"canonical_version": N,
"patterns": [...]}`, where each entry has `id, version, title, category,
variant_of, behavior, status, fingerprint, path` (sorted by id and version). A
tool that fingerprints code must use the same rules version. The catalog's
internals can change without breaking these tools.

- **Miner** (`docs/specs/v2-miner.md`, planned): scan repositories, canonicalize
  every function, cluster identical or near-identical fingerprints, and propose
  the most common shapes as candidate patterns (via `pcat add`).
- **MCP server** (`v3-mcp.md`, planned): serve the catalog to coding agents —
  search by summary/behavior, fetch rendered code with the caller's names
  (`render`), so agents reuse approved code instead of improvising.
- **Linter** (`v4-linter.md`, planned): in application CI, fingerprint new
  functions (`pcat find` is the seed of this), flag reimplementations of
  catalog patterns, uses of deprecated versions, and near-misses.

## Further reading

- `CLAUDE.md` — handoff and invariants for future sessions
- `DECISIONS.md` — every assumption made while building v1
- `KNOWN_GAPS.md` — limitations and suggested fixes
- `docs/specs/` — phase specs (`v1-catalog.md` is the spec for this build)
