# Pattern Catalog — Build Spec (v1)

You are building this project from scratch, unattended. Do not stop to ask questions. When something is ambiguous, pick the simplest reasonable option, record it in `DECISIONS.md`, and continue. You are done when every item under **Acceptance criteria** passes.

## 1. Goal

An organization wants its code (written by humans or AI agents) to be predictable. Instead of each prompt producing a new variation, common code shapes are written once, verified by engineers, and stored in a **catalog**. Later tools (out of scope here) will mine repos for candidates, serve the catalog to coding agents over MCP, and lint new code against it.

v1 builds only the **catalog and its review workflow**: the storage format, a Python canonicalizer, a CLI, validation, and CI so that a merged pull request = an approved pattern.

## 2. Scope

**In scope**
- Catalog format stored as plain files in a git repo
- Canonicalization and fingerprinting of Python code
- CLI `pcat` to scaffold, import, validate, index, show and render patterns
- CI workflow that validates every pull request touching the catalog
- 6 seed patterns proving the system works end to end

**Out of scope (design so these can be added later, but do not build)**
- Mining repos for candidate patterns
- MCP server
- CI linter that checks application code against the catalog
- Any language other than Python
- Any web UI

## 3. Tech stack

- Python 3.11+
- Standard library `ast` for parsing and code generation (`ast.unparse`)
- `typer` for the CLI, `pyyaml` for metadata, `pydantic` v2 for schema validation, `pytest` for tests
- Packaged with `pyproject.toml`; installable with `pip install -e .`; console script `pcat`
- No network access needed at runtime

## 4. Core concepts

- **Pattern**: one verified, self-contained Python function (plus any helper functions it needs), with metadata and tests.
- **Variant**: a separate pattern for each behavior-relevant difference. Example: `binary_search.iterative`, `binary_search.recursive`. Variants are explicit entries, not runtime switches.
- **Canonical form**: the pattern's code after normalization (section 6). Comments, docstrings, formatting and local names do not survive.
- **Fingerprint**: SHA-256 of the canonical form. Two snippets that differ only in names, comments or formatting have the same fingerprint.
- **Name map**: the mapping from canonical placeholders (`f0`, `v0`, `v1` …) to real names. Rendering = canonical form + name map → readable code.

Determinism is the core promise: the same input always produces byte-identical output on any machine.

## 5. Repository layout

```
pattern-catalog/
├── pyproject.toml
├── README.md
├── CLAUDE.md             # handoff for future Claude Code sessions (section 15)
├── DECISIONS.md
├── KNOWN_GAPS.md
├── docs/specs/v1-catalog.md   # copy of this spec
├── CODEOWNERS
├── .github/workflows/validate.yml
├── src/pcat/
│   ├── __init__.py
│   ├── cli.py            # typer app
│   ├── canonical.py      # normalization + fingerprint + render
│   ├── schema.py         # pydantic models for pattern.yaml
│   ├── catalog.py        # load, validate, index
│   └── errors.py
├── catalog/
│   ├── index.json        # generated, committed
│   └── <category>/<pattern_id>/
│       ├── pattern.yaml
│       ├── impl.py
│       └── test_impl.py
└── tests/                # tests for the tool itself
```

## 6. Canonicalization rules (`canonical.py`)

Input: Python source containing one top-level function (the entry point) and optionally top-level helper functions. Reject anything else at top level except imports.

Steps, in order:
1. Parse with `ast.parse`. Reject on syntax error.
2. Remove docstrings (first-statement string constants in modules and functions). Comments vanish automatically.
3. Sort and deduplicate top-level imports; keep them.
4. Rename, in order of first appearance during a deterministic depth-first walk:
   - Top-level function names → `f0`, `f1`, … (entry point is always `f0`; helpers follow in source order)
   - Parameters and local variables (including loop targets, comprehension variables, `except … as` names) → `v0`, `v1`, … scoped per function, numbering restarting at `v0` in each function
