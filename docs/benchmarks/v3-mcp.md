# v3 benchmark: serving the catalog over MCP

Does a coding agent with `pcat serve` connected find the right reviewed pattern
and use it? Two measurements: **retrieval** (search alone, 95 requests) and
**end to end** (160 headless Claude Code runs with the server connected).

Data: `experiments/mcp/` (`dev_negatives.json`, `heldout_needs.json`,
`heldout_set.json`, `retrieval.json`, `e2e/<task>/sample_NN.{json,log.jsonl}`,
`e2e_results.json`). Spec: `docs/specs/v3-mcp-server.md`.

## Setup

- **Catalog:** the 13 patterns on `main` (7 application patterns from v2.2, 6 seeds).
  Part A gave each `keywords`, `use_when`, `usage` and (pbkdf2, env config)
  `exports`, written from each pattern's code only. No `impl.py` or fingerprint changed.
- **Search:** BM25 (k1 = 1.5, b = 0.75) over id tokens, title, summary, category,
  keywords, use_when, entry point and exports, read from `catalog/index.json`;
  lowercase / split / stop words / light suffix stripping. Standard library only.
- **Threshold:** `MATCH_THRESHOLD = 9.08`, calibrated on the development set only:
  the midpoint of the best-accuracy range of candidate cut-offs. On the dev set
  the best negative scored 5.76 and the worst positive 12.41, so the range was wide.
- **Request sets.** *Development:* the 35 v2.1 paraphrases of the 7 cataloged
  tasks + 10 negatives I wrote. *Held-out:* 50 requests written by fresh
  `claude -p` processes (claude-sonnet-5-5, no tools, empty folder), each given
  only a one-sentence developer need (7 positive needs × 5, 15 negative needs × 1,
  including the deferred FastAPI task). Generated after the metadata commit
  (`b9bf291`) and committed (`5a68b6e`) before any evaluation (`a47dff9`).
- **End to end:** `scripts/mcp_eval.py e2e`, same backend as v2.1: one fresh
  `claude -p` per sample (claude-sonnet-5-5) in a new empty folder, no session
  persistence, extra CLAUDE.md directories removed, slash commands disabled,
  `--strict-mcp-config` with only `pcat serve --log <sample log>`, and only the
  three pcat tools allowed (no file, shell or web tools). Prompt = held-out request
  + "This repo uses the organization's pattern catalog via the pcat tools." + the
  v2.1 suffix (one Python code block, standalone functions, no explanation).
  140 positive samples (each task's 5 held-out requests cycled to 20) + 20
  negative samples (held-out negatives cycled). 160/160 completed, 0 failures.
- **Scoring:** `scripts/mcp_eval.py e2e-analyze` (reproducible from the committed
  samples and logs). *Pattern match* runs `check_code`'s logic on the final code:
  every pattern function (entry point and exports) must appear as `covered` (exact
  fingerprint) or `near` (shape fingerprint). *Similarity* is the v2.1 shape-text
  similarity of the whole snippet to the pattern's `impl.py`.

### Limitations

- **Dev-set contamination.** I wrote the metadata and had read the v2.1 tasks in
  earlier phases. I did not look at the paraphrases while writing it, but the
  dev numbers are optimistic by construction; the held-out set is the real test.
- **Held-out authorship.** The needs are mine; the requests come from the same
  model family that is evaluated end to end. Real developers may phrase things
  more tersely (see "terse queries" below).
- **Small catalog.** 13 patterns, 7 of them application patterns with distinct
  vocabularies. Retrieval gets harder as the catalog grows and topics overlap.
- **One model, one client.** Only Claude Code + claude-sonnet-5-5 was tested.
- **Not a controlled comparison with v2.1.** The prompts differ (held-out requests,
  repo note, tools), so the v2.1/v2.2 baselines are indicative only.
- **Library agreement** only checks the catalog's third-party libraries (pyjwt,
  requests, sqlalchemy); it does not flag extra libraries such as pandas.
- **Cost** is the CLI's `total_cost_usd`, an estimate that may reflect plan usage
  rather than billing.

## Retrieval

`python scripts/mcp_eval.py retrieval` → `experiments/mcp/retrieval.json`.

| Set | Positives | Top-1 | Top-3 | Top-1 ignoring threshold | Negatives | False-match rate |
|---|---|---|---|---|---|---|
| Development | 35 | **1.00** (35/35) | 1.00 | 1.00 | 10 | **0.00** (0/10) |
| Held-out | 35 | **1.00** (35/35) | 1.00 | 1.00 | 15 | **0.13** (2/15) |

