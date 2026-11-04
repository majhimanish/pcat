# v5 — Realistic simulation on open-source applications

Work unattended. Do not stop to ask questions; when something is ambiguous, pick the simplest reasonable option, record it in `DECISIONS.md`, and continue.

## 0. Before you start

1. Read `CLAUDE.md`, `DECISIONS.md`, `KNOWN_GAPS.md`, every spec in `docs/specs/`, and everything in `docs/benchmarks/`.
2. Save this file verbatim as `docs/specs/v5-open-source-simulation.md`.
3. Run the full test matrix and `pcat validate` to confirm a green start.
4. If pull request #1 (approval demo) is still open, leave it alone.

Do not change canonicalization rules, shape fingerprints, any `impl.py` or fingerprint in `catalog/`, the search threshold, or any earlier experiment data. New catalogs for this phase live outside `catalog/` (Part C).

## 1. Goal

Everything so far ran in the lab: 7 patterns, tool-less agents, carefully worded prompts. v5 asks what happens in conditions close to real use:
- real application codebases, each treated as its own organization with its own catalog
- agents with full file and shell tools working inside the repo, where existing code competes with the catalog as a source of examples
- short requests like developers actually type
- larger catalogs with overlapping topics

It also re-measures v4's feedback result under v4.1's rules, so every headline number comes from one consistent rule set.

Build in this order, committing after each part: **A** feedback rerun → **B** pick and mine apps → **C** per-app catalogs → **D** tasks and requests → **E** retrieval eval → **F** end-to-end runs → **G** write-up, summary and handoff.

## 2. Usage and cost control

