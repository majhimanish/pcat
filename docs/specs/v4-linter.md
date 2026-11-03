# v4 — Deviation linter

Work unattended. Do not stop to ask questions; when something is ambiguous, pick the simplest reasonable option, record it in `DECISIONS.md`, and continue.

## 0. Before you start

1. Read `CLAUDE.md`, `DECISIONS.md`, `KNOWN_GAPS.md`, every spec in `docs/specs/`, everything in `docs/benchmarks/`, and `docs/catalog-review/v2.2-comparison.md`.
2. Save this file verbatim as `docs/specs/v4-linter.md`.
3. Run the full test matrix and `pcat validate` to confirm a green start.

Do not change canonicalization rules, shape fingerprints, any `impl.py`, any fingerprint, the search threshold, or any experiment data from v2.1–v3. `pattern.yaml` may gain new optional fields.

## 1. Goal

v3 showed that agents find the right pattern every time, but in 18 of 140 runs they changed it after fetching it, and `check_code` only said `none`. One change was a silent regression: HTTP retries narrowed to timeouts, so connection errors stopped being retried.

v4 makes deviations **visible and explained**: for code derived from a pattern, report *what* changed (a dropped exception type, a removed check, a swapped library, a lowered security constant), rate how serious it is, and fail CI on serious unapproved deviations. A human approves a deviation by writing a reason next to the code.

Build in this order, committing after each part: **A** provenance → **B** guards → **C** deviation analysis → **D** `pcat lint` and approvals → **E** MCP upgrade → **F** evaluation → **G** write-up and handoff.

## 2. Part A — provenance

The linter must know which pattern a piece of code came from.

- **Marker (explicit):** `get_pattern` output starts the entry point with a comment line `# pcat: <pattern-id>@v<version>` directly above the `def`. Comments don't affect fingerprints. The server instructions tell agents to keep the marker. A marker may appear above any function.
- **Inference (implicit):** for unmarked functions, find the most similar catalog entry point using the v2.1 similarity measure. At or above a threshold, the function is **likely derived**. Calibrate the threshold on existing data only: v3 end-to-end samples (derived) versus v2.1 condition A/B samples for the deferred FastAPI task and the v3 negative samples (not derived). Record the choice.
- Inferred provenance is **advisory only**: it is reported but never fails CI. Only marked code can fail CI.

## 3. Part B — guards

Reviewed security and correctness properties, declared per pattern so the linter checks what the reviewer cared about. Add an optional `guards` field to `pattern.yaml` (metadata only, no fingerprint effect) supporting these kinds:

