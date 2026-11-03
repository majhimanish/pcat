# v4 benchmark: making deviations visible

v3 showed that agents connected to `pcat serve` find the right pattern every
time, but 18 of 140 then changed it, and `check_code` could only say `none`. One
change was a silent regression: HTTP retries narrowed to timeouts. v4 adds
provenance markers, reviewed **guards**, an explainable **deviation analysis**
(`PC100`–`PC110`), `pcat lint` with approvals, and a `check_code` that returns
deviations. This page measures it.

Data: `experiments/linter/` (`inference_calibration.json`, `replay.json`,
`feedback/<task>/sample_NN.{json,log.jsonl}`, `feedback_results.json`).
Reproduce with `scripts/lint_eval.py calibrate | replay | feedback | feedback-analyze`.
Spec: `docs/specs/v4-linter.md`.

## Setup

- **Catalog:** the same 13 patterns as v3 (no `impl.py` or fingerprint changed).
  32 guards on the 7 application patterns, written from the v2.2 security notes
  and the patterns' code, committed (`e90aaa3`) before any Part F run: 7
  `must_raise`, 7 `must_call`, 6 `must_not_call`, 5 `max_value`, 3 `must_catch`,
  3 `min_value`, 1 `must_not_import`. Every guard holds on its own pattern
  (validation check 11).
- **Replay (no generation):** every v3 end-to-end sample (140 positive, plus the 2
  negatives that fetched a pattern), linted against the pattern its tool log shows
  it fetched, using `check_code(code, pattern_id)` (the same analysis as
  `pcat lint`). The v3 samples have no markers, so the pattern id stands in for one.
- **Inference check:** the calibration set of Part A (200 derived functions from
  v3 positives, 187 not derived from v2.1 FastAPI A/B and v3 negative samples).
- **Feedback run:** the three tasks with v3 misses (`http_retry`, `csv_import`,
  `paginate_query`), 20 samples each, **the same held-out requests, prompt and
  `claude -p` setup as v3** (claude-sonnet-5-5, one fresh process per sample, only
  the three pcat tools), against the v4 server: markers in `get_pattern`,
  deviations in `check_code`, and instructions to fix high-severity deviations
  unless the request requires them (then add `# pcat-allow` with a reason).
  60/60 completed.

### Limitations

- **The replay is not blind.** The guards were written before Part F, but the v3
  write-up already described the misses, and I looked at three v3 miss samples
  while developing the analyzer (decisions 149, 151). The 122 exact matches were
  not used for development.
- **Agents wrote the approvals.** The spec's intent is that a *human* approves a
  deviation. In the feedback run the agent added `# pcat-allow` lines itself, as
  the server instructions allow; a reviewer still has to accept them on the pull
  request. The linter makes them visible; it cannot judge whether a reason is good.
- **One model, small numbers, three tasks.** 60 new samples; differences of one
  or two samples are noise.
- **Severity is rule-based.** A real regression without a guard (dropping 429
  from the retry statuses) is only `PC109` low; a harmless rewrite of plumbing can
  be high (`PC103` for `io` → `openpyxl`, below).
- **Cost** is the CLI's `total_cost_usd`, an estimate that may reflect plan usage
  rather than billing.

## Replay on the v3 samples

| v3 outcome | Samples | No deviation | Worst low | Worst medium | Worst high |
|---|---|---|---|---|---|
| Exact match (pattern unchanged) | 122 | 108 | 14 | **0** | **0** |
| Fetched, then changed | 18 | **0** | 0 | 6 | 12 |

Against the spec's expectations:

| Expectation | Result |
|---|---|
| Exact matches report nothing but `PC109` | **122/122** (14 have `PC109` only) |
| Every miss gets at least one deviation | **18/18** |
| The 6 HTTP-retry misses get `PC100`/`PC101` high | **6/6** (`PC100`, guard `must_catch`) |
| The 2 pagination misses get `PC106` | **1/2**, see below |
| CSV misses that switched library get `PC103` | **4/4** (the pandas rewrites) |

Would fail CI (`--fail-on high`, marked code): 12 of 140 samples, all misses.

**Surprising results**
- **All 20 HTTP samples dropped `429`** from `RETRY_STATUSES`, including the 14
  that v3 counted as exact matches (the v3 match looked at the entry function's
  fingerprint, where constants are free names). The requests say "timeouts or 5xx",
  and the agent read that as "not 429". Rate-limited responses are no longer
  retried. It is reported only as `PC109` low because no guard covers the
  constant: a real behaviour change that the severity model misses.
- **Pagination sample 17 is `PC107`, not `PC106`.** It never touched a private
  attribute; it adds an unrequested `tiebreaker` parameter. My v3 write-up said
  both pagination misses read `_order_by_clauses`; only sample 12 does (erratum
  added to `docs/benchmarks/v3-mcp.md`). Sample 12 gets `PC106` medium.
- **The 6 non-pandas CSV misses** kept the `csv` module but wrapped `openpyxl`
  readers around it. Four are medium (two add `except Exception`, `PC104`). Two
  are high: sample 12 replaced `csv.DictReader` with `csv.reader` (`PC100`), and
  sample 2 gets `PC103` "replaced `io` with `openpyxl`". That one is arguably a
  false high: `io` is plumbing, not a library choice.