Per task, both sets: 5/5 top-1 and 5/5 top-3 for every task (`csv_import`,
`env_config`, `http_retry`, `jwt_create`, `paginate_query`, `password_hash`,
`token_bucket`). The lowest-scoring held-out positive scored 13.93; the lowest
dev positive 12.41. Held-out top-1 was above 80%, so there was no improvement round.

**The two held-out false matches** are hard negatives that share vocabulary
with a pattern:
- FastAPI sign-up endpoint ("…validates it with a Pydantic model… invalid input…
  email that's already registered") → `importers.users_csv.parse` at 14.70
  (via "user", "email", "valid", "error"). This scores *above* the lowest held-out
  positive, so no single threshold separates it.
- "Forgot password" email flow → `auth.password.pbkdf2` at 12.01 ("password",
  "secure", "verify", "token").

The next-highest held-out negative scored 7.65 (a large-file download → env
config), below the threshold. Ranking was never wrong; only the "nothing fits"
decision was.

## End to end

`python scripts/mcp_eval.py e2e-analyze` → `experiments/mcp/e2e_results.json`.
20 samples per task.

| Task | Search | Correct retrieval | Pattern match (shape) | Exact | Library | Check | Median sim. | v2.2 baseline: B matched | v2.1 C: ref. shape match |
|---|---|---|---|---|---|---|---|---|---|
| `jwt_create` | 1.00 | 1.00 | **1.00** | 1.00 | 1.00 | 0.90 | 0.816 | 0/20 | 0.56 |
| `password_hash` | 1.00 | 1.00 | **1.00** | 1.00 | 1.00 | 0.45 | 1.000 | 0/20 | 0.70 |
| `paginate_query` | 1.00 | 1.00 | **0.90** | 0.90 | 1.00 | 0.45 | 1.000 | 0/20 | 0.80 |
| `http_retry` | 1.00 | 1.00 | **0.70** | 0.70 | 1.00 | 0.85 | 0.886 | 0/20 | 1.00 |
| `env_config` | 1.00 | 1.00 | **1.00** | 1.00 | 1.00 | 0.90 | 0.652 | 0/15 | 0.90 |
| `token_bucket` | 1.00 | 1.00 | **1.00** | 1.00 | 1.00 | 1.00 | 0.808 | 0/20 | 1.00 |
| `csv_import` | 1.00 | 1.00 | **0.50** | 0.50 | 1.00 | 0.95 | 0.731 | 0/20 | 0.65 |
| **All** | **1.00** | **1.00** | **0.87** (122/140) | 0.87 | 1.00 | 0.79 | | **0/135** | |

- **Baselines.** v2.2's coverage check: none of the 135 valid v2.1 condition-B
  samples (paraphrased prompts, no catalog) contained the chosen pattern, exactly
  or by shape. v2.1 condition C (an unreviewed reference pasted in the prompt)
  reached 56–100% reference shape match. With the server, the agent itself had to
  find the pattern and still reached 50–100% per task (87% overall).
- **Every match was exact.** No sample changed only literal values; agents either
  kept the pattern's structure exactly (renaming freely) or changed it.
- **Median similarity** is over the whole snippet, so code around the pattern
  (wrappers, a CLI, tests, an xlsx converter) lowers it even when the pattern
  function is present verbatim — e.g. `env_config` 0.652 with 20/20 exact.
- **Negatives (20):** search rate 1.00; 6 got above-threshold hits (some from a
  second, sub-task query); 2 called `get_pattern` and both used
  `auth.password.pbkdf2` — for the password hashing inside the FastAPI sign-up
  endpoint. That is a fitting sub-task, not a forced pattern; no negative bent
  its main task to a pattern. The forgot-password flow saw pbkdf2 in its results
  twice and correctly did not use it. Check rate 0.95.
- **Behaviour:** median 1 search query per sample (max 2), median 5 turns. Agent
  queries were descriptive phrases ("Parse and validate a users CSV/Excel upload
  with per-row errors"), never one or two words.
- **Cost** (CLI estimate): $8.65 total, $0.054 per positive sample, $0.055 per negative.

## Where the agent did not use the pattern, and why

All 18 non-matching positive samples searched, retrieved and fetched the right
pattern. From the logs and code:

| Reason | Samples |
|---|---|
| Didn't search | 0 |
| Searched with a poor query / search missed | 0 |
| Fetched a different pattern | 0 |
| Retrieved, then rewrote without being asked | 2 (`paginate_query`) |
| Retrieved, then adapted for something the request said | 16 (`csv_import` 10, `http_retry` 6) |

- **`csv_import` (10/20):** every held-out request asks for "CSV or xlsx/Excel"; the
  pattern parses CSV text. The 10 matching samples kept `import_users` verbatim and
  added an `xlsx_to_csv_text` converter in front — the intended adaptation. The
  10 others rewrote the reader around a row iterator: 4/4 samples of the request
  that asked to "use pandas if that makes sense" switched to pandas; 4/4 of
  another request and 2 more restructured it into per-format readers. These are
  legitimate, request-driven changes, but they lose the reviewed parser.
- **`http_retry` (6/20):** two requests say the API "sometimes times out or returns
  5xx errors". The pattern retries on `(requests.ConnectionError, requests.Timeout)`
  and on 5xx; 6 samples narrowed the exception to `requests.Timeout` to follow the
  wording literally (all 4 samples of one request, 2 of 4 of the other). Read
  against the request this is "adapting what it explicitly requires", but it is a
  **silent regression**: connection failures are no longer retried.
- **`paginate_query` (2/20):** both from one request; they added an unrequested
  "statement must have an ORDER BY" check that reads SQLAlchemy's private
  `stmt._order_by_clauses`. A reasonable worry, but not asked for and built on a
  private attribute.
  *Erratum (v4 replay):* only sample 12 reads `_order_by_clauses`; sample 17 adds
  an unrequested `tiebreaker` parameter for a stable ORDER BY instead (no private
  access). Both are unrequested rewrites, so the counts above are unchanged.

`check_code` was called in 79% of positive samples but did not prevent these:
the agent saw `none` for its rewritten function and submitted anyway. The tool
reports; nothing obliges the agent to act on it.

## Assessment

**What the data shows**
- On this catalog, search alone finds the right pattern for every request in
  both sets (70/70 top-1), with a threshold calibrated only on dev.
- The "no pattern fits" decision is the weak spot: 0/10 false matches on dev,
  2/15 on held-out, both hard negatives that share a domain with a pattern.
- With the server connected and a one-line repo note, the agent searched in
  160/160 runs and fetched the correct pattern in 140/140 positive runs; 87% of
  positive samples contain the reviewed pattern exactly, against 0% of v2.1's
  catalog-free samples. Library choice agreed in 100%.
- Every miss followed retrieval; none came from the agent skipping the tools.
- The agent did not force patterns onto unrelated work: 0/20 negatives, with 2
  legitimate sub-task uses.

**What it suggests (not shown)**
- Delivery, not retrieval, is now the limit: the remaining variance comes from
  how much the agent decides a request entitles it to change. Requests that name
  a different library or input format (pandas, xlsx) or describe behaviour
  narrowly ("times out") pull the agent off the pattern.
- The 100% search rate probably owes much to the explicit repo note and to a tool
  set limited to pcat; with file and shell tools available and no note, search
  rates are likely lower. That was not measured.
- Retrieval numbers will fall as the catalog grows and categories overlap; BM25
  over hand-written keywords is fine at 13 patterns and untested beyond.
- The prompts differ from v2.1, so "0% → 87%" is indicative, not a controlled effect size.

**Two most valuable next steps**
1. **Make deviations visible and costly: the v4 linter plus a stricter
   `check_code`.** Have `check_code` report *what* differs from the fetched
   pattern (dropped exception types, removed checks, private attributes) and let
   CI flag functions that are `none` but closely resemble a pattern. The
   `http_retry` narrowing is exactly the kind of silent regression review should
   catch.
2. **Run end to end in realistic conditions.** A repo with file/shell tools, no
   explicit note (only the server instructions), terse real-developer requests, a
   larger catalog with overlapping topics, and a second model. This measures the
   search rate and the false-match rate where they actually matter, and would
   show whether an embedding or LLM rerank step is needed for "nothing fits".

## Reproduce

```bash
pip install -e ".[dev,catalog,mcp]"
python scripts/mcp_eval.py heldout --resume     # held-out requests (needs `claude`)
python scripts/mcp_eval.py retrieval            # offline; writes retrieval.json
python scripts/mcp_eval.py e2e --jobs 6         # 160 claude -p runs with pcat serve
python scripts/mcp_eval.py e2e-analyze          # offline; writes e2e_results.json
```