- `must_catch`: exception types that must still be handled where the pattern handles them (e.g. `requests.ConnectionError`, `requests.Timeout`)
- `must_call`: calls that must remain (e.g. `hmac.compare_digest`)
- `must_not_call`: calls that must not appear (e.g. `hashlib.md5`, `eval`, `pickle.loads`)
- `min_value`: a constant or default argument that must not go below a value (e.g. PBKDF2 iterations ≥ 600000)
- `must_not_import`: modules that must not be imported
- `must_raise`: exception types the code must still be able to raise (e.g. the pattern's validation errors)

Write guards for all 7 application patterns from each pattern's security notes in `docs/catalog-review/v2.2-comparison.md` and its own code. Write them **before** looking at the v3 miss samples, and commit them before Part F. Every guard must pass on its own pattern (add this as validation check 11).

## 4. Part C — deviation analysis

`src/pcat/deviation.py`, standard library only. Given a function and the pattern it derives from, compare canonical forms and report deviations, each with a stable code, severity, a one-line message **using the user's own names**, and source line.

Compute deviations as explainable set and structure differences, not a raw diff:

| Code | Deviation | Default severity |
|---|---|---|
| `PC100` | guard violated (any guard kind) | high |
| `PC101` | exception type removed from or narrowed in an `except` | high |
| `PC102` | `raise` or validation branch (`if … : raise`) removed | high |
| `PC103` | library swapped: imports differ from the pattern's `requires`/imports | high |
| `PC104` | broad `except` (`Exception`, bare) added | medium |
| `PC105` | call removed | medium |
| `PC106` | private attribute or `_name` access added | medium |
| `PC107` | signature changed (parameter added, removed or default changed) | medium |
| `PC108` | call added | low |
| `PC109` | literal value changed (not covered by a guard) | low |
| `PC110` | other structural change (statements added/removed/reordered) | low |

Also attach a short unified diff of the canonical forms rendered back to the user's names, for display. Code that matches the pattern's shape fingerprint exactly reports no deviations except `PC109` for changed literals.

Deterministic output; no false "removed" reports caused by renaming alone.

## 5. Part D — `pcat lint` and approvals

```
pcat lint <path> [<path> …] [--changed-since REF] [--format text|json|github]
          [--fail-on high|medium|low|never] [--include-inferred]
```
- Scans Python files with the miner's discovery and filters; finds marked functions (and inferred ones with `--include-inferred`, default on for text output, off for CI).
- `--changed-since REF`: only functions whose lines changed relative to `REF` (git diff).
- `--format github`: GitHub Actions annotations so deviations appear on the pull request diff.
- Exit 1 if any **unapproved** deviation on **marked** code is at or above `--fail-on` (default `high`); otherwise 0.

**Approval:** a comment directly above the function's marker or `def`:
```
# pcat-allow: PC101 -- this API only treats timeouts as transient; connection errors must fail fast
```
- One code per line; reason after `--` is required and must be at least 10 characters.
- An approval for a code that no longer occurs is reported as stale (warning, not failure).
- Approved deviations still appear in the report, marked approved, so reviewers see them.

Add a reusable workflow example `docs/ci/pcat-lint.yml` for client repos, and README instructions.

## 6. Part E — MCP upgrade

- `check_code(code, pattern_id=None)`: when `pattern_id` is given, or a marker is present, return deviations from Part C in addition to covered/near/none. Without either, behave as in v3 plus advisory inferred provenance.
- `get_pattern` output includes the marker line.
- Server instructions: after writing code from a pattern, call `check_code` with the pattern id; fix every high-severity deviation unless the request explicitly requires it, and in that case add a `# pcat-allow` line with the reason.

Keep all v3 tool behavior backward compatible; existing v3 tests must pass unchanged.

## 7. Part F — evaluation

**Replay (no new generation).** Run the linter on all v3 end-to-end samples against the pattern each one fetched (from the tool-call logs):
- The 122 exact matches: report precision problems if any get a deviation other than `PC109`.
- The 18 misses: every one gets at least one deviation; the 6 HTTP-retry samples get `PC100`/`PC101` at high severity; the 2 pagination samples get `PC106`; the CSV samples get `PC103` where they switched library.
- Report a confusion summary and every surprising result.

**Inference check:** on the data used for calibration, report how many unmarked functions are inferred as derived correctly and incorrectly.

**Feedback run (small, new generation).** Rerun only the three tasks that had misses (`http_retry`, `csv_import`, `paginate_query`) with the upgraded server, using the same held-out requests and v3 setup: 20 samples each, 60 runs total. Report for each task: pattern match rate, high-severity deviations shipped without approval, and deviations shipped with a `# pcat-allow` reason (quote a few reasons briefly). Compare with v3. Record the CLI's cost estimate, noting it may reflect plan usage rather than billing.

Save results under `experiments/linter/`, reproducible with `scripts/lint_eval.py`.

## 8. Part G — write-up

`docs/benchmarks/v4-linter.md`, committed: setup and limitations; replay results table; inference results; feedback-run table versus v3; examples of reports (one high-severity, one approved deviation) in the user's names; an honest assessment separating what the data shows from what it suggests; and the two most valuable next steps.

## 9. Tests

- Provenance: marker parsing (with and without version, multiple markers in a file); inference threshold applied; inferred never fails CI
- Each guard kind passes on a compliant snippet and fails on a violating one; validation check 11 fails when a guard doesn't hold on its own pattern
- Each deviation code triggers on a minimal fixture and doesn't trigger on renaming alone
- Messages use the user's names, not placeholders
- `pcat lint`: exit codes per `--fail-on`; approvals (valid, missing reason, too short, stale); `--changed-since` on a temporary git repo; `github` format output
- MCP: `check_code` with `pattern_id`, with a marker, and without either; `get_pattern` includes the marker; all v3 tests unchanged
- Evaluation scoring on small fixtures (no live `claude -p` calls in tests)
- Everything passes in all extras combinations

## 10. Acceptance criteria

- Full test matrix passes on Python 3.11 and 3.13; `pcat validate` passes; CI passes on GitHub
- Guards committed before Part F (check git history)
- Replay: all 6 HTTP-retry misses flagged high; no exact match flagged above low
- `docs/benchmarks/v4-linter.md` exists with real numbers
- No `impl.py`, fingerprint, search threshold or earlier experiment file changed

## 11. Handoff

- Update `CLAUDE.md` (within ~150 lines), `DECISIONS.md`, `KNOWN_GAPS.md` and the README.
- Commit after each part, push to `main`, finish with a clean working tree.
- Final message: replay results, feedback-run numbers versus v3, example report lines, and what you'd do next.
