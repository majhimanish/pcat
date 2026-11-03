# v3 — MCP server

Work unattended. Do not stop to ask questions; when something is ambiguous, pick the simplest reasonable option, record it in `DECISIONS.md`, and continue.

## 0. Before you start

1. Read `CLAUDE.md`, `DECISIONS.md`, `KNOWN_GAPS.md`, every spec in `docs/specs/`, `docs/benchmarks/` and `docs/catalog-review/v2.2-comparison.md`.
2. Save this file verbatim as `docs/specs/v3-mcp-server.md`.
3. Run `pytest` and `pcat validate` (with and without the `catalog` extra) to confirm a green start.

Do not change canonicalization rules, shape fingerprints, any pattern's `impl.py`, any fingerprint, or the experiment data from v2.1/v2.2. Metadata in `pattern.yaml` may gain new optional fields.

## 1. Goal

Deliver catalog patterns to coding agents through an MCP server, and measure two things:
- **Retrieval:** given a plain-language request, does search return the right pattern, and stay quiet when nothing fits?
- **End to end:** with the server connected, how often does the agent's code match the reviewed pattern? This is the real-product version of v2.1's condition C.

Build in this order, committing after each part: **A** metadata → **B** search → **C** server → **D** retrieval eval → **E** end-to-end eval → **F** write-up and handoff.

## 2. Part A — metadata

Add optional fields to `pattern.yaml`. None may affect fingerprints. All appear in `index.json`.
- `exports`: public functions besides the entry point (closes the KNOWN_GAPS entry). Fill in for `auth.password.pbkdf2` (`verify_password`, `needs_rehash`) and `config.env.load_settings` (`parse_bool`). Validation: every export exists in `impl.py`.
- `keywords`: 5–15 search terms
- `use_when`: one or two sentences describing the situations the pattern is for
- `usage`: a short example of calling the pattern (a few lines), shown to agents

Write `keywords`, `use_when` and `usage` for all 13 patterns **from each pattern's own code and purpose only**. Do not look at `experiments/variance/tasks.yaml` paraphrases while writing them; they are evaluation data. Commit the metadata before Part D.

`pcat validate --base` must keep allowing metadata-only changes to approved patterns while still rejecting any `impl.py` change.

## 3. Part B — search

`src/pcat/search.py`, standard library only:
- BM25 ranking over each active pattern's id tokens, title, summary, category, `keywords`, `use_when`, entry point and export names
- Simple tokenizer: lowercase, split on non-alphanumerics and `_`/`.`, drop a small fixed stop-word list, light suffix stripping (e.g. `tokens` → `token`). Deterministic.
- Deprecated patterns excluded unless `include_deprecated=True`
- A score threshold below which a request is treated as **no match**. Calibrate it in Part D on the development set only, store it in a constant, and record how it was chosen.
- Results sorted by score, then id

CLI: `pcat search "<request>" [--limit N]` printing id, score and title.

## 4. Part C — MCP server

Use the official `mcp` Python SDK, stdio transport. Add it to a new `mcp` optional-dependency group. Entry point: `pcat serve [--catalog PATH] [--log FILE]`.

Server instructions (sent to the client): this organization keeps reviewed code patterns; before writing code for a common application task (auth, passwords, pagination, HTTP retries, config loading, rate limiting, CSV import, and whatever categories the catalog has), call `search_patterns`; if a pattern fits, call `get_pattern` and use it, adapting only names and what the request explicitly requires; afterwards, call `check_code` on the result. Generate the category list from the catalog.

