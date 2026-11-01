# CLAUDE.md — handoff for future sessions

## Purpose

`pcat` is an organization-specific catalog of verified Python code patterns.
Common code shapes (binary search, retry with backoff, slugify, …) are written
once, reviewed by engineers and stored under `catalog/` with metadata, tests
and a fingerprint of their canonical form (names, comments, docstrings and
formatting removed). The goal is predictable code: humans and AI agents reuse
approved patterns instead of producing a new variation per prompt.

## Status

- **v1 (done):** catalog format, canonicalizer, `pcat` CLI (`new add canonical
  fingerprint validate index show render find`), 10 validation checks plus an
  optional `--base` immutability check, GitHub Actions CI, CODEOWNERS, 6 seed
  patterns. Spec: `docs/specs/v1-catalog.md`.
- **Planned next:** v2 miner (find candidate patterns in repos), v3 MCP server
  (serve the catalog to coding agents), v4 linter (flag application code that
  reimplements or uses deprecated patterns). Specs will go in `docs/specs/`.

## Setup and commands

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e .[dev]
pytest                      # tool tests (tests/), includes validating the real catalog
pcat validate               # all checks incl. every pattern's tests
pcat validate --skip-tests  # fast
pcat validate --skip-tests --base origin/main   # approved versions unchanged
pcat index                  # regenerate catalog/index.json (commit it)
pcat fingerprint <id> --write
```

## Architecture

- `src/pcat/canonical.py` — canonicalization rules, fingerprint, name map,
  AST-based `render`, `extract_function` (function + helpers + used imports).
  Owns every fingerprint.
- `src/pcat/schema.py` — pydantic `PatternMeta` for `pattern.yaml` (unknown keys
  rejected, cross-field rules).
- `src/pcat/catalog.py` — on-disk layout, loading, `index.json` generation,
  all validation checks (`validate`), per-pattern pytest runner, `--base` git
  check.
- `src/pcat/cli.py` — typer app; thin layer over the two modules above; errors
  become `error: …` + exit 1.
- `src/pcat/errors.py` — `PcatError` and subclasses.
- `catalog/<category>/<pattern_id>[@vN]/` — `pattern.yaml`, `impl.py`,
  `test_impl.py`; `catalog/index.json` is generated.
- `tests/` — tool tests; `conftest.py` gives a `root` fixture with a temp copy
  of the seed catalog.

## Invariants (never break these)

1. **Canonical output and fingerprints are stable.** Any change to what
   `canonical.analyze` produces changes fingerprints of every pattern. That
   needs a deliberate migration: one PR that changes the rules, re-runs
   `pcat fingerprint --write` for all patterns, regenerates the index, and
   explains why in `DECISIONS.md`. Never "fix" a fingerprint casually.
2. **Approved patterns are immutable.** Never edit `impl.py`, `behavior`,
   `entry_point`, `keep_annotations` or `fingerprint` of a version on `main`.
   Changes go in `<pattern_id>@v<N+1>/`; the old one becomes
   `status: deprecated` + `replaced_by`.
3. **`catalog/index.json` is the only interface for future tools** (miner, MCP,
   linter). Add fields compatibly; never require tools to read pattern folders.
4. **Output is deterministic and byte-identical across machines**: sorted
   iteration everywhere, `\n` line endings, `json.dumps(sort_keys=True,
   indent=2)`, no timestamps, no absolute paths in generated files.

## Conventions

- Python 3.11+, type hints, `from __future__ import annotations`, standard
  library `ast` only for parsing/printing, line length ~100.
- Library code raises `PcatError` subclasses; only `cli.py` prints or exits.
- Tests: `tests/test_<module>.py`; use the `root` fixture (never mutate the real
  `catalog/` in tests). Each validation check has a test that triggers it.
- Pattern tests: `test_impl.py` next to `impl.py`, `from impl import …`, cover
  normal cases, edge cases and empty input; no network, no sleeping.
- Commits: imperative subject (≤ 72 chars) saying what; body saying why.
  One meaningful step per commit; one pattern per PR.

## Where to look

- `DECISIONS.md` — every assumption made so far (read before changing behavior)
- `KNOWN_GAPS.md` — limitations and suggested fixes (good backlog)
- `docs/specs/` — phase specs (`v1-catalog.md`; later `v2-miner.md`,
  `v3-mcp.md`, `v4-linter.md`)
- `README.md` — user-facing docs: adding patterns, review flow, versioning

## Rule for later sessions

When given a new phase spec: first read `CLAUDE.md`, `DECISIONS.md`,
`KNOWN_GAPS.md` and the earlier specs in `docs/specs/`; save the new spec
verbatim into `docs/specs/` (e.g. `v2-miner.md`); then build; then update the
handoff files (`CLAUDE.md` status/architecture, `DECISIONS.md`,
`KNOWN_GAPS.md`) before finishing.

## Before you finish any session

- [ ] `pytest` passes
- [ ] `pcat validate` passes
- [ ] `pcat index` run and `catalog/index.json` committed
- [ ] `CLAUDE.md` (status, architecture) and `KNOWN_GAPS.md` updated
- [ ] new assumptions recorded in `DECISIONS.md`
- [ ] all work committed; `git status` clean
