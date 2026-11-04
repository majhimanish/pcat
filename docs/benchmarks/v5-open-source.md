# v5 benchmark: open-source applications, brief requests, agents in the repo

Everything before v5 ran in the lab: 7 patterns, tool-less agents, long carefully
worded prompts. v5 moves closer to real use: three real web applications, each
treated as its own organization with its own catalog; agents working *inside* the
repository, where existing code competes with the catalog as a source of examples;
short requests; larger catalogs with overlapping topics. It also re-measures v4's
feedback result under the v4.1 rules, so the headline numbers share one rule set.

Spec: `docs/specs/v5-open-source-simulation.md`. Data: `experiments/v5/` and
`experiments/linter/feedback_v4.1/`. Reproduce with `scripts/v5.py`
(`clone`, `mine`, `references`, `requests`, `retrieval`), `scripts/v5_e2e.py`
(`run`, `analyze`) and `scripts/lint_eval.py feedback|feedback-analyze --dir feedback_v4.1`.

## Setup

- **Apps** (pinned; `experiments/v5/apps.yaml`): **CTFd 3.8.9** (Flask, Apache-2.0,
  47k lines of Python), **healthchecks v5.0.3** (Django, BSD-3, 45k), **LNbits v1.6.2**
  (FastAPI, MIT, 85k). Rejected: the FastAPI template (3k lines), mealie (AGPL),
  netbox (420k lines, class-based throughout), Netflix/dispatch (no commit since
  2025-09) and polar (659k lines).
- **Catalogs** (`experiments/v5/catalogs/<app>/`): 9, 9 and 8 *house* patterns promoted
  from each app's own code (mined clusters where they exist, single house idioms
  otherwise), plus the 7 reviewed generic patterns copied unchanged: 16, 16 and 15
  patterns, with overlapping topics (CTFd's rate limiter vs the token bucket, LNbits'
  `create_access_token` vs the generic JWT, two email senders in healthchecks).
