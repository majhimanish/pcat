# v6 — Productize

Work unattended. Do not stop to ask questions; when something is ambiguous, pick the simplest reasonable option, record it in `DECISIONS.md`, and continue.

## 0. Before you start

1. You were given three files with this spec: `PROJECT_BRIEF.md`, this file and `v7-pitch.md`. Save `PROJECT_BRIEF.md` at the repo root and both specs verbatim into `docs/specs/` (`v6-productize.md`, `v7-pitch.md`). Commit them first.
2. Read `PROJECT_BRIEF.md`, `CLAUDE.md`, `DECISIONS.md`, `KNOWN_GAPS.md`, every spec in `docs/specs/`, and everything in `docs/benchmarks/` (especially `summary.md` and `v5.2-unsafe-neighbour.md`).
3. Run the full test matrix and `pcat validate` (for `catalog/` and every v5 catalog) to confirm a green start.
4. Leave pull request #1 alone.
5. When v6 is complete and pushed, continue directly with `docs/specs/v7-pitch.md` in the same session.

Do not change canonicalization rules, shape fingerprints, any `impl.py`, fingerprint or guard, the search threshold, the default inference threshold, or any experiment data. Every earlier experiment script must still run.

## 1. Goal

The full loop exists and has evidence behind it, but only its author can use it. v6 makes pcat something a real team can install and try in an afternoon:
- one command to set it up in a repository
- a one-time audit that finds existing code which looks like a catalog pattern but breaks its guards (v5.2 showed agents rarely fix flawed code next to their work, and copied flaws carry no marker)
- a clean package, separated from research code
- documentation a newcomer can follow, proven by following it

Build in this order, committing after each part: **A** separate product from research → **B** packaging → **C** `pcat audit` → **D** `pcat init` → **E** small product-facing fixes → **F** getting-started guide and dogfooding → **G** handoff.

## 2. Part A — separate product from research

- The installed package should contain only product code: canonicalizer, catalog, miner, search, server, linter, approvals, audit, init and the CLI.
- Move experiment-only modules (for example the v2.1/v5/v5.2 harnesses and scorers) out of `src/pcat/` into an `experiments/lib/` (or similar) package used by `scripts/`. Keep their tests, moved alongside.
- Every script in `scripts/` must still run; re-run each analysis step that needs no new generation and confirm byte-identical outputs where earlier phases guaranteed them.
- Remove experiment-only commands from the product CLI (keep them reachable through `scripts/`). Record each move in `DECISIONS.md`.

## 3. Part B — packaging

