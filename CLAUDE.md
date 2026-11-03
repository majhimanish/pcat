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
  `pcat` CLI, validation checks + `--base`, CI, CODEOWNERS, 6 seeds,
  `migrate-fingerprints`, versioned `index.json`. Specs: `docs/specs/v1*.md`.
- **v2 (done):** miner `pcat mine`, `pcat promote` (library code barely repeats).
- **v2.1 (done):** LLM variance, 480 samples: effective shapes 15.7/20 same prompt,
  17.4 paraphrased, 2.0 with a reference in the prompt.
- **v2.2 (done):** owner's `docs/catalog-review/choices.yaml` → 7 application
  patterns (`auth.*`, `db.*`, `http.*`, `config.*`, `ratelimit.*`, `importers.*`;
  FastAPI deferred: no classes). Multi-function `pcat add`, `requires`, `catalog` extra.
- **v3 (done):** MCP server `pcat serve` (`search_patterns`, `get_pattern`,
  `check_code`), BM25 `pcat search` (threshold 9.08). Retrieval top-1 35/35 dev and
  held-out; end to end: right pattern fetched 140/140, pattern in code 87%.
- **v4 (done):** deviation linter. Markers `# pcat: <id>@vN` (written by
  `get_pattern`), inferred provenance (threshold 0.56), `guards` in pattern.yaml
  (check 11), deviation codes PC100–PC110, `pcat lint` with `# pcat-allow`
  approvals, `check_code(code, pattern_id)`. Replay: 0/122 exact matches above low,
  18/18 misses flagged; feedback run: unapproved high 12/60 → 0/60 (mostly approved,
  not fixed). Next: human-confirmed approvals, guards grown from observed deviations.

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
pcat lint <path>... [--changed-since REF] [--format text|json|github] [--fail-on high] [--catalog P]
python scripts/lint_eval.py calibrate|replay|feedback|feedback-analyze   # v4 evaluation
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
- `shape.py` (`SHAPE_VERSION`, literals blanked); `miner.py` (`MINER_VERSION`;
  discovery, cached per-file analysis, clusters, coverage); `report_html.py`.
- `src/pcat/search.py` — tokenizer, BM25 `SearchIndex` over `index.json`,
  `MATCH_THRESHOLD` (recalibrate only on the dev set; `mcp_eval.py retrieval`).
- `src/pcat/serving.py` — `CatalogService` (the three tools, instructions, JSONL
  log); `mcp_server.py` wraps it with FastMCP (only module importing `mcp`).
  `evaluation.py` + `scripts/mcp_eval.py` — v3 evaluation.
- `src/pcat/codeunit.py` — a function + same-file helpers/constants/imports, name
  resolution (imports → origin, `.method`), anonymized statement keys.
- `src/pcat/provenance.py` — markers/approvals in the comment block above a function,
  `INFERENCE_THRESHOLD`, inference. `guards.py` — guard checks (validation check 11).
- `src/pcat/deviation.py` — PC100–PC110 (codes, severities, alignment, diff).
  `lint.py` — `pcat lint` (approvals, `--changed-since`, text/json/github).
  `linteval.py` + `scripts/lint_eval.py` — v4 evaluation; data in `experiments/linter/`.
- `src/pcat/cli.py` — typer app, thin; errors → `error: …` + exit 1. `errors.py`: `PcatError`.
- `catalog/<category>/<pattern_id>[@vN]/` — `pattern.yaml` (optional `requires`, v3 fields, `guards`),
  `impl.py`, `test_impl.py`; `catalog/index.json` is generated. App patterns + 6 seeds.
- `tests/` — tool tests; `root` fixture = temp copy of the catalog.
- `src/pcat/variance.py` — variance logic (backends incl. `claude -p`, similarity);
  `scripts/variance.py`. Data (frozen): `experiments/variance/`, `experiments/mcp/`
  (v3 held-out set, `e2e/<task>/sample_NN.{json,log.jsonl}`, results).
- `scripts/benchmark.py`, `docs/benchmarks/` — benchmarks and their results.
  `docs/ci/pcat-lint.yml` — reusable workflow for client repositories.
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
3. **`catalog/index.json` is the only interface for out-of-process tools.** Add
   fields compatibly; never require them to read pattern folders. In-package
   commands (`validate`, `mine`, `serve`, `lint`) may read folders via `catalog.py`
   (the index lacks code, shape fingerprints and guards); search uses the index only.
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
  `v2.1-…`, `v2.2-app-catalog.md`, `v3-mcp-server.md`, `v4-linter.md`)
- `docs/benchmarks/` — `v2-results.md`, `v2.1-variance.md`, `v3-mcp.md`, `v4-linter.md`
- `README.md` — user-facing docs: adding patterns, review flow, versioning

## Rule for later sessions

For a new phase spec: read `CLAUDE.md`, `DECISIONS.md`, `KNOWN_GAPS.md` and earlier
specs; save the spec verbatim in `docs/specs/`; build; update the handoff files.

## Before you finish any session

- [ ] `pytest` passes
- [ ] `pcat validate` passes
- [ ] `pcat index` run and `catalog/index.json` committed
- [ ] `CLAUDE.md` (status, architecture) and `KNOWN_GAPS.md` updated
- [ ] new assumptions recorded in `DECISIONS.md`
- [ ] all work committed; `git status` clean
