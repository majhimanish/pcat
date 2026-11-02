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
- **v1.1 (done):** canonicalization rules v2 (`CANONICAL_VERSION = 2`):
  keyword arguments at calls to the pattern's own functions are renamed;
  literal module constants allowed (`cN`); `pcat migrate-fingerprints`;
  `index.json` records `canonical_version`; `--base` allows fingerprint changes
  only with a rules bump and byte-identical `impl.py`. Spec:
  `docs/specs/v1.1-canonicalizer-fix.md`. Seed fingerprints did not change.
- **v2 (done):** pattern miner. `pcat mine` clusters repeated function shapes
  and block fragments across repos, reports catalog coverage (`report.json` +
  `report.html`); `pcat promote` turns a function cluster into a pattern via the
  `pcat add` flow. Spec: `docs/specs/v2-miner.md`. Benchmark on
  requests/flask/fastapi: `docs/benchmarks/v2-results.md` (0% coverage; all
  default clusters were FastAPI tutorial copies; library code barely repeats).
- **Planned next:** v3 MCP server (serve the catalog to coding agents), v4 linter
  (flag application code that reimplements or uses deprecated patterns). Before
  v4, re-run the benchmark on application code (see the results doc).

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
pcat migrate-fingerprints   # after bumping CANONICAL_VERSION; prints old/new table
pcat mine <path>... --out <dir> [--jobs N]   # report.json + report.html; cache in .pcat-cache/
pcat promote <fn-cluster-id> --report <dir>/report.json --id <pattern-id> [--member N]
python scripts/benchmark.py # clones pinned OSS repos into .bench/ and mines them (not in CI)
```

## Canonicalization rules (version 2, summary)

Imports (sorted, one name each) → literal constants (`c0…`, source order) →
entry point `f0` → helpers (`f1…`, source order). Parameters/locals are
`v0…` per function. Never renamed: free names/builtins, imports, attributes,
`self`/`cls`, dunders, and keyword-argument names at call sites **except at
calls to functions defined in the pattern** (keywords then follow the callee's
placeholders; unmatched `**kwargs` keywords stay). Full list: `DECISIONS.md`.

## Architecture

- `src/pcat/canonical.py` — canonicalization rules and `CANONICAL_VERSION`,
  fingerprint, name map, AST-based `render`, `extract_function` (function +
  helpers + used constants + used imports). Owns every fingerprint.
- `src/pcat/schema.py` — pydantic `PatternMeta` for `pattern.yaml` (unknown keys
  rejected, cross-field rules).
- `src/pcat/catalog.py` — on-disk layout, loading, `index.json` generation,
  all validation checks (`validate`), per-pattern pytest runner, `--base` git
  check, `migrate_fingerprints`.
- `src/pcat/shape.py` — `SHAPE_VERSION`; shape text = canonical text with literal
  values blanked (True/False/None/... kept). Never changes canonical fingerprints.
- `src/pcat/miner.py` — `MINER_VERSION` (cache format); file discovery and
  filters, per-file analysis (functions + fragments, cached by content hash and
  rule versions, process pool), clustering, coverage, report JSON, promotion
  target selection.
- `src/pcat/report_html.py` — renders report.json data as one self-contained page.
- `src/pcat/cli.py` — typer app; thin layer over the modules above; errors
  become `error: …` + exit 1.
- `src/pcat/errors.py` — `PcatError` and subclasses.
- `catalog/<category>/<pattern_id>[@vN]/` — `pattern.yaml`, `impl.py`,
  `test_impl.py`; `catalog/index.json` is generated.
- `tests/` — tool tests; `conftest.py` gives a `root` fixture with a temp copy
  of the seed catalog; `tests/fixtures/miner/` holds miner fixture code
  (excluded from collection).
- `scripts/benchmark.py`, `docs/benchmarks/` — miner benchmark and its results.

## Invariants (never break these)

1. **Canonical output and fingerprints are stable.** Any change that can alter
   what `canonical.analyze` produces must, in one PR: bump `CANONICAL_VERSION`,
   run `pcat migrate-fingerprints` (paste its table in the PR), and explain why
   in `DECISIONS.md`. Never edit `impl.py` in the same PR. Never "fix" a
   fingerprint casually.
2. **Approved patterns are immutable.** Never edit `impl.py` (not even
   comments), `behavior`, `entry_point` or `keep_annotations` of a version on
   `main`; its `fingerprint` changes only via a rules migration.
   Changes go in `<pattern_id>@v<N+1>/`; the old one becomes
   `status: deprecated` + `replaced_by`.
3. **`catalog/index.json` is the only interface for out-of-process tools** (MCP
   server, linter). Add fields compatibly; never require them to read pattern
   folders. In-package commands (`validate`, `mine`) may read folders via
   `catalog.py`; the miner does, because the index lacks shape fingerprints.
4. **Output is deterministic and byte-identical across machines**: sorted
   iteration everywhere, `\n` line endings, `json.dumps(sort_keys=True,
   indent=2)`, no timestamps, no absolute paths in generated files. Miner
   reports must not depend on `--jobs` or cache state; bump `SHAPE_VERSION` /
   `MINER_VERSION` when shape rules / per-file analysis output change.

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
- `docs/specs/` — phase specs (`v1-catalog.md`, `v1.1-canonicalizer-fix.md`,
  `v2-miner.md`; later `v3-mcp.md`, `v4-linter.md`)
- `docs/benchmarks/v2-results.md` — what mining real code found
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
