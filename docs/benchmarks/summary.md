# pcat benchmark summary (v2 – v5.2)

Every headline number, the rule set it was measured under, and whether it is safe to
use in a pitch. "Rule set" = canonicalization v2 / shape v1 throughout; linter rules
v4 (PC100–PC110) or v4.1 (hashed approvals, proposals need a human, PC111,
`must_include` 429, graded PC103) or v5.1 (one symbol table per unit, partial code, check 12, `match: any`, graded PC102). Models: claude-sonnet-5-5 via `claude -p`. Costs
are the CLI's estimates and may reflect plan usage rather than billing.

| Phase | Headline | Measured under | Pitch? |
|---|---|---|---|
| v2 mining | Libraries barely repeat: requests + Flask + FastAPI, 1,215 functions, 55 clusters, **all** from FastAPI's tutorial docs; 0 across repos | miner v2 | Yes, as "real code has few exact repeats" |
| v5 mining | Apps barely repeat either: 3 / 6 / 8 function clusters in 587 / 608 / 1,768 functions (CTFd, healthchecks, LNbits) | miner v2 | Yes, with v2: catalogs come from review, not from mining |
| v2.1 variance | Same prompt, 20 samples: **15.7** effective shapes on average; paraphrased: 17.4; with a reference in the prompt: **2.0** (480 samples, 8 tasks) | shape v1 | Yes: "an agent writes a different version almost every time; a reference collapses it" |
| v2.2 coverage | **0 of 135** catalog-free samples matched the reviewed pattern for their task | canonical v2 | Yes, with "lab prompts" |
| v3 retrieval | Top-1 **35/35** dev and **35/35** held-out; false matches 0/10 dev, **2/15** held-out | BM25, threshold 9.08 | Yes for 7 distinct patterns and long requests only |
| v3 end to end | Searched 160/160, right pattern fetched **140/140**, pattern in the code **122/140 (87%)** vs 0/135 without | v3 metrics, tool-less agent | Indicative only (not controlled; long prompts; MCP tools only) |
| v4 replay | Exact matches flagged above low **0/122**; misses flagged **18/18** | linter v4 | Superseded by v4.1; do not quote alone |
| v4 feedback | Unapproved high deviations shipped 12/60 → **0/60** | linter v4 | **No**: under v4.1 rules the same samples are 21/60 (approvals had no hash) |
| v4.1 replay | 20/20 HTTP samples flagged for dropping 429; 25/140 would fail CI [v5.1 re-score: unchanged, 25/140] | linter v4.1 | Yes, with "all 5 HTTP requests asked for no 4xx retries" |
| v5 Part A | v4 feedback rerun: high unapproved v3 / v4 / v4.1 = **25 / 21 / 20 of 60**; in v4.1 all 20 covered by correctly hashed proposals (22 lines), 0 uncovered [v5.1 re-score: unchanged, 25 / 21 / 20] | linter v4.1 | Yes: "nothing high ships without a human decision" |
| v5 retrieval | Brief requests, 15–16-pattern catalogs: top-1 **0.94 / 0.89 / 0.67**; 6/54 right-but-below-threshold; expected pattern first in 3/3 house-vs-generic overlaps | BM25, threshold 9.08 | Yes, with the LNbits drop |
| v5 end to end | Inside real repos: search 71/72, right pattern 54/54, matches pattern **0.72 vs 0.46** baseline; similarity to the house original **1.00 in both**; same-function tasks **12/12 vs 2/12**; negatives forced 0/36; $14.59 for 144 runs; pcat runs that would fail CI 5/72 **[v5.1 re-score: 0/72]** | linter v4.1, restricted shell | Yes, framed correctly (below) |
| v5.1 re-score | v5 runs that would fail CI 5/72 → **0/72** (3 exact LNbits reproductions, 2 safe CTFd siblings); high deviations pcat 16 → 7, baseline 16 → 9, all left advisory; lab data unchanged | linter v5.1 | Yes: "no correct code failed CI in 144 in-repo runs" |
| v5.1 survey | Untouched app code, inferred findings: 0 true deviations, 15 debatable, 75 false positives in 90 sampled medium/high findings | linter v5.1 | Yes, as a caveat: inferred findings are advisory noise |
| v5.2 neighbour | A flawed sibling planted next to the work: flaw inherited **3/54 baseline vs 0/54 pcat** (all 3 in the 2 tasks where the neighbour could be renamed into the missing function: 3/6 vs 0/6); 0/66 in v5 without the neighbour; 48/49 pcat runs that saw it used the pattern | linter v5.1, restricted shell | Yes, with "planted by us, 6 runs carry the effect" |
| v5.2 CI | Default CI caught **0/3** inherited flaws (unmarked); opt-in `--fail-on-inferred-guards` (similarity >= 0.75, held-out P 0.962 / R 0.884) catches 3/3 but also fails 2/108 correct runs and 5/4,031 untouched functions | linter v5.2 | Only as "opt-in, still noisy" |

