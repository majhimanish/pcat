# pcat — Project brief

This file carries the project's context across fresh sessions. A new Claude chat or Claude Code session should read it first. Keep it current: update the **Status** and **Open items** sections at the end of every phase.

## What pcat is

A tool that makes AI-written code predictable inside an organization. Reviewed code patterns are kept in a catalog, served to coding agents through an MCP server, and enforced in CI by a linter that explains how new code deviates from the pattern it came from.

**Origin of the idea.** It began as "compression like chemistry": fixed rules (physics) plus raw materials, where decompression runs a chain of reactions. That narrowed to compressing source code by mapping standard algorithms to dictionary entries plus a name map, accepting lossy output (comments and formatting dropped, behavior kept). It then became a per-organization catalog of verified code shapes that AI agents reuse, so the code an employee gets doesn't depend on how they worded the prompt.

## The pitch

**Problem:** the same request to an AI coding agent produces different code each time, depending on who asks and how. Reviewers re-check the same kinds of code, and one flawed version can spread.

**Product:**
- a catalog of reviewed patterns, mined from the organization's own code and approved through pull requests
- an MCP server so agents search and fetch the approved version instead of improvising
- a CI linter that reports how code deviates from its pattern (guards encode what reviewers cared about), with human-confirmed approvals for legitimate deviations

**Differentiator:** rules files and style guides steer the model; pcat checks the output in CI.

**Focus:** application glue code (auth, tokens, passwords, pagination, retries, config, rate limiting, imports), not textbook algorithms.

**Numbers:** use only what `docs/benchmarks/summary.md` marks as safe to pitch, with its caveats; every pitched number is registered in `docs/pitch/claims.md`. The three headlines (wording in `docs/pitch/one-pager.md`):
- variance: asked for the same function 20 times, 15.7 effectively distinct versions on average; with a reference, 2.0 (v2.1, lab)
- first-time code inside real apps: 2/12 matched the house version without pcat, 12/12 with it, on the 4 tasks where it existed nowhere else in the repo (v5); where a sibling exists, agents copy it either way
- every high-severity deviation becomes a human decision: 20 of 60 lab runs broke a guard, all flagged with hashed proposals, 0 uncovered (v4.1 / v5 Part A); no correct code failed CI in 144 in-repo runs (v5.1)

## Architecture (Python, single package, CLI `pcat`)

- **Canonicalizer:** lossy, deterministic; renames to `fN`/`vM`/`cN`; fingerprints; versioned rules (`CANONICAL_VERSION`)
- **Catalog:** pattern folders (`pattern.yaml`, `impl.py`, tests), `index.json`, immutable approved versions, validation checks
- **Miner:** shape and fragment clustering, `pcat mine` / `pcat promote`
- **Search and MCP server:** BM25 keyword search, `search_patterns` / `get_pattern` / `check_code`, `pcat serve`
- **Linter:** markers (`# pcat: id@vN`), guards, deviation codes PC100–PC111, `pcat lint`
- **Approvals:** `# pcat-allow: CODE #hash -- reason`; proposals confirmed by a human on the pull request

Details live in `CLAUDE.md`, `DECISIONS.md`, `KNOWN_GAPS.md`, `docs/specs/` and `docs/benchmarks/`.

## Phase history

| Phase | What it did | Outcome |
|---|---|---|
| v1 | Catalog, canonicalizer, CLI, 6 algorithm seeds | Works; deterministic across Python versions |
| v1.1 | Keyword-argument fix, constants, rule versioning | 0 seed fingerprints changed |
| v2 | Miner | Libraries barely repeat; repetition lives in application glue |
| v2.1 | LLM variance experiment | Strong evidence: high variance, collapses with a reference |
| v2.2 | Owner-chosen application catalog (7 patterns) | 0 of 135 samples already matched the chosen pattern |
| v3 | MCP server | Agents searched every time; 122/140 matched (before literal-aware guards) |
| v4 / v4.1 | Linter, guards, human-confirmed approvals | Silent regressions become visible decisions |
| v5 | Three real open-source apps as simulated orgs | Agents already copy neighbours; catalog wins for first-time code |
| v5.1 | Linter fixes for real code | 0/72 false CI failures on marked code; inference is noisy |
| v5.2 | Unsafe planted neighbour | Inherited flaw 3/54 without catalog, 0/54 with; CI can't catch copied flaws without markers |
| v6 | Productize: package split, starter catalog, `pcat init`, `pcat audit`, getting-started guide | Installs from a wheel on 3.11/3.13; guide dogfooded on healthchecks (8 frictions, 5 fixed); audit surfaces 10/18 planted neighbours, 5 candidates on 4,086 untouched functions |
| v7 | Pitch material: one-pager, deck, demo script, FAQ, pilot plan, claims register | Every pitched number sourced and checked by script; demo rehearsal found two product gaps (changed constants, which check to require) |