5. **Never rename**: builtins, imported names, attribute names (`x.append`), keyword argument names at call sites, `self`/`cls`, dunder names, and global names not defined in the snippet.
6. Strip type annotations only if `pattern.yaml` sets `keep_annotations: false` (default `true`).
7. Produce canonical text with `ast.unparse` on the normalized tree, then ensure a single trailing newline.
8. Fingerprint = `sha256(canonical_text.encode("utf-8")).hexdigest()`.

Also provide:
- `extract_name_map(source) -> dict[str, str]` returning `{"f0": "binary_search", "v0": "items", …}`
- `render(canonical_text, name_map) -> str` replacing placeholders by walking the AST (not string replacement) and unparsing
- Guarantee: `canonicalize(render(c, m)) == c` for every catalog entry (idempotence)

## 7. Pattern metadata (`pattern.yaml`)

```yaml
id: search.binary_search.iterative     # dotted, lowercase, unique, matches folder path
version: 1                             # integer; bump = new folder suffix, see section 9
title: Binary search (iterative)
summary: Return index of target in a sorted list, or -1 if absent.
category: search
variant_of: search.binary_search       # optional family id
behavior:                              # behavior-relevant facts; variants must differ here
  style: iterative
  on_missing: -1
  duplicates: any_index
  midpoint: overflow_safe
entry_point: binary_search             # real function name in impl.py
owner: "@platform-team"
status: active                         # active | deprecated
replaced_by: null                      # id, required when deprecated
keep_annotations: true
fingerprint: <sha256>                  # written by `pcat fingerprint --write`
```

Validate with pydantic. Unknown keys are an error.

## 8. CLI (`pcat`)

All commands exit non-zero on failure and print one clear error per problem.

| Command | Behavior |
|---|---|
| `pcat new <id>` | Scaffold folder with template `pattern.yaml`, `impl.py`, `test_impl.py` |
| `pcat add <file.py> --function <name> --id <id>` | Import a function (and helpers it calls) from existing code into a new pattern folder |
| `pcat canonical <file.py>` | Print canonical form |
| `pcat fingerprint <id> [--write]` | Print fingerprint; `--write` stores it in `pattern.yaml` |
| `pcat validate [<id>…]` | Run all checks in section 10; default all patterns |
| `pcat index` | Regenerate `catalog/index.json` |
| `pcat show <id>` | Print metadata and rendered code |
| `pcat render <id> --names key=value …` | Render with a custom name map, e.g. `--names f0=find_user v0=users` |
| `pcat find <file.py>` | Report which catalog pattern (if any) has the same fingerprint as each top-level function in the file |

`index.json` is a sorted list of `{id, version, title, category, variant_of, behavior, status, fingerprint, path}`, written with `sort_keys=True, indent=2` so diffs are stable. Future MCP and linter tools will read only this file.

## 9. Review workflow and versioning

- One pattern per pull request is the norm; CI enforces validation, CODEOWNERS enforces review.
- Merged to `main` = approved. There is no separate approval state.
- Approved patterns are **immutable**. To change behavior or code, create `<id>` at `version: N+1` in folder `<pattern_id>@v<N+1>`, and mark the old one `deprecated` with `replaced_by`.
- Editing `impl.py` of an existing version must fail validation (fingerprint mismatch).
- `CODEOWNERS`: `/catalog/ @platform-team` as a placeholder; note in README how to change it.

## 10. Validation checks (`pcat validate`)

1. `pattern.yaml` matches schema; `id` matches folder path
2. `impl.py` parses and passes canonicalization rules (only functions + imports at top level)
3. `entry_point` exists in `impl.py`
4. Stored `fingerprint` equals computed fingerprint
5. No two active patterns share a fingerprint (report both ids)
6. No two variants in the same family have identical `behavior` maps
7. `deprecated` patterns have a valid `replaced_by`
8. `test_impl.py` exists and passes under pytest (run per pattern, isolated)
9. Idempotence: `canonicalize(render(canonical, name_map)) == canonical`
10. `index.json` is up to date (regenerate in memory and compare)