- Version `0.1.0`, `pcat --version`, and a `CHANGELOG.md` summarizing v1–v6 in a few lines each.
- Installable with `pipx install "git+https://github.com/majhimanish/pcat"` and with `pip`. Optional extras stay (`catalog`, `mcp`, `dev`); document which a team needs.
- The generic 7 application patterns ship as a **starter catalog** inside the package data, so `pcat init` can copy them without the source repo.
- Do not publish to PyPI (it needs the owner's credentials); document the steps the owner would take.
- Verify a clean install in a fresh virtualenv from a built wheel, on Python 3.11 and 3.13.

## 4. Part C — `pcat audit`

A one-time, human-reviewed report on existing code; never a CI gate.

```
pcat audit <path> [--catalog PATH] [--out DIR]
```
- Uses the opt-in inference variant from v5.2 (similarity ≥ 0.75) to find functions that look derived from a catalog pattern, then applies that pattern's guards.
- Report (`audit.html` self-contained and readable on a phone, plus `audit.json`, deterministic): each finding with file, function, the pattern it resembles, similarity, **the margin to the second-best pattern** (displayed only; v5.2 found sibling-pattern confusion, and a margin rule is untested, so do not filter on it), the guard violated and a short explanation in the user's names.
- Summary at the top: functions scanned, findings, and a plain note that findings are candidates for human review, not confirmed bugs.
- Exit 0 always (unless the command itself fails).
- Run it on the three v5 apps and the planted v5.2 working copies; report how many planted neighbours it surfaces and how many findings there are on untouched code. Save under `experiments/v6/audit/`. This is a measurement, not tuning: do not change the threshold.

## 5. Part D — `pcat init`

One command to set pcat up in a target repository.

```
pcat init [--path REPO] [--catalog PATH | --starter] [--apply]
```
- **Dry run by default:** print every file it would create or change, with a short reason. `--apply` makes the changes. Running it twice changes nothing the second time.
- Detects: Python project, main framework (FastAPI, Django, Flask or none), git repo, CI provider (GitHub Actions supported; others: print instructions only).
- Creates or updates:
  - `.pcat/config.yaml`: catalog location, approvers, lint settings
  - a catalog: an existing path given by `--catalog`, or `pcat-catalog/` in the repo seeded with the starter catalog (`--starter`), or empty
  - Claude Code MCP configuration for `pcat serve` at the project level (check the current Claude Code documentation for the correct file name and format, and record the source)
  - a one-line note in the repo's `CLAUDE.md` (create if absent)
  - GitHub Actions workflows for `pcat lint` and `pcat approvals check`, using the recommended settings from v5.1 (`--changed-since`, `--fail-on high`, marked code only)
  - `.pcat/approvers.yaml` with a commented template
- Then runs `pcat mine` on the repo and writes a short candidates report pointing to `pcat promote`.
- Ends with a numbered list of what the human must do next (review candidates, add approvers, protect the branch, make the checks required).

## 6. Part E — small product-facing fixes

From `KNOWN_GAPS.md`, fix only these, each with a regression test:
- a `# pcat:` marker placed between decorators and `def` is ignored
- approvals whose deviation no longer fires are not reported as unnecessary
- an older pcat silently drops patterns that use newer metadata keys: make `pcat` refuse a catalog whose patterns use keys it doesn't know, with a message to upgrade
- `src/` layouts and namespace packages get a shorter module path

## 7. Part F — getting-started guide and dogfooding

- `docs/getting-started.md`: a 30-minute walkthrough for a team lead: install, `pcat init`, review candidates, promote and approve a first pattern, connect Claude Code, see a deviation flagged on a pull request, run an audit. Plain language, copy-paste commands, short sections.
- A **Quickstart** at the top of the README (under 20 lines). Move research history lower in the README.
- **Dogfood:** follow the guide literally, step by step, on a fresh copy of the healthchecks app (from `.bench/apps/`) in a new folder, with pcat installed from the built wheel. Write down every point of friction, fix what's fixable, and record the rest in `KNOWN_GAPS.md`. Finish with 2 `claude -p` runs in that copy to confirm the agent finds and uses the pcat tools through the configuration `pcat init` wrote. Save notes under `experiments/v6/dogfood/`.

## 8. Tests

- Package contents: no experiment modules in the wheel; starter catalog included
- `init`: dry run changes nothing; `--apply` creates expected files; second run is a no-op; framework detection; non-GitHub CI prints instructions
- `audit`: deterministic report; exit code 0; margin displayed; no findings below threshold
- Part E regressions
- Moved experiment code: its tests still pass in their new location
- Everything passes on Python 3.11 and 3.13 in all extras combinations

## 9. Acceptance criteria

- Full test matrix passes; `pcat validate` passes for `catalog/` and every v5 catalog; CI passes on `main`
- A wheel installs cleanly in a fresh virtualenv; `pcat --version` prints `0.1.0`
- The dogfood run followed the guide end to end, with notes and 2 agent runs recorded
- No fingerprint, `impl.py`, guard, threshold or earlier experiment output changed

## 10. Handoff

- Update `CLAUDE.md` (at or under 150 lines), `DECISIONS.md`, `KNOWN_GAPS.md`, README, and `PROJECT_BRIEF.md` (**Status**, phase history row, **Open items**).
- Commit after each part, push to `main`, clean tree. Then start `docs/specs/v7-pitch.md`.
