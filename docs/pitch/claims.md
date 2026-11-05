# Claims register

Every claim and every number used in `one-pager.md`, `deck.pptx` and `faq.md`, where it
comes from, and what limits it. Numbers come only from rows that
`docs/benchmarks/summary.md` marks as safe to pitch, under the rule set they were measured
with. `check_numbers.py` (next to this file) fails if those three files use a number that
is not in a **Numbers** cell below, or if a number in a cell is not in the section it cites.

What was simulated, everywhere: three open-source apps (CTFd, healthchecks, LNbits) stood
in for organizations; the builder of pcat picked and reviewed every catalog pattern (no
app maintainer did); one model (claude-sonnet-5-5 through Claude Code); small samples
(3 per task in v5 and v5.2, 20 per cell in v2.1). Costs are the Claude Code CLI's own
estimates and may reflect plan usage rather than billing.

Source format: `file` § exact section heading.

## Claims

| ID | Claim (as used) | Numbers | Source | Caveat |
|---|---|---|---|---|
| C1 | Agents rarely write the same code twice: asked for the same function 20 times, the agent wrote 15.7 effective shapes on average (17.4 when the request was paraphrased); with a reference in the prompt, 2.0 | 20; 15.7; 17.4; 2.0; 480; 8 | `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2); `docs/benchmarks/v2.1-variance.md` § Results | Pitch: yes. Lab prompts, one model, 8 tasks, 20 samples per cell (20 is the ceiling). The reference was an unreviewed model output placed in the prompt (a perfect lookup) |
| C2 | Without a catalog, none of the lab samples matched the reviewed pattern for their task | 0; 135 | `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2) | Pitch: yes, with "lab prompts" |
| C3 | Given the reviewed pattern, agents use it: the right pattern was fetched in 140/140 lab runs and 54/54 runs inside real repositories | 140/140; 54/54 | `docs/benchmarks/summary.md` § Safe claims, with caveats | v3 is lab (long prompts, tool-less agent); v5 catalogs are self-reviewed |
| C4 | Inside the repositories agents searched the catalog in 71/72 runs and forced a pattern onto unrelated work in 0/36 | 71/72; 0/36 | `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2) | Brief requests; 3 apps; one model |
| C5 | For code the repository does not have yet, the catalog decides the outcome: on the 4 tasks where the function existed nowhere else in the repo, agents with pcat reproduced the house version 12/12 times, without pcat 2/12 (similarity 0.85) | 12/12; 2/12; 12; 4; 0.85; 3 | `docs/benchmarks/summary.md` § Safe claims, with caveats; `docs/benchmarks/v5-open-source.md` § Part F: end to end inside the repos; `docs/benchmarks/summary.md` § Open issues that affect the numbers | Pitch: yes, framed this way. 4 tasks × 3 samples carry the effect; self-reviewed catalogs; one model; restricted shell |
| C6 | Where similar code already sits nearby, agents copy it with or without pcat (median similarity to the house original 1.00 in both conditions) | 1.00 | `docs/benchmarks/summary.md` § Safe claims, with caveats | This is a limit, said up front: the catalog's measured value is for code that is not already in the repo |
| C7 | Real apps, end to end: 3 apps, 144 runs, 72 per condition; new code matched the pattern 0.72 with pcat vs 0.46 without | 3; 144; 72; 0.72; 0.46 | `docs/benchmarks/v5-open-source.md` § Part F: end to end inside the repos; `docs/benchmarks/v5-open-source.md` § Setup | "Matches the pattern" is strict when a sibling differs by a field; similarity is the better consistency measure (C6) |
| C8 | Nothing high-severity ships without a human decision: in 20 of 60 lab runs the code broke a guarded property of the reviewed pattern; all 20 were flagged and each carried a hashed approval proposal (22 lines) that keeps CI red until a person confirms it; 0 went through uncovered | 20; 60; 22; 0 | `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2); `docs/benchmarks/v5-open-source.md` § Part A: the v4 feedback run under v4.1 rules | Pitch: yes, under the v4.1 rules. The requests themselves asked for the deviation (all 5 HTTP requests said "not on 4xx errors", and 429 is a 4xx). Agents write the proposals; a human must still read them |
| C9 | The HTTP guard flagged 20/20 samples that dropped retrying on 429; 25/140 lab samples would fail CI | 20/20; 429; 25/140; 5 | `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2) | Pitch: yes, with "all 5 HTTP requests asked for no 4xx retries" |
| C10 | With markers, no correct code failed CI in 144 in-repo runs (0/72 pcat runs; the earlier linter failed 5) | 144; 0/72; 5 | `docs/benchmarks/summary.md` § v5.1 — the linter on real code | Pitch: yes. 144 runs, 3 apps, self-reviewed catalogs, one model; not a general false-positive rate |
| C11 | Findings on code nobody marked are mostly wrong: of 90 sampled medium/high findings on untouched app code, 75 were false positives, 15 debatable, 0 true; so they stay advisory and out of required checks | 90; 75; 15; 0 | `docs/benchmarks/summary.md` § v5.1 — the linter on real code; `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2) | Pitch: as a limit only |
| C12 | Supporting evidence: with a flawed function planted next to the work, 3/54 agents without the catalog inherited the flaw, 0/54 with it; all 3 cases were in the 2 tasks where the flawed function was the obvious stand-in (3/6 vs 0/6); 51/54 baseline runs did not copy it | 3/54; 0/54; 3/6; 0/6; 2; 51/54; 54; 108 | `docs/benchmarks/summary.md` § v5.2 — catalog versus an unsafe neighbour; `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2); `docs/benchmarks/v5.2-unsafe-neighbour.md` § Results | Pitch: yes, with "planted by us, 6 runs carry the effect". Self-reviewed catalogs, one model. Do not claim bad neighbours are usually copied |
| C13 | With the catalog, 48/49 agents that saw the flawed neighbour used the reviewed pattern instead | 48/49 | `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2) | Same caveats as C12 |
| C14 | A copied flaw in unmarked code passes default CI (0/3 caught); the opt-in high-confidence mode catches 3/3 but also fails 2/108 correct runs and 5 of 4,031 untouched functions | 0/3; 3/3; 2/108; 5; 4,031; 0.75 | `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2); `docs/benchmarks/summary.md` § v5.2 — catalog versus an unsafe neighbour | Pitch: only as "opt-in, still noisy" |
| C15 | Real code has few exact repeats, so catalogs come from review, not mining: 3 / 6 / 8 repeated function shapes in 587 / 608 / 1,768 functions | 3; 6; 8; 587; 608; 1,768 | `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2) | Pitch: yes, with v2 (libraries barely repeat either) |
| C16 | Search on brief requests is good but uneven: right pattern ranked first 0.94 / 0.89 / 0.67 of the time across the three apps; 6/54 right answers fell below the match threshold | 0.94; 0.89; 0.67; 6/54 | `docs/benchmarks/summary.md` § pcat benchmark summary (v2 – v5.2) | Pitch: yes, with the LNbits drop (thin metadata) |
| C17 | Cost of running agents with pcat is about the same as without: median $0.10 per run with pcat vs $0.09 without; $14.59 for all 144 runs | $0.10; $0.09; $14.59; 144 | `docs/benchmarks/v5-open-source.md` § Part F: end to end inside the repos | CLI estimates, may reflect plan usage rather than billing |
| C18 | The planted-neighbour study cost $11.71 for 108 runs | $11.71; 108 | `docs/benchmarks/summary.md` § v5.2 — catalog versus an unsafe neighbour | CLI estimate |