- The two negative samples that used `auth.password.pbkdf2` inside a FastAPI
  sign-up endpoint report no deviations (they used it unchanged).

## Inference

On the calibration data (threshold 0.56, chosen on the same data, so this is a
fit, not a test):

| Set | Functions | Inferred correctly | Wrong |
|---|---|---|---|
| v3 derived (positives) | 200 | 199 inferred as derived, from the right pattern function | 1 missed (a CSV rewrite, 0.54) |
| v2.1 FastAPI A/B (not derived) | 125 | 124 not derived | 1 inferred as derived: a hand-rolled PBKDF2 `hash_password` (0.58) |
| v3 negatives (not derived) | 62 | 62 not derived | 0 |

The margin is narrow: the lowest derived function scores 0.54 and the highest
non-derived 0.58. Small validator functions reach 0.56 against `parse_bool`
(0.5556, just under). That is acceptable only because inferred findings are
advisory.

## Feedback run: v4 server vs v3

| Task | Pattern match v3 → v4 | High deviations shipped unapproved v3 → v4 | Samples with an approved deviation | `check_code` with pattern id | Cost (v4) |
|---|---|---|---|---|---|
| `http_retry` | 0.70 → **0.75** | 6/20 → **0/20** | 8/20 | 20/20 | $1.17 |
| `csv_import` | 0.50 → **0.60** | 6/20 → **0/20** | 2/20 | 20/20 | $1.65 |
| `paginate_query` | 0.90 → **1.00** | 0/20 → 0/20 | 0/20 | 11/20 | $0.89 |

(v3 high counts come from the replay above. Total CLI cost estimate $3.70, against
$3.32 for the same 60 samples in v3; median turns 5 in both.)

- **No high-severity deviation shipped silently.** Each one was either fixed or
  approved with a reason. 20/20 samples in each task kept the marker.
- **The HTTP narrowing was mostly declared, not fixed.** 4 samples still retry
  only on timeouts, now with an approval such as *"request says to retry only on
  timeouts and 5xx responses, so plain connection errors are not retried"*. One
  sample (5) first wrote a POST variant, saw `PC100` from `check_code` and rewrote
  it back to the pattern. Another (20) turned the call into a POST and approved
  `must_not_call .post` with *"payments API call is a POST; retries are made safe
  by sending one Idempotency-Key reused across all attempts"*, a good reason a
  reviewer can check. 4 samples approved dropping 429 (`PC109`), e.g. *"request
  says not to retry any 4xx, so 429 is removed from RETRY_STATUSES"*; in all,
  8/20 HTTP samples carry approvals (5 for `PC100`, 4 for `PC109`, one both).
  Low deviations stay unapproved in most samples (only high ones were required).