## How the owner works

- Solo developer, often on a phone; English is a second language, so plain, short explanations work best.
- Uploads a Markdown spec to Claude Code and waits for it to finish unattended, then pastes the final message into a Claude chat to plan the next phase.
- Pushes directly to `main` while developing.
- Usage: Claude Code runs on the owner's Claude plan; CLI cost figures are estimates and may reflect plan usage rather than billing.

## How specs are written

Each phase spec follows the same structure, which has worked well:
1. "Work unattended; record assumptions in `DECISIONS.md`."
2. **Before you start:** read `PROJECT_BRIEF.md`, `CLAUDE.md`, `DECISIONS.md`, `KNOWN_GAPS.md`, earlier specs and benchmarks; save the spec into `docs/specs/`; confirm a green start.
3. **Frozen list:** what must not change (fingerprints, `impl.py`, thresholds, earlier experiment data).
4. **Goal**, then **Parts in order**, committing after each.
5. For experiments: commit prompts or planted data **before** any run; held-out data never used for tuning; usage cap with smoke test and resumable runs.
6. **Tests**, **acceptance criteria**, **handoff** (update `CLAUDE.md` within ~150 lines, `DECISIONS.md`, `KNOWN_GAPS.md`, README, this brief), push to `main`, clean tree.
7. **Final message:** what to report.

If a session stops partway, a fresh session resumes from git history and the handoff files; tell it which spec and part to continue and what must not be regenerated.

## Status

(Updated at the end of each phase.) Last completed: **v7** (pitch material). Next: **a real pilot** with one team (`docs/pitch/pilot-plan.md`); before it, fix the two gaps the demo rehearsal found (KNOWN_GAPS, "Pitch (v7)").

## Where things are

- `docs/getting-started.md`: the 30-minute guide for a team trying pcat
- `docs/pitch/one-pager.md`, `deck.pptx` / `deck.pdf`: the pitch
- `docs/pitch/claims.md`: every pitched number with source and caveat, and the "to verify" hypotheses; `check_numbers.py` checks it
- `docs/pitch/demo-script.md`, `faq.md`, `pilot-plan.md`: the live demo, objections, the next step
- `docs/benchmarks/summary.md`: all measured results and what is safe to claim

## Open items

- Pull request #1 (approval demo) is open; the owner should comment `/pcat approve`, confirm the check turns green, then close it without merging. The live demo depends on this step, which nobody has seen work end to end yet.
- Product gaps found in v7: `pcat lint --changed-since` does not flag a changed module constant a marked function uses (a lowered `MIN_ITERATIONS` passes the pull-request check); `pcat init` still tells users to require both checks, but `pcat-lint` stays red on confirmed proposals.
- Find a pilot team (one Python repository on GitHub, engineers using Claude Code, a pattern owner and approvers); success criteria are already fixed in `docs/pitch/pilot-plan.md`.
- `main` is not protected; `CODEOWNERS` uses the placeholder `@platform-team`. Fine while solo; set both before anyone else contributes.
- Install is from git (`pipx install "pcat[mcp] @ git+https://github.com/majhimanish/pcat"`); PyPI publishing needs the owner's account (`docs/releasing.md`).
- Untested ideas: a margin rule for inference (best pattern clearly ahead of the second); a larger rerun of the "rename the neighbour into the gap" scenario; Argon2id pattern; Pydantic class support in patterns (FastAPI endpoint deferred); languages other than Python.
