# CLAUDE.md — handoff for future sessions

## Purpose

`pcat` is an organization-specific catalog of verified Python code patterns.
Common code shapes (binary search, retry with backoff, slugify, …) are written
once, reviewed by engineers and stored under `catalog/` with metadata, tests
and a fingerprint of their canonical form (names, comments, docstrings and
formatting removed). The goal is predictable code: humans and AI agents reuse
approved patterns instead of producing a new variation per prompt.

## Status

- **v1 / v1.1 (done):** catalog format, canonicalizer (`CANONICAL_VERSION = 2`),
  `pcat` CLI, 10 validation checks + `--base`, CI, CODEOWNERS, 6 seeds,
  `migrate-fingerprints`, versioned `index.json`. Specs: `docs/specs/v1*.md`.
- **v2 (done):** miner: `pcat mine` (function/fragment clusters, coverage),
  `pcat promote`. Benchmark: `docs/benchmarks/v2-results.md` (library code barely repeats).
- **v2.1 (done):** LLM output variance (`experiments/variance/`, `variance.py`):
  480 samples; effective shapes 15.7/20 same prompt, 17.4 paraphrased, 2.0 with a
  reference in the prompt. Write-up: `docs/benchmarks/v2.1-variance.md`.
- **v2.2 (done):** application catalog. `docs/catalog-review/` compares 17 tested
  variants; the owner's `choices.yaml` (final) became 7 patterns (`auth.*`, `db.*`,
  `http.*`, `config.*`, `ratelimit.*`, `importers.*`; FastAPI deferred until patterns
  support classes). Added: multi-function `pcat add`, `requires` metadata, `catalog` extra.
- **v3 (done):** MCP server. Metadata `exports`/`keywords`/`use_when`/`usage`;
  BM25 `pcat search` (threshold 9.08, dev-calibrated); `pcat serve` (tools
  `search_patterns`, `get_pattern`, `check_code`). Retrieval top-1 35/35 dev and
  held-out, false matches 0/10 dev, 2/15 held-out; end to end 160 runs: searched
  100%, right pattern fetched 140/140, pattern in code 87%. `docs/benchmarks/v3-mcp.md`.
- **Planned next:** v4 linter (flag application code that reimplements or uses
  deprecated patterns; report what differs from a fetched pattern).

## Setup and commands

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,catalog,mcp]"  # catalog = pattern libraries; mcp = pcat serve (CI: all)
pytest                      # tool tests + review variants; validates the real catalog
pcat validate               # all checks incl. every pattern's tests
pcat validate --skip-tests  # fast
pcat validate --skip-tests --base origin/main   # approved versions unchanged
pcat index                  # regenerate catalog/index.json (commit it)
pcat fingerprint <id> --write
pcat migrate-fingerprints   # after bumping CANONICAL_VERSION; prints old/new table
pcat mine <path>... --out <dir> [--jobs N]   # report.json + report.html; cache in .pcat-cache/
pcat promote <fn-cluster-id> --report <dir>/report.json --id <pattern-id> [--member N]
python scripts/benchmark.py # clones pinned OSS repos into .bench/ and mines them (not in CI)
python scripts/variance.py generate|analyze|reference|report --run-id <id>  # needs API key or `claude`
pcat search "<request>" [--limit N]          # BM25 over index.json; below threshold = no match
pcat serve [--catalog PATH] [--log FILE]     # MCP stdio server (claude mcp add pcat -- pcat serve …)
python scripts/mcp_eval.py heldout|retrieval|e2e|e2e-analyze   # v3 evaluation (heldout/e2e need `claude`)
```

## Canonicalization rules (version 2, summary)

Imports (sorted, one name each) → literal constants (`c0…`, source order) →
entry point `f0` → helpers (`f1…`, source order). Parameters/locals are
`v0…` per function. Never renamed: free names/builtins, imports, attributes,
`self`/`cls`, dunders, and keyword-argument names at call sites **except at
calls to functions defined in the pattern** (keywords then follow the callee's
placeholders; unmatched `**kwargs` keywords stay). Full list: `DECISIONS.md`.

## Architecture

- `src/pcat/canonical.py` — rules, `CANONICAL_VERSION`, fingerprint, name map,
  AST `render`, `extract_function` (function + helpers + constants + imports).
- `src/pcat/schema.py` — pydantic `PatternMeta` for `pattern.yaml` (extra keys rejected).
- `src/pcat/catalog.py` — layout, loading, `index.json`, all validation checks,
  per-pattern pytest runner, `--base` git check, `migrate_fingerprints`.
- `src/pcat/shape.py` — `SHAPE_VERSION`; canonical text with literal values blanked.
- `src/pcat/miner.py` — `MINER_VERSION`; discovery, cached per-file analysis
  (process pool), clustering, coverage, report JSON, promotion targets.
  `report_html.py` renders report.json as one self-contained page.
- `src/pcat/search.py` — tokenizer, BM25 `SearchIndex` over `index.json`,
  `MATCH_THRESHOLD` (recalibrate only on the dev set; `mcp_eval.py retrieval`).
- `src/pcat/serving.py` — `CatalogService`: the three tools as plain functions,
  server instructions, JSONL call log. `mcp_server.py` wraps it with FastMCP
  (only module importing `mcp`).
- `src/pcat/evaluation.py` — v3 request sets, retrieval metrics, threshold
  calibration, end-to-end scoring; `scripts/mcp_eval.py` drives it.
- `src/pcat/cli.py` — typer app, thin; errors → `error: …` + exit 1. `errors.py`: `PcatError`.
- `catalog/<category>/<pattern_id>[@vN]/` — `pattern.yaml` (optional `requires`, v3 fields),
  `impl.py`, `test_impl.py`; `catalog/index.json` is generated. App patterns + 6 seeds.
- `tests/` — tool tests; `root` fixture = temp copy of the catalog;
  `tests/fixtures/miner/` (excluded from collection).
- `src/pcat/variance.py` — variance logic (backends incl. `claude -p`, extraction,
  similarity, metrics); `scripts/variance.py`. Data: `experiments/variance/` (frozen).
- `experiments/mcp/` — v3 dev negatives, held-out needs/requests (frozen),
  `retrieval.json`, `e2e/<task>/sample_NN.{json,log.jsonl}`, `e2e_results.json`.
- `scripts/benchmark.py`, `docs/benchmarks/` — benchmarks and their results.
- `docs/catalog-review/` — v2.2 comparison doc, `choices.yaml`, `variants/<task>/`
  (+ tests, in pytest testpaths; skip without `requirements.txt` libraries).

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
   linter). Add fields compatibly; never require them to read pattern folders.
   In-package commands (`validate`, `mine`, `serve`) may read folders via
   `catalog.py` (the index lacks code and shape fingerprints); search uses the index only.
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
- Pattern tests: `test_impl.py` next to `impl.py`, `from impl import …`, normal/edge/
  failure/security cases; no network or sleeping; `importorskip` for `requires` libs.
- Commits: imperative subject (≤ 72 chars) saying what; body saying why.
  One meaningful step per commit; one pattern per PR.

## Where to look

- `DECISIONS.md` — every assumption made so far (read before changing behavior)
- `KNOWN_GAPS.md` — limitations and suggested fixes (good backlog)
- `docs/specs/` — phase specs (`v1-catalog.md`, `v1.1-…`, `v2-miner.md`,
  `v2.1-…`, `v2.2-app-catalog.md`, `v3-mcp-server.md`; later `v4-linter.md`)
- `docs/benchmarks/` — `v2-results.md` (mining), `v2.1-variance.md`, `v3-mcp.md`
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