## 11. CI (`.github/workflows/validate.yml`)

On pull requests and pushes to `main`: set up Python 3.11, `pip install -e .[dev]`, run `pytest tests/`, then `pcat validate`. Assume GitHub; keep the steps simple enough to port to other CI systems, and note this in README.

## 12. Seed patterns

Write these, each with real tests (normal cases, edge cases, empty input):

1. `search.binary_search.iterative`
2. `search.binary_search.recursive`
3. `sort.merge_sort.recursive`
4. `collections.group_by.dict_of_lists`
5. `retry.with_exponential_backoff` (injectable `sleep` function so tests run instantly)
6. `text.slugify.ascii`

## 13. Tests for the tool (`tests/`)

At minimum:
- Two snippets differing only in names, comments, docstrings and formatting → same fingerprint
- Changing a builtin, attribute name or literal → different fingerprint
- Name scoping restarts per function; helpers get `f1`, `f2` in source order
- `render` round-trips for every seed pattern
- Each validation check in section 10 has a test that triggers its failure
- `pcat add` extracts a function plus the helpers it calls from a multi-function file
- Running `pcat index` twice produces byte-identical output

## 14. Acceptance criteria

- `pip install -e .[dev]` works in a fresh virtualenv
- `pytest` passes with no failures
- `pcat validate` passes on the seed catalog
- `pcat find` on a copy of a seed pattern with renamed variables and added comments reports the matching id
- Editing any seed `impl.py` without bumping version makes `pcat validate` fail
- README explains: what this is, how to add a pattern, the review flow, versioning, and the planned miner/MCP/linter extensions
- `DECISIONS.md` lists every assumption you made
- `CLAUDE.md`, `KNOWN_GAPS.md` and `docs/specs/v1-catalog.md` exist and follow section 15
- All work is committed to git with a clean working tree

## 15. Handoff for future sessions

Future Claude Code sessions will start with no memory of this one. Leave the repository so a new session can continue from files alone.

**Git**
- Run `git init` if needed. Commit after each meaningful step (scaffold, canonicalizer, CLI, validation, seeds, CI, docs) with a clear message saying what and why.
- Finish with everything committed and `git status` clean.

**`CLAUDE.md`** (repo root; Claude Code reads it automatically at session start). Keep it under ~150 lines and include:
1. One-paragraph project purpose (organization-specific verified pattern catalog)
2. Current status: what v1 delivers, and that miner, MCP server and linter are planned next
3. Setup and commands: install, run tests, `pcat validate`, `pcat index`
4. Architecture map: one line per module in `src/pcat/` and what it owns
5. Invariants that must never break:
   - canonicalization output and fingerprints are stable; changing the rules changes every fingerprint and requires a deliberate migration
   - approved patterns are immutable; changes go through a new version
   - `catalog/index.json` is the only interface for future tools
   - output is deterministic and byte-identical across machines
6. Conventions: code style, test layout, commit message style
7. Pointers to `DECISIONS.md`, `KNOWN_GAPS.md` and `docs/specs/`
8. A "Before you finish any session" checklist: tests pass, `pcat validate` passes, `index.json` regenerated, `CLAUDE.md` and `KNOWN_GAPS.md` updated, work committed

**`KNOWN_GAPS.md`**: honest list of limitations, shortcuts, unhandled Python constructs, and anything in this spec not fully met, each with a one-line suggestion for fixing it.

**`docs/specs/v1-catalog.md`**: a verbatim copy of this spec. Future phase specs go in the same folder (`v2-miner.md`, `v3-mcp.md`, `v4-linter.md`).

**Rule for later sessions** (write this into `CLAUDE.md`): when given a new phase spec, first read `CLAUDE.md`, `DECISIONS.md`, `KNOWN_GAPS.md` and the earlier specs; save the new spec into `docs/specs/`; then build; then update the handoff files before finishing.