Tools:
- **`search_patterns(request: str, limit: int = 5)`** → matches above the threshold, each with id, title, summary, `use_when`, score, `requires`, `exports`. An empty list when nothing passes the threshold, with a message saying no reviewed pattern fits.
- **`get_pattern(id: str, names: dict | None = None)`** → rendered code (with the caller's names via the existing `render`; invalid name keys are an error listing the valid ones), `requires`, `exports`, `usage`, version, status. Deprecated patterns return a warning naming `replaced_by`.
- **`check_code(code: str)`** → for each function: `covered` (exact fingerprint match, with id), `near` (shape match, with id, meaning only literal values differ), or `none`. Reuse the miner's analysis. Code that doesn't parse returns a clear error, not an exception.

All tool results are JSON-serializable and deterministic. If `--log` is given, append one JSON line per tool call (tool, arguments, result summary, timestamp) for the evaluation.

README: how to connect the server to Claude Code and to other MCP clients, and a short suggested `CLAUDE.md` line for repos that use it.

## 5. Part D — retrieval evaluation

Two request sets, kept separate:
- **Development set:** the 5 paraphrases per task from `tasks.yaml` for the 7 cataloged tasks (35 requests), plus 10 negative requests you write (common tasks with no pattern, e.g. sending email, resizing images, a FastAPI endpoint).
- **Held-out set:** generated **after** Part A's metadata is committed, by fresh `claude -p` processes in empty folders with no tools. Each is given only a one-sentence description of a developer's need (not the pattern's metadata) and asked to write how a developer would phrase the request. 5 requests per cataloged task (35), plus 15 negative needs (including the deferred FastAPI task). Commit the held-out set before evaluating on it.

Calibrate the threshold on the development set only. Then report for both sets: top-1 accuracy, top-3 accuracy, false-match rate on negatives, and per-task results. Save results as JSON under `experiments/mcp/` and make the evaluation reproducible with `scripts/mcp_eval.py retrieval`.

If held-out top-1 accuracy is below 80%, improve tokenization or metadata **using only the development set and the patterns themselves**, never the held-out requests, and report both before and after numbers.

## 6. Part E — end-to-end evaluation

Same backend approach as v2.1 (`claude -p`, one fresh process per sample in a new empty folder, extra CLAUDE.md files disabled), with the MCP server connected via `--mcp-config` and its `--log` writing to a per-sample file. Allow only the server's three tools; no file, shell or web tools.

- **With-server condition:** the 35 held-out requests for the 7 tasks, cycled to 20 samples per task (140 samples). Prompt: the request, a one-line note simulating a repo's CLAUDE.md ("This repo uses the organization's pattern catalog via the pcat tools."), and the v2.1 suffix (one Python code block, standalone functions, no explanation).
- **Negative condition:** 20 samples from the held-out negative requests, to check the agent doesn't force a pattern onto unrelated work.
- Total 160 samples. Record everything as in v2.1, plus the tool-call log.

Metrics per task:
- **Search rate:** fraction of samples where the agent called `search_patterns`
- **Correct retrieval:** fraction that called `get_pattern` with the right id
- **Pattern match:** fraction whose code contains the pattern's entry point (and exports) with the pattern's shape fingerprint, using `check_code`'s logic; also the v2.1 similarity score to the pattern
- **Library agreement:** the code's imports match the pattern's `requires`
- **Check rate:** fraction that called `check_code`
- Negatives: fraction that called `get_pattern` and used a pattern anyway (should be near 0)

Baseline for comparison: v2.1 condition B and the v2.2 coverage check (0 of 135 matched). State clearly that the prompts differ from v2.1's, so the comparison is indicative, not controlled. Record the cost the CLI reports, and note it is an estimate that may come from plan usage rather than billing.

## 7. Part F — write-up

`docs/benchmarks/v3-mcp.md`, committed:
- Setup and limitations
- Retrieval table (dev and held-out), with any misses explained
- End-to-end table per task with the metrics above, alongside the v2.1/v2.2 baseline
- Where the agent failed to use the server and why (from the logs): didn't search, searched with a poor query, retrieved but rewrote, or adapted for a legitimate reason in the request
- An honest assessment, separating what the data shows from what it suggests, and the two most valuable next steps

## 8. Tests

- Metadata: new fields validate; a missing export fails; fingerprints and `impl.py` unchanged; metadata-only change passes `--base`
- Search: deterministic ranking; tokenizer cases; deprecated excluded; threshold returns no match for an unrelated request
- Server: each tool via the SDK's in-process test client or direct handler calls: search results, empty results, `get_pattern` with and without names, invalid name keys, unknown id, deprecated warning, `check_code` covered/near/none/syntax error, log lines written
- Evaluation scoring functions on small fixtures (no live `claude -p` calls in tests)
- Everything passes with and without the `catalog` and `mcp` extras (server tests skip cleanly without `mcp`)

## 9. Acceptance criteria

- `pytest` passes on Python 3.11 and 3.13 in all extras combinations; `pcat validate` passes; CI passes on GitHub (CI installs the `mcp` extra)
- Git history shows Part A metadata committed before the held-out set was generated, and the held-out set committed before it was evaluated
- `pcat serve` works with Claude Code (proven by the end-to-end run)
- `docs/benchmarks/v3-mcp.md` exists with real numbers
- No `impl.py`, fingerprint, or v2.1/v2.2 experiment file changed

## 10. Handoff

- Update `CLAUDE.md` (keep it within ~150 lines), `DECISIONS.md`, `KNOWN_GAPS.md` and the README.
- Commit after each part, push to `main`, finish with a clean working tree.
- Final message: retrieval numbers (dev and held-out), end-to-end headline numbers, the main reasons the agent didn't use patterns, and what you'd do next.