- **CSV converged on the reviewed parser.** 12/20 kept `import_users` exactly and
  converted xlsx in front of it (v3: 10/20). Pandas still appears in the 4 samples
  of the request that asks for it, but in 3 of them only to turn the upload into
  CSV text (`frame.to_csv()`) that the pattern's `csv.DictReader` then parses (they
  do not count as matches because they also changed `REQUIRED_COLUMNS` and the loop). Sample 1 first replaced `csv.DictReader`, saw `PC100`, and
  restored it. Sample 11 kept pandas parsing and approved `PC100` (*"request
  explicitly requires pandas and xlsx support"*).
- **Pagination** needed no feedback: 20/20 matched. Only 11/20 called
  `check_code` at all, so the instruction is followed less when the agent thinks
  the code is unchanged.

## Example reports

High severity, failing (v3 HTTP sample 2 with a marker added; `pcat lint`, text):

```
v3_http_02.py:10: get_with_retry <- http.get_with_retry.requests@v1 get_with_retry (marked)
  v3_http_02.py:27: PC100 high: `get_with_retry` no longer handles `requests.ConnectionError`
    (it catches requests.Timeout); the reviewed pattern must catch it (connection errors and
    timeouts are transient and must be retried) [guard must_catch] [fails]
  v3_http_02.py:6: PC109 low: `RETRY_STATUSES` changed from (429, 500, 502, 503, 504) to (500, 502, 503, 504)
1 function(s) checked (1 marked, 0 inferred) in 1 file(s); deviations: 1 high, 0 medium, 1 low; 1 failing
```

Approved (v4 feedback HTTP sample 20, the agent's own names; exit code 0):

```
v4_http_20.py:9: post_payment_with_retry <- http.get_with_retry.requests@v1 get_with_retry (marked)
  v4_http_20.py:17: PC100 high: `post_payment_with_retry` calls `.post`, which the reviewed pattern
    forbids (only idempotent GET requests are retried) [guard must_not_call] [approved: payments API
    call is a POST; retries are made safe by sending one Idempotency-Key reused across all attempts]
  v4_http_20.py:9: PC107 medium: `post_payment_with_retry` adds parameter `payload`
  v4_http_20.py:13: PC108 low: `post_payment_with_retry` adds a call to `uuid.uuid4`
  ...
```

The same approved deviation on a pull request (`--format github`, sample 12):

```
::notice file=v4_http_12.py,line=17,title=PC100 guard violated (high) - http.get_with_retry.requests@v1::
  `get_with_retry` no longer handles `requests.ConnectionError` ... (approved: request says to retry
  only on timeouts and 5xx responses, so plain connection errors are not retried)
```

## Assessment

**What the data shows**
- On the v3 samples, the analysis separates unchanged from changed code: none of
  the 122 exact matches is flagged above low, and every one of the 18 misses gets
  a specific, named deviation. The silent HTTP regression is `PC100` high in all 6.
- With deviations in `check_code`, no sample in the feedback run shipped an
  unapproved high-severity deviation (v3: 12 of 60). Pattern match rose slightly
  in all three tasks (0.70→0.75, 0.50→0.60, 0.90→1.00).
- Most high deviations were **approved, not fixed**: 5 HTTP samples and 1 CSV
  sample approved a `PC100` (4 of them the timeout-only narrowing). Two samples
  fixed a high deviation after `check_code` reported it.
- Severity follows the guards. The most common real behaviour change (429 no
  longer retried: 20/20 HTTP samples in v3 and again in v4) is only low, because
  no guard covers it.

**What it suggests (not shown)**
- The main value is turning silent changes into explicit, reviewable claims. Whether
  "the request says timeouts and 5xx" justifies dropping connection-error retries
  is a judgement call; v4 moves it from hidden in the diff to an annotation a
  reviewer reads. That only helps if reviewers read and reject weak reasons.
- Agents treat an approval as a cheap way out. If approvals are too easy, the
  linter becomes a formality. Requiring a human approval for high deviations
  (an approval written by the agent counts as a proposal) would test this.
- Guard coverage drives usefulness more than the analysis does. One missing guard
  (retry statuses) hid the most frequent change. Guards written by reviewers who
  know what agents tend to change would catch more.
- With 20 samples per task and one model, the match-rate increases are within
  noise; the drop in unapproved high deviations (12 → 0) is the robust result.

**Two most valuable next steps**
1. **Make approval a human act and measure review.** Treat agent-written
   `# pcat-allow` lines as proposals: the linter fails until a CODEOWNERS
   reviewer confirms them (e.g. an approval with a reviewer handle, checked in CI
   against the PR's approvals). Then measure how many agent-proposed deviations
   reviewers accept on real pull requests.
2. **Grow guards from observed deviations.** Use replay data across tasks to
   propose guards where agents change behaviour often (e.g. a `must_contain`
   guard for `429` in `RETRY_STATUSES`), let reviewers accept them, and add
   severity for value changes in reviewed tuples and sets. Fix the two noisy
   rules seen here (`PC103` for stdlib plumbing like `io`; `PC110` repeating a
   `must_not_call` line).

## Addendum (v4.1): replay with the new guard and rules

*Added in v4.1 (`docs/specs/v4.1-human-approval.md`); the v4 numbers above are
unchanged.* Same 140 v3 samples, same method, with three v4.1 changes: a
`must_include` guard (`RETRY_STATUSES` must include 429, 500, 502, 503, 504),
PC103 graded by what changed, and PC110 never repeating a line that already
carries another deviation. Data: `experiments/linter/replay_v4.1.json`
(`scripts/lint_eval.py replay`); `replay.json` remains the v4 result.

| | v4 | v4.1 |
|---|---|---|
| HTTP samples flagged for dropping 429 | 0/20 (only `PC109` low) | **20/20** (`PC100` high) |
| Exact matches: no deviation / low / high | 108 / 14 / 0 | 108 / 0 / **14** |
| Misses: medium / high | 6 / 12 | 7 / 11 |
| Samples that would fail CI (`--fail-on high`) | 12 | **25** |
| `PC103`: high / medium | 5 / 0 | 0 / 10 |
| `PC109` / `PC110` deviations | 28 / 29 | 8 / 29 |

- **429.** All 20 HTTP samples now fail on `RETRY_STATUSES` no longer including
  429. That includes the 14 that v3 counted as exact matches and v4 reported
  only as low: they *are* behaviour changes the reviewer cared about, so the v4
  expectation "no exact match above low" no longer holds, deliberately.
- **PC103.** No sample drops a library from a pattern's `requires`, so no `PC103`
  is high any more. The 4 pandas rewrites and 6 openpyxl additions are medium
  ("adds the third-party ..."); CSV sample 2 (`io` → `openpyxl`, high in v4) is
  medium, and its worst severity drops from high to medium. The pandas samples
  still fail on `PC100` (`csv.DictReader` no longer called).
- **PC110** did not change on the replay: its 29 reports are rewrites with new
  statements on lines without another deviation. The rule fixes the v4 feedback
  example instead: on HTTP sample 20, the `session.post(...)` line is now only
  the `PC100` it carries, not also a `PC110`.
- **Approvals.** The v4 feedback samples' approvals have no hash, so under v4.1
  they are stale and approve nothing; each now needs a hash and a human
  confirmation (`pcat approvals check`).