Agent runs with full tools cost much more than v3's. Before Part F:
- Run a 2-sample smoke test per condition and estimate the total from the CLI's reported cost.
- If the estimate exceeds **$60**, scale down samples per task (never below 2) until it fits, and record the scaling.
- Make every generation step resumable (skip completed samples, as in v3's `--resume`). If the usage limit is hit, wait and resume; if it stays blocked, write up what was completed and say so.
- Record CLI cost estimates and note they may reflect plan usage rather than billing.

## 3. Part A — feedback rerun under v4.1 rules

Rerun v4's feedback run (the same 60 held-out requests for `http_retry`, `csv_import`, `paginate_query`, same setup) with the current server and linter. Report per task: pattern match, unapproved high deviations, proposed approvals (with hash), and how many of those approvals would have been confirmable versus stale. Compare with v3 and with v4 re-scored under v4.1 rules. Save under `experiments/linter/feedback_v4.1/`.

## 4. Part B — pick and mine applications

Choose **3** open-source Python web **applications** (not libraries or frameworks), each:
- actively maintained, with real business logic (auth, data access, background jobs, integrations)
- 20k–300k lines of Python, permissive licence, public on GitHub
- different frameworks where possible (e.g. one FastAPI, one Django, one Flask)

Candidates to evaluate: `fastapi/full-stack-fastapi-template`, `mealie-recipes/mealie`, `CTFd/CTFd`, `healthchecks/healthchecks`, `netbox-community/netbox`. Verify each exists, pin a release tag or commit, and record why you chose it. Clone into `.bench/apps/` (gitignored).

Mine each app with `pcat mine`, excluding docs, examples, migrations and tests. Report per app: functions mined, function and fragment clusters, top clusters. Save reports under `experiments/v5/mining/`.

## 5. Part C — per-app catalogs

Each app is a separate organization. For each, build a catalog at `experiments/v5/catalogs/<app>/` (same format as `catalog/`, own `index.json`) containing:
- **8–12 house patterns** promoted from that app's own code: prefer mined clusters; where the app has a clear house way of doing something that appears only once or twice (an auth dependency, a permission check, a paginated list endpoint, a background task wrapper), it may still become a pattern. Each needs metadata, `keywords`, `use_when`, `usage`, guards where security or correctness warrants them, and tests that pass (mock the app's framework where needed; record when a test can't run outside the app).
- **The 7 reviewed application patterns** from `catalog/`, copied in unchanged, so topics overlap (e.g. the app's own pagination versus the generic one).

Patterns may use classes only if the current tooling already supports them; otherwise skip that candidate and record it.

These catalogs are **reviewed by you, not the owner**. Write `experiments/v5/catalogs/<app>/REVIEW.md` stating what was reviewed and how, and treat that as a limitation in the write-up.

## 6. Part D — tasks and requests

Tasks come from real code, so success can be compared with what the app's own developers wrote.

For each app, choose **8 tasks**:
- **6 pattern tasks:** each is a real function in the app that a catalog pattern covers. Remove that function (and its now-unused helpers) from the working copy used for the run, and record the original as the reference.
- **2 negative tasks:** real functions no catalog pattern covers, removed the same way.

Write a one-sentence description of each task's need. Then, as in v3, generate requests with fresh `claude -p` processes given only the description and asked to phrase it **briefly, the way a developer types into an assistant (usually under 15 words)**. One request per task. Commit descriptions and requests before any run uses them.

## 7. Part E — retrieval with larger, overlapping catalogs

For each app's catalog, evaluate search on that app's requests and on 20 extra brief requests per app generated the same way (pattern and negative needs mixed). Report top-1, top-3 and false-match rate, and specifically: when an app's house pattern and a generic pattern cover the same topic, which ranks first. Do not change the search threshold; report how it behaves. If short queries fall below the threshold, quantify it.

## 8. Part F — end-to-end inside the repos

Each run: a fresh copy of the app at the pinned commit with the task's function removed, `claude -p` started in that copy, **full tools allowed** (read, search, edit, write, shell), extra user/global CLAUDE.md disabled, a per-run time limit (10 minutes), and the request as the prompt. Capture the final `git diff`, the transcript summary, the pcat tool-call log, cost and duration.

Two conditions:
- **Baseline:** no pcat server.
- **pcat:** the app's catalog served by `pcat serve`, and one line added to the repo's `CLAUDE.md` (create it if absent): "This repo uses the organization's pattern catalog via the pcat tools."

Default 3 samples per task per condition (3 apps × 8 tasks × 3 × 2 = 144 runs), subject to section 2.

Metrics per app and condition:
- **Search rate:** runs that called `search_patterns`; for pcat runs, also how often the agent read existing repo code instead of or before searching
- **Pattern use:** runs that fetched the right pattern; runs whose new code matches it (shape) or derives from it (marker or inference)
- **Linter outcome:** `pcat lint` on the diff with the app's catalog: deviations by severity, and runs that would fail CI. Run the linter on baseline diffs too.
- **House consistency:** similarity of the new function to the removed original (v2.1 measure)
- **Negatives:** runs that forced a pattern onto unrelated work
- **Effort:** cost, duration, files touched
- Optionally, if the app's test suite can be run quickly in the copy, whether its relevant tests pass; skip and record when it can't.

## 9. Part G — write-up, summary and handoff

- `docs/benchmarks/v5-open-source.md`: setup and limitations (self-reviewed catalogs, small samples, open-source code), Part A results, mining summary, retrieval results, end-to-end tables per app and condition, the main ways the catalog was ignored or misused (with examples), and an honest assessment separating what the data shows from what it suggests.
- `docs/benchmarks/summary.md`: one page with every headline number from v2 to v5, each stated under the rule set it was measured with, and which numbers are safe to use in a pitch and with what caveats.
- Update `CLAUDE.md` (at or under 150 lines), `DECISIONS.md`, `KNOWN_GAPS.md` and the README.
- Commit after each part, push to `main`, finish with a clean working tree.

## 10. Tests

New code (task extraction, function removal, run harness, scoring) gets tests on small fixtures; no live `claude -p` calls in tests. Everything passes in all extras combinations.

## 11. Acceptance criteria

- Full test matrix passes on Python 3.11 and 3.13; `pcat validate` passes for `catalog/` and every v5 catalog; CI passes on `main`
- Git history shows requests committed before any run used them
- Part A, retrieval and end-to-end results exist with real numbers, or the write-up explains exactly what was cut and why
- `docs/benchmarks/summary.md` exists
- No `impl.py` or fingerprint in `catalog/`, search threshold or earlier experiment file changed

## 12. Final message

Part A numbers, apps chosen, retrieval headline, baseline versus pcat end-to-end headline per app, the biggest surprise, total cost estimate, and what you'd do next.