## Product facts

Plain facts about the tool, not results. They come from the getting-started guide, which
was followed end to end once on a copy of healthchecks (`experiments/v6/dogfood/notes.md`).

| ID | Fact (as used) | Numbers | Source | Caveat |
|---|---|---|---|---|
| P1 | The getting-started guide takes about 30 minutes | 30 | `docs/getting-started.md` § Getting started with pcat (about 30 minutes) | The guide's own estimate; dogfooded once by the builder, not timed with a new user |
| P2 | `pcat init --starter` seeds 7 reviewed application patterns | 7 | `docs/getting-started.md` § 2. Set pcat up in your repository (3 minutes) | Reviewed by the builder |
| P3 | Current version | 0.1.0 | `docs/getting-started.md` § 1. Install (2 minutes) | Installs from git; not on PyPI yet |
| P4 | Python 3.11 or newer | 3.11 | `docs/getting-started.md` § Getting started with pcat (about 30 minutes) | Python code only |
| P5 | The guide budgets 10 minutes to turn one piece of your code into a reviewed pattern | 10 | `docs/getting-started.md` § 3. Make your first reviewed pattern (10 minutes) | An estimate for the mechanics; the real review time is not measured (H5) |
| P6 | The audit lists functions with similarity of 0.75 or more to a pattern that break one of its guards | 0.75 | `docs/getting-started.md` § 6. Run a one-time audit (5 minutes) | Candidates for review, not confirmed bugs |
| P7 | A 4-week pilot with one real team is the next step (weeks 1, 2, 3, 4 on the timeline) | 4; 1; 2; 3 | `docs/pitch/pilot-plan.md` § The plan | A plan, not a result |

## Not used in the pitch

- v3 "122/140 (87%) used the pattern": lab only, and in real repos the baseline is
  already consistent where siblings exist (summary.md, "Do not claim").
- v4 "0/60 shipped": relied on agent-written approvals without a hash.
- v6 audit and dogfooding numbers (audit surfaced 10 of 18 planted neighbours; 5
  candidates on untouched code; 8 friction points): `summary.md` does not cover v6, so
  they are product notes (`experiments/v6/`), not pitch evidence.
- Test pass rates (agents could not run tests in v5), anything about a human-reviewed
  catalog, and any effect across models or clients.

## To verify (hypotheses, not shown by the data)

These are the business-value claims a pitch is tempted to make. None is measured; each is
something the pilot (`pilot-plan.md`) or later work would have to show.

| ID | Hypothesis | How it could be checked |
|---|---|---|
| H1 | Reviewers spend less time re-checking common glue code (auth, tokens, retries) when it comes from a reviewed pattern | Review time and comment counts on marked vs unmarked pull requests in the pilot |
| H2 | Teams adopting coding agents see the same variance in their own code that the lab showed | Run `pcat mine` and the audit on the pilot repository before and after |
| H3 | Fixing a pattern once (a new `@v2`) fixes the code that uses it faster than finding copies by hand | Count marked uses found and updated after a pattern change |
| H4 | The catalog's protective effect grows with how tempting a bad example in the repo is | A larger rerun of the "flawed function as the obvious stand-in" scenario |
| H5 | A team can write and review a useful pattern in under an hour | Time each pattern in the pilot |
| H6 | The results hold for other models and other agents | Repeat v5 with another model or client |
| H7 | Required CI on marked code stays quiet on a real team's pull requests | False CI failures per week in the pilot |
| H8 | Security and platform teams value guards as an enforceable record of what reviewers care about | Interviews after the pilot |
| H9 | Engineering leaders at companies adopting coding agents have this problem and would pay to fix it | Conversations; no market sizing exists |
