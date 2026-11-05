# v7 — Pitch material

Work unattended. Do not stop to ask questions; when something is ambiguous, pick the simplest reasonable option, record it in `DECISIONS.md`, and continue.

## 0. Before you start

1. This spec runs after v6 in the same session. If v6 isn't finished and pushed, finish it first.
2. Read `PROJECT_BRIEF.md`, `docs/benchmarks/summary.md`, every file in `docs/benchmarks/`, `docs/getting-started.md`, `KNOWN_GAPS.md` and the README.

No code changes in this phase except what's needed to build the deck file. Do not change any experiment data or benchmark write-up.

## 1. Goal

Turn the project's evidence into material the owner can use to pitch pcat to engineering leaders (heads of engineering, platform and developer-experience teams, security leads) at companies adopting AI coding agents. Honesty is the selling point: every number is real, sourced and caveated.

## 2. Rules for every claim

- Use only numbers that `docs/benchmarks/summary.md` marks as safe to pitch, stated under the rule set they were measured with, with their caveat.
- Every number in the deck and one-pager appears in `docs/pitch/claims.md` with its source file and section.
- No invented customers, quotes, market sizes or savings figures. Anything about the market or business value that the data doesn't show is phrased as a hypothesis and listed in `claims.md` under "to verify".
- Say plainly what was simulated: open-source apps as stand-in organizations, catalogs reviewed by the builder, one model, small samples.

## 3. Deliverables (all under `docs/pitch/`, committed)

**`one-pager.md`**: one page: the problem, what pcat does, three headline results with caveats, how a team tries it (`pcat init`), and what's not proven yet.

**`deck.pptx`** plus a PDF export if a converter is available: 10–12 slides, readable on a phone. Suggested flow:
1. Title and one-line promise
2. The problem: same request, different code (v2.1 variance)
3. Why it matters: reviews, consistency, flaws that spread
4. What pcat is: catalog, MCP server, linter (simple diagram)
5. How it works in a pull request: marker, guard, deviation, human approval
6. Result: first-time code in real apps (v5)
7. Result: silent regressions caught and turned into decisions (v4–v5.1)
8. Result: catalog over a flawed neighbour (v5.2, as supporting evidence only, with its small-sample caveat)
9. What it is not (not a style guide, not a code generator, not proven at scale)
10. How to try it: `pcat init`, 30-minute guide, audit
11. What's next: pilot with a real team, and what the pilot would measure
12. Appendix: method and caveats

Use simple, consistent styling; charts made from the real numbers; no stock photos or logos. Speaker notes on every slide in plain English.

**`demo-script.md`**: a 5-minute live demo on a sample repo: `pcat init`, an agent fetching a pattern, a deviation flagged on a pull request, a `/pcat approve` confirmation, and an audit finding. Exact commands, what to say, what to do if something fails.

**`faq.md`**: honest answers to likely objections, including: why not a shared library; how this differs from rules files or skills; who writes and reviews patterns and how long it takes; what if agents ignore the catalog; false positives in CI; languages other than Python; cost; why the samples are small; what happens when a pattern is wrong.

**`claims.md`**: every claim, its number, source, caveat, and a "to verify" list.

**`pilot-plan.md`**: a 4-week pilot with a real team: setup, which metrics to collect (from the benchmarks, adapted to real pull requests), success criteria decided in advance, and what the team must provide.

## 4. Checks

- Every number in `one-pager.md`, `deck.pptx` and `faq.md` matches `claims.md`, and every `claims.md` entry matches its source. Write a small script that extracts numbers from the Markdown files and the deck text and reports any not listed in `claims.md`; it must report none.
- Render the deck to images (or PDF) and look at every slide: nothing overflows, text is readable at phone size.

## 5. Handoff

- Update `PROJECT_BRIEF.md`: **Status** (v7 done; what's next is a real pilot), phase history rows for v6 and v7, **Open items**, and a short "Where things are" list pointing to the pitch files and the getting-started guide.
- Update `CLAUDE.md` (at or under 150 lines), `DECISIONS.md`, README (link to `docs/pitch/`).
- Commit, push to `main`, clean tree.

## 6. Final message

For v6: what was built, audit results on the three apps and planted neighbours, dogfooding friction found and fixed, install command. For v7: the list of pitch files, the three headline claims exactly as worded in the one-pager, and anything you couldn't verify. End with what the owner should do next.