## Safe claims, with caveats

- **"Agents rarely write the same code twice"** (v2.1): 15.7/20 effective shapes. Lab
  prompts, one model, 8 tasks.
- **"Given the reviewed pattern, agents use it"** (v3, v5): 140/140 and 54/54 fetched
  the right one; brief requests in real repos still worked. Self-reviewed catalogs in v5.
- **"The gate makes deviations a human decision"** (v4.1, v5 A): under one rule set,
  0 high deviations ship uncovered; all are hashed proposals. Agents write the
  proposals; a human must still read them.
- **"Inside a repo, agents copy what is nearby"** (v5): with a sibling present, the
  baseline already matches the house original (similarity 1.00). The catalog's
  measured value is for code that is **not** in the repo (12/12 vs 2/12).

## Do not claim

- That pcat makes code "87% consistent" in real use: v3's number is lab-only, and in
  real repos the baseline is already consistent where siblings exist.
- v4's "0/60 shipped": it relied on hash-less, agent-written approvals.
- Anything about a human-reviewed v5 catalog, or about test pass rates (agents could
  not run tests in v5).
- Effects across models or clients: everything used one model through Claude Code.

## Open issues that affect the numbers

- `pcat lint` does not resolve same-module classes in guards (3 false CI failures in v5).
  **Fixed in v5.1** (re-scored: 0 false failures).
- Brief requests on thin metadata fall below the search threshold (LNbits).
- 3 samples per task in v5; 4 same-function tasks carry the main effect.

## v5.1 — the linter on real code

Details: `docs/benchmarks/v5.1-linter.md`. Nothing new was generated; v5's runs, the
v4 / v4.1 feedback runs and the v3 samples were re-scored, and untouched app code linted.

- **Safe:** "with markers, the linter failed no correct code in 144 in-repo runs" (0/72
  pcat runs fail CI; v5 had 5 false or over-strict failures, each explained). Lab
  headlines (v4.1 replay 25/140, v5 Part A 25 / 21 / 20 of 60) are unchanged.
- **Safe, as a limit:** inferred findings on code nobody marked are mostly wrong (75 of
  90 sampled medium/high findings were false positives, 0 true): keep `--include-inferred`
  out of required checks.
- **Do not claim** a general false-positive rate for marked code: 144 runs, 3 apps,
  self-reviewed catalogs, one model.

## v5.2 — catalog versus an unsafe neighbour

Details: `docs/benchmarks/v5.2-unsafe-neighbour.md`. 108 runs, $11.71 (CLI estimate).

- **Safe:** "with the catalog, no agent inherited a planted flaw (0/54); without it, 3/54
  did" — with the caveats that we wrote the flawed code, catalogs are self-reviewed, one
  model, and the effect sits in 2 tasks (3/6 vs 0/6) where the neighbour was the obvious
  stand-in for the missing function.
- **Safe:** "a copied flaw in unmarked code passes default CI" (0/3 caught; all three were
  flagged only as advisory).
- **Safe, as a limit:** the opt-in high-confidence mode catches copied flaws (3/3) but is
  not quiet: 2 false failures in 108 runs and 5 in 4,031 untouched app functions.
- **Do not claim** that bad neighbours are usually copied: 51/54 baseline runs did not;
  or a codebase-level precision for inference from the 0.962 (the labeled set is 57%
  derived; on real CI failures 3 of 10 were real).

