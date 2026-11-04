# CLAUDE.md — handoff for future sessions

## Purpose

`pcat` is an organization-specific catalog of verified Python code patterns.
Common code shapes (binary search, retry with backoff, slugify, …) are written
once, reviewed by engineers and stored under `catalog/` with metadata, tests
and a fingerprint of their canonical form (names, comments, docstrings and
formatting removed). The goal is predictable code: humans and AI agents reuse
approved patterns instead of producing a new variation per prompt.

## Status

- **v1–v2.2:** catalog, canonicalizer (`CANONICAL_VERSION = 2`), CLI, validation, CI, miner,
  variance study, 7 app patterns from `docs/catalog-review/choices.yaml` (+ 6 seeds).
- **v3:** MCP server `pcat serve` (`search_patterns`, `get_pattern`, `check_code`),
  BM25 `pcat search`. **v4:** linter: markers `# pcat: <id>@vN`, inference (0.56),
  `guards` (check 11), PC100–PC110, `pcat lint`, `check_code(code, pattern_id)`.
- **v4.1:** hashed approvals (`# pcat-allow: PC100 #<hash> -- reason`), confirmed/proposed/
  stale; proposals need a human (`pcat approvals check`); PC111; `must_include`. PR #1: demo, open.
- **v5:** CTFd, healthchecks, LNbits as orgs with own catalogs (`experiments/v5/catalogs/`,
  self-reviewed); 144 in-repo runs: matches 0.72 vs 0.46, baseline copies siblings.
- **v5.1 (done):** linter on real code: per-unit symbol table (same-file names →
  `<module>.<name>`), partial code in `check_code` (`context`, `file_path`, `resolution`),
  check 12 (`requires` vs imports, `import_names`, `first_party` in `catalog/catalog.yaml`),
  guard `match: any`, graded PC102; re-score 0/72 false CI failures (was 5); survey:
  inferred findings on app code mostly noise. Headlines: `docs/benchmarks/summary.md`.
- **Next ideas:** inference calibration on app code; markers inside decorator blocks.

## Setup and commands

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,catalog,mcp]"  # catalog = pattern libraries; mcp = pcat serve (CI: all)
pytest                      # tool tests + review variants; validates the real catalog
pcat validate               # all checks incl. every pattern's tests
pcat validate --skip-tests  # fast
pcat validate --skip-tests --base origin/main   # approved versions unchanged
pcat index                  # regenerate catalog/index.json (commit it)
pcat fingerprint <id> --write; pcat migrate-fingerprints   # the latter after a CANONICAL_VERSION bump
pcat mine <path>... --out <dir> [--jobs N]   # report.json + report.html; cache in .pcat-cache/
pcat promote <fn-cluster-id> --report <dir>/report.json --id <pattern-id> [--member N]
python scripts/benchmark.py # clones pinned OSS repos into .bench/ and mines them (not in CI)
python scripts/variance.py generate|analyze|reference|report --run-id <id>  # needs API key or `claude`
pcat search "<request>" [--limit N]          # BM25 over index.json; below threshold = no match
pcat serve [--catalog PATH] [--log FILE] [--repo DIR]  # MCP stdio server (claude mcp add pcat -- pcat serve …)
python scripts/mcp_eval.py heldout|retrieval|e2e|e2e-analyze   # v3 evaluation (heldout/e2e need `claude`)
pcat lint <path>... [--changed-since REF] [--format text|json|github] [--fail-on high] [--catalog P]
pcat approvals check --repo OWNER/REPO --pr N   # GITHUB_TOKEN; fails while proposals wait
python scripts/lint_eval.py calibrate|replay|feedback|feedback-analyze   # v4 evaluation
python scripts/v5.py clone|mine|references|requests|retrieval; python scripts/v5_e2e.py run|analyze
python scripts/v5_1.py lint-e2e|compare-e2e|compare-samples|survey   # re-score, no agent runs
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
- `src/pcat/codeunit.py` — a function + same-file helpers/constants/imports, symbol
  table (imports, same-file defs → module path, unknown names), `target_matches`.
- `src/pcat/provenance.py` — markers/approvals in the comment block above a function,
  `INFERENCE_THRESHOLD`, inference. `guards.py` — guard checks (validation check 11).
- `src/pcat/deviation.py` — PC100–PC110 (`bind` both units, alignment, diff, skipped rules).
  `requirements.py` — `requires` ↔ import names, check 12.
  `lint.py` — `pcat lint` (approval states, PC111, `--changed-since`, text/json/github).
  `approvals.py` — approver config, CODEOWNERS, GitHub client, confirmation gate.
  `linteval.py` + `scripts/lint_eval.py` — v4 evaluation; data in `experiments/linter/`.
- `src/pcat/v5.py` — v5 tasks, working copies, scoring. `rescore.py` + `scripts/v5_1.py` — v5.1.
- `src/pcat/cli.py` — typer app, thin; errors → `error: …` + exit 1. `errors.py`: `PcatError`.
- `catalog/<category>/<pattern_id>[@vN]/` — `pattern.yaml` (optional `requires`, v3 fields, `guards`),
  `impl.py`, `test_impl.py`; `catalog/index.json` is generated. App patterns + 6 seeds.
- `tests/` — tool tests; `root` fixture = temp copy of the catalog.
- `src/pcat/variance.py` — variance logic (`claude -p` backends, similarity). Frozen data:
  `experiments/{variance,mcp,linter,v5,v5.1}/`.
- `scripts/benchmark.py`, `docs/benchmarks/` — benchmarks and their results.
  `docs/ci/pcat-{lint,approvals}.yml` — workflows for client repositories; this repo
  runs `.github/workflows/pcat-approvals.yml` with `.pcat/approvers.yaml` (solo mode).
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

- `DECISIONS.md` (every assumption; read before changing behavior), `KNOWN_GAPS.md` (backlog)
- `docs/specs/` — phase specs (`v1-catalog.md` … `v4.1-human-approval.md`, `v5-…`)
- `docs/benchmarks/` — per phase, `v5-open-source.md`, and `summary.md` (all headlines)
- `README.md` — user-facing docs: adding patterns, review flow, versioning

## Rule for later sessions

For a new phase spec: read `CLAUDE.md`, `DECISIONS.md`, `KNOWN_GAPS.md` and earlier
specs; save the spec verbatim in `docs/specs/`; build; update the handoff files.

## Before you finish any session

- [ ] `pytest` and `pcat validate` pass; `pcat index` run and `catalog/index.json` committed
- [ ] `CLAUDE.md` (status, architecture, ≤ 150 lines), `KNOWN_GAPS.md`, `DECISIONS.md` updated
- [ ] all work committed; `git status` clean