- **Tasks** (`experiments/v5/tasks.yaml`): per app, 6 real functions a pattern covers
  and 2 no pattern covers, removed from a fresh copy (the original is the reference).
  Of the 18 pattern tasks, 14 are **sibling** tasks (the pattern was promoted from
  another occurrence that stays in the repo) and 4 are **same** tasks (the removed
  function *is* the pattern's only occurrence).
- **Requests** (`experiments/v5/requests.json`): one per task and 20 extra per app,
  written by fresh no-tools `claude -p` from a one-sentence need, asked to be brief
  ("usually under 15 words"): median 15 words, max 23, 38 of 84 over 15. They invent
  names and locations as people do (`authorize_write`, `send_verify_link`, a view
  "in hc/front/views.py").
- **End to end** (`scripts/v5_e2e.py`): 3 apps × 8 tasks × 3 samples × 2 conditions =
  **144 runs**, claude-sonnet-5-5, each in a fresh copy (outside this repo, opaque
  path) with the task's function removed, project settings only, 10-minute limit.
  *Baseline*: no pcat. *pcat*: the app's catalog over MCP and the one-line note in
  `CLAUDE.md`. Captured: diff, transcript, pcat tool log, cost, duration.

### Limitations

- **The shell was restricted.** The spec asked for full tools. This environment
  refused to start unattended agents with unrestricted shell access, so runs had the
  file tools in full (read, search, edit, write) but the shell only for read-only
  commands (`git diff/log/grep/show`, `ls`, `head`, `wc`, `py_compile`). Agents
  could not run the apps' tests (one said so: "the shell asked for approval on my
  test commands"), so the optional test-pass metric was skipped.
- **Self-reviewed catalogs.** I picked, extracted and reviewed every house pattern
  (`REVIEW.md` per app); no app maintainer or owner did. Pattern tests stub
  Django/Flask/FastAPI and the apps.
- **Small samples.** 3 samples per task per condition; 4 same-function tasks.
- **Open-source code**, not a company codebase: house patterns are what these apps
  happen to do, sometimes with weaknesses kept verbatim (a non-constant-time badge
  signature compare; a JWT without `iss`/`aud`).
- **Sibling code makes "pattern match" strict.** A sibling often differs from the
  pattern by a field (`team.score` vs `team.place`, `KeyType.invoice` vs `admin`), so
  its correct reimplementation cannot have the pattern's shape. Similarity to the
  removed original is the better house-consistency measure.
- **No filesystem sandbox.** The originals exist on disk; every transcript was
  scanned for paths outside the copy: **0 runs** touched them.
- **Cost** is the CLI's estimate and may reflect plan usage rather than billing. The
  first pass hit the 5-hour usage limit after 52 runs; the rest were rerun after the
  reset (DECISIONS 201).

## Part A: the v4 feedback run under v4.1 rules

The same 60 held-out requests and setup as v4, with the current server; v3 and v4
samples re-scored under the v4.1 rules (a proposal approves nothing until a human
confirms it; approvals need the function's hash; `RETRY_STATUSES` must include 429).

| Task | Pattern match v3 / v4 / v4.1 | High unapproved v3 / v4 / v4.1 | High not covered by a proposal (v4.1) | Approval lines in final code |
|---|---|---|---|---|
| `http_retry` | 0.70 / 0.75 / **0.80** | 20/20 / 20/20 / 20/20 | **0/20** | v4: 9, all stale (no hash); v4.1: **22, all confirmable** |
| `csv_import` | 0.50 / 0.60 / **0.60** | 5/20 / 1/20 / **0/20** | 0/20 | v4: 2 stale; v4.1: 0 |
| `paginate_query` | 0.90 / 1.00 / **1.00** | 0 / 0 / 0 | 0/20 | none |

- Under one rule set, v4's "0/60 unapproved high" becomes **21/60** (v3: 25/60): v4's
  approvals carry no hash, so they are stale, and every HTTP sample drops 429.
- In the v4.1 rerun every one of those 20 is covered by a correctly hashed proposal
  (22 lines; 2 samples also propose the connection-error narrowing), and nothing high
  ships uncovered. They still fail CI until a human confirms.
- **Correction to earlier write-ups:** all five HTTP requests say "not on 4xx
  errors", and 429 is a 4xx. Dropping it is what the request literally asked for, not
  an agent misreading. The guard turns a real conflict between the reviewed pattern
  and the request into a human decision, which is the intended outcome.
- CLI cost estimate: $3.96.

## Part B: mining

`experiments/v5/mining/summary.md` (tests, migrations, docs, examples excluded):

| App | Functions found / mined | Function clusters | Fragment clusters | Largest clusters |
|---|---|---|---|---|
| CTFd | 806 / 587 | 3 | 8 | import-status setters (4), form `__init__`s (3) |
| healthchecks | 767 / 608 | 6 | 8 | email senders (5), integration `add` views (4), `TokenBucket.authorize_*` (4) |
| LNbits | 2,186 / 1,768 | 8 | 7 | provider `cleanup` methods (18), `paid_invoices_stream` (4+4) |

As in v2, application code barely repeats: a handful of clusters per app, half of
them methods (which patterns cannot contain). Most house patterns are "a house way
that appears once or twice", not mined clusters.

## Part E: retrieval with larger, overlapping catalogs

Brief requests against each app's own catalog, unchanged threshold (9.08):

| App | Positives / negatives | Top-1 (≥ threshold) | Top-3 | Top-1 ignoring threshold | False matches |
|---|---|---|---|---|---|
| CTFd | 18 / 10 | **0.94** | 0.94 | 1.00 | 2/10 |
| healthchecks | 18 / 10 | **0.89** | 0.89 | 0.94 | 0/10 |
| LNbits | 18 / 10 | **0.67** | 0.67 | 0.89 | 1/10 |

- **Short queries fall below the threshold:** 6 of 54 positives rank the right
  pattern first but score under 9.08 (CTFd 1, healthchecks 1, LNbits 4), e.g. "Clear
  the extension's stored settings when it's uninstalled." (7.45) and "Add a total
  wallets count card to the admin dashboard." (8.55). Most LNbits house patterns have
  short, generic metadata (CRUD helpers), which brief requests barely overlap.
- **House vs generic:** a house and a generic pattern both passed the threshold in 3
  requests, and the expected one ranked first in all 3: CTFd's `decorators.ratelimit`
  (24.5) over the token bucket (12.0) for "rate-limit decorator for POST requests per
  client IP"; LNbits' JWT (17.6) over the generic JWT (15.5); the token bucket over
  LNbits' API-key dependency for per-key invoice limits.
- **False matches** are vocabulary collisions: "first-blood bonus points" and "solve
  counts per category" both hit CTFd's challenge-decay pattern (14.4, 11.4).

## Part F: end to end inside the repos

| App | Condition | Search rate | Fetched the right pattern | New code matches the pattern | Derives from it (marker or inference) | Median similarity to the original | Would fail CI | Median cost |
|---|---|---|---|---|---|---|---|---|
| CTFd | baseline | 0 | 0 | 0.67 | 1.00 | 1.00 | 0/24 | $0.08 |
| CTFd | pcat | 1.00 | 1.00 | **0.83** | 1.00 | 1.00 | 2/24 | $0.10 |
| healthchecks | baseline | 0 | 0 | 0.33 | 1.00 | 1.00 | 0/24 | $0.09 |
| healthchecks | pcat | 1.00 | 1.00 | **0.67** | 1.00 | 1.00 | 0/24 | $0.10 |
| LNbits | baseline | 0 | 0 | 0.39 | 0.89 | 0.99 | 0/24 | $0.11 |
| LNbits | pcat | 0.96 | 1.00 | **0.67** | 1.00 | 1.00 | 3/24 | $0.11 |
| **All** | baseline | 0 | 0 | 0.46 | 0.96 | 1.00 | 0/72 | $0.09 |
| **All** | pcat | 0.99 | 1.00 | **0.72** | 1.00 | 1.00 | 5/72 | $0.10 |

Match, derivation and similarity are over the 54 pattern-task runs per condition;
search and CI over all 72. All 144 runs finished (no timeouts), median 31 s (baseline)
and 34 s (pcat), one file touched. CLI cost estimate **$14.59** for the 144
completed runs (about $15.84 with the attempts cut off by the usage limit).

**By task type:**

| Tasks | Condition | Matches the pattern | Median similarity to the original |
|---|---|---|---|
| sibling (14 tasks, 42 runs) | baseline | 0.55 | **1.00** |
| sibling | pcat | 0.64 | 1.00 |
| same (4 tasks, 12 runs) | baseline | 0.17 | 0.85 |
| same | pcat | **1.00** | **1.00** |

- **Where sibling code exists, the repo already does the catalog's job.** Baseline
  agents read the neighbouring function and reproduce the house shape (median
  similarity 1.00 without pcat). pcat adds little there (0.55 → 0.64 match).
- **Where the code exists nowhere else, the catalog decides the outcome.** On the
  four same-function tasks, pcat reproduces the house function every time (12/12);
  the baseline writes its own version (2/12 match, similarity 0.85). Examples: CTFd's
  rate limiter (baseline similarity 0.73: a reasonable cache-counter decorator, but
  not CTFd's), healthchecks' post-login redirect check (0.71).
- **Negatives:** 0 of 36 runs forced a pattern onto unrelated work (fetched one and
  marked or matched it). Inference flagged 11 negative runs as "similar" (small regex
  and version helpers vs `regex_match`/`parse_bool`, scores 0.57–0.66), advisory only.
- **Agents read code first:** in half the pcat runs (51%) the agent read or searched
  the repo before calling `search_patterns` (LNbits 74%, CTFd 29%); one LNbits
  negative run never searched.

### How the catalog was ignored or misused

- **Ignored in favour of the sibling.** On `hc_api_authorize`, pcat agents fetched
  `api.authorize_read` but wrote `authorize` from the neighbouring code in
  `hc/api/decorators.py` (similarity 0.90, the same as baseline): reasonable, since
  the request was about the write variant.
- **A false CI failure on correct code** (3 runs). For `lnbits_invoice_key` the agent
  wrote exactly the original function from the pattern, but `pcat lint` failed it:
  the guard `must_call lnbits.decorators.KeyChecker` cannot match because `KeyChecker`
  is a class defined *in the same module*, which the linter does not resolve to its
  module path. A tooling bug, now in KNOWN_GAPS.
- **The gate working as designed** (2 runs). On `ctfd_reset_token` the agent raised
  `UserResetPasswordTokenInvalidException` (the type `CTFd/auth.py` catches), not the
  pattern's confirm-token exception, and proposed hashed approvals ("reset flow must
  raise UserResetPasswordTokenInvalidException; CTFd/auth.py catches that type"). CI
  stays red until a human confirms. My `must_raise` guard was over-specific for a
  sibling use.
- **`check_code` on a fragment.** One agent passed `check_code` only the function, so
  the module's imports were missing and it reported a high PC103 ("library swapped").
  The agent correctly reasoned it away, but a less careful one would "fix" it.

## Assessment

**What the data shows**
- With full file tools in a real repo, agents already copy the house way when a
  sibling exists: baseline median similarity to the removed original is 1.00 on
  sibling tasks. The catalog's measurable effect is concentrated where the code is
  *not* in the repo: 12/12 vs 2/12 on same-function tasks.
- Agents with the server search (71/72) and fetch the right pattern (54/54), even
  with brief requests and 15–16-pattern catalogs, and do not force patterns onto
  unrelated work (0/36).
- Retrieval holds with overlapping catalogs (the expected pattern ranked first in all
  3 house/generic overlaps) but degrades with brief requests on thin metadata (LNbits
  0.67 top-1; 6/54 positives below the threshold).
- Under one rule set, v4's "unapproved high 0/60" is 21/60 (v3: 25/60). In the v4.1
  rerun 20/60 have one, and every one is a correctly hashed proposal waiting for a human.

**What it suggests (not shown)**
- The pitch shifts from "agents write inconsistent code" to "agents copy whatever is
  nearby". The catalog's value is for code that is new to the repo, or where the
  nearby code is not the approved version. A study that plants an *outdated* sibling
  (or a deprecated pattern use) next to the gap would test the second case directly.
- Guards and linting need to understand the app's module structure before they can
  gate real repositories: the same-module class bug failed 3 correct runs.
- Search in apps needs richer house metadata (synonyms, the app's own vocabulary) or
  a below-threshold "weak match" band; brief requests are the norm.

**Two most valuable next steps**
1. **Fix the linter for real codebases**: resolve same-module names (classes,
   functions) to their module path for guards, run `check_code` on whole files (with
   imports), and check `requires` against imports. Then re-score the 144 runs (no new
   generation) to see how many CI failures remain.
2. **Test the case where the nearby code is wrong**: plant a sibling that differs from
   the reviewed pattern in a guarded way (an old, less safe version) and measure whether
   agents follow the catalog or the neighbour, with and without pcat.
