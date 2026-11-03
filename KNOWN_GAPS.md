# Known gaps

Honest list of limitations (as of v1.1), each with a suggested fix. Remove an entry
when you fix it; add one whenever you take a shortcut.

## Canonicalization

- **Indirect calls to snippet functions keep keyword names.** Only direct calls
  `f(key=…)` are rewritten. `functools.partial(f, key=…)`, `f(**{"key": …})`,
  aliases (`g = f; g(key=…)`) and callbacks invoked with keywords elsewhere keep
  the real keyword, so their canonical text is not runnable and a custom
  `render --names` can break them. *Fix:* reject or rewrite these forms when the
  target resolves to a snippet function.
- **One flat scope per top-level function.** A comprehension variable that
  shadows an outer local (`x = 1; [x for x in xs]`) gets the same placeholder as
  the outer `x`. Behaviour is preserved, but writing it with a distinct name
  gives a different fingerprint. *Fix:* number nested scopes (lambda,
  comprehension, nested def) separately.
- **Fingerprints depend on the Python version's `ast.unparse`.** Seeds are
  identical on 3.11–3.13, but unparse details (f-string quoting, parentheses)
  have changed between versions before. CI pins 3.11. *Fix:* add a
  version-independent printer, or a CI matrix that asserts identical
  fingerprints across supported versions.
- **No classes.** Classes are rejected at top level and inside functions.
  *Fix:* support class patterns with method-level scopes and leave attribute
  names untouched (class-body bindings must not be renamed).
- **Only literal constants.** Module-level values that are not
  `ast.literal_eval` literals (a compiled regex, `frozenset(...)`, a value
  computed from another constant) still cannot be part of a pattern; `pcat add`
  now fails naming them instead of dropping them. *Fix:* allow an explicit
  allowlist of pure constructors (`re.compile`, `frozenset`, `tuple`), or move
  such values into the function.
- **Mutable literal constants are shared state.** `CACHE = {}` or `ITEMS = [1]`
  is accepted and functions can mutate it across calls. *Fix:* accept only
  immutable literals (numbers, strings, bytes, bools, None, tuples/frozen
  forms), or have validation warn on list/dict/set constants.
- **`pcat add` drops inline comments after constants** (`X = 1  # why`): constants
  are copied as their exact source segment. *Fix:* copy whole source lines when
  no other statement shares them.
- **Function order matters beyond the entry point.** Helpers keep source order,
  so swapping two helpers changes the fingerprint. *Fix:* order helpers by first
  reference from `f0` (a migration).
- **Unused imports are part of the fingerprint**, and `import os.path` vs
  `import os` differ. *Fix:* drop imports whose names are never referenced.
- **Dynamic name access is not understood** (`locals()`, `globals()`, `eval`,
  `exec`, string annotations, `getattr(module, "name")`): renaming can change
  behaviour for such code. *Fix:* reject snippets that call these.
- **Python 3.12 type parameters** (`def f[T](x: T)`) are not renamed and not
  stripped with `keep_annotations: false`. *Fix:* treat `type_params` as
  module-scope bindings of the function.

## Validation and workflow

- **Immutability depends on CI and branch protection.** Locally, only check 4
  (fingerprint mismatch) guards approved code; someone can rewrite the
  fingerprint. The `--base` check catches that, but only on pull requests, and
  only if `main` is protected (required PR, required `validate` check, required
  code-owner review). *Fix:* document/automate branch protection; run `--base`
  on pushes too (`--base ${{ github.event.before }}`).
- **`replaced_by` chains are not checked**: a deprecated pattern can point to
  another deprecated pattern, and cycles are not detected. *Fix:* follow the
  chain and require it to end at an active pattern.
- **`behavior` content is not reviewed by tooling**: the scaffold's
  `todo: describe` placeholder passes the schema. *Fix:* reject `todo` keys/
  values, or define per-category behavior vocabularies.
- **Variant families have no root entry**: `variant_of: search.binary_search`
  names a family that exists only implicitly. *Fix:* optional
  `catalog/<category>/<family>/family.yaml` with a description.
- **Pattern tests run with whatever packages are installed**; there is no
  per-pattern dependency declaration. *Fix:* add `requires:` to the schema and
  install into an isolated environment per pattern.
- **Check 8 is slow-ish at scale** (one pytest process per pattern, sequential).
  *Fix:* run in parallel, or only for patterns changed relative to `--base`.
- **`CODEOWNERS` uses a placeholder team** (`@platform-team`), which GitHub
  ignores until replaced with a real team.

## CLI

- **`pcat find` uses a loose match for annotations.** It compares both the
  annotated and the annotation-stripped fingerprint, so a function that differs
  from a pattern only by annotations is reported when that pattern has no
  annotations. *Fix:* add `keep_annotations` to `index.json` and compare in the
  matching mode only.
- **`pcat find` only finds exact structural matches** (same canonical form);
  any refactor, extra statement or different helper split is a miss. That is by
  design for v1; near-miss detection belongs to the planned linter/miner.
- **`pcat show` prints re-serialized metadata**, so comments in `pattern.yaml`
  are not shown. *Fix:* print the raw file.
- **The render collision check lives in the CLI only.** `canonical.render()`
  itself does not detect collisions. *Fix:* move the check into a
  `render_checked()` library function for the future MCP server.
- **Windows is untested.** Paths are handled with `pathlib` and files are
  written with `\n`, but CI runs only on Linux.

## Miner (v2)

- **Docs and example code dominate results.** In the benchmark every default-run
  cluster came from FastAPI's `docs_src/`. *Fix:* skip `docs/`, `docs_src/`,
  `examples/` by default and report byte-identical files once, separately.
- **Annotation spelling splits shapes** (`Union[X, None]` vs `X | None` vs
  `Annotated[...]`). *Fix:* an annotation-insensitive shape level (strip or
  normalize annotations before blanking).
- **`test_*` functions in non-test files are mined.** *Fix:* also filter by
  function name, switchable with `--include-tests`.
- **Free names must match exactly** (called functions, attributes, globals), so
  idioms that differ only in which API they call never cluster; 54 of 55
  benchmark clusters were plain exact copies. *Fix:* an optional looser level
  that abstracts free names, reported separately.
- **Only top-level functions can be promoted.** Methods (12 of 15 library-only
  benchmark clusters), nested functions and fragments must be extracted by hand.
  *Fix:* class support in patterns; a fragment-to-function extractor.
- **`index.json` has no shape or entry-point fingerprints**, so the miner reads
  pattern folders. *Fix:* add `entry_fingerprint`, `shape_fingerprint`,
  `entry_shape_fingerprint` and `shape_version` to the index before building
  the out-of-process linter.
- **Inputs are stored as given**, so `pcat promote` must run from the directory
  where `pcat mine` ran when relative paths were used. *Fix:* store paths relative
  to the report, or accept a `--base-dir`.
- **The cache is never pruned** and lives in the working directory. *Fix:*
  `pcat mine --prune-cache`, or an LRU limit.
- **Reports list every member**, which gets large on big corpora (the benchmark's
  report.json is ~300 KB for 55+7 clusters). *Fix:* cap members shown per
  cluster in HTML, add paging.
- **Score ignores spread**: 23 copies in one folder outrank a shape repeated across
  teams. *Fix:* weight by distinct inputs/files.
- **Fragment normalization does not check placeholder collisions** (a free name
  like `v0` can merge shapes), and `else: if` is treated as `elif`. Both are rare.

## Variance experiment (v2.1)

- **One model through one backend.** All samples are Claude Sonnet 5.5 via
  `claude -p`, which adds Claude Code's system prompt and a little hosting
  context, and hides the temperature. *Fix:* re-run with `ANTHROPIC_API_KEY`
  (bare API calls) and at least one more model; compare.
- **The CLI can answer as a skill** (2 samples became `/security-review` output).
  *Fix:* prefer the API backend; with the CLI, disable skills/slash commands
  (`--disable-slash-commands`) and check that responses contain code.
- **20 samples hit the ceiling.** A and B often have 20/20 distinct shapes, so the
  data cannot rank them. *Fix:* 50–100 samples per cell for the main tasks.
- **"No classes" conflicts with idiomatic FastAPI**, leaving 1–2 valid samples in
  A/B for that task (only the supplementary metric covers it). *Fix:* support
  classes in canonicalization, or ask for models in a separate block.
- **References are arbitrary sampled outputs** and sit directly in the prompt.
  *Fix:* use reviewed catalog patterns and a real retrieval step (MCP lookup),
  and run each reference's tests against the condition-C samples.
- **Strict shape equality overstates differences**; the 0.90 similarity threshold
  for near-shape groups is a judgment call. *Fix:* report the full similarity
  distribution, or a semantic check (do two samples pass the same tests?).
- **`third_party` uses the running interpreter's `sys.stdlib_module_names`**, so
  import-set columns could differ slightly across Python versions.

## Catalog review (v2.2 Part 1)

- **Grouping relied partly on regexes**; the counts in the comparison are
  approximate where a decision is hard to detect textually. *Fix:* classify with
  AST checks per decision, or label samples by hand.
- **Pagination is tested on SQLite only.** COUNT over a subquery and LIMIT/OFFSET
  behave the same on PostgreSQL/MySQL, but this is untested. *Fix:* a CI job with
  a PostgreSQL service.
- **FastAPI TestClient warns** that `httpx` is deprecated for Starlette's test
  client in favour of `httpx2`. *Fix:* switch the test dependency once `httpx2`
  is stable.

## Application catalog (v2.2 Part 2)

- **Skipped tests count as passing.** Without the `catalog` extra, `pcat validate`
  passes third-party patterns whose tests were all skipped. CI installs the extra,
  so it verifies them there. *Fix:* report skipped patterns in `validate` output,
  or add a `--require-tests-run` flag for CI.
- **`requires` is not checked against imports.** Nothing verifies that a pattern
  importing `jwt` declares `pyjwt`. *Fix:* map top-level imports to distributions
  (`importlib.metadata.packages_distributions`) during validation.
- **FastAPI create-user is deferred** until patterns can contain classes
  (Pydantic models). The tested class-free variant stays in `docs/catalog-review/`.
- **Seed-specific assumptions** may remain in docs or examples (e.g.
  `pcat show search.binary_search.iterative` in the quick start); harmless, but
  application patterns make better examples.
- **Owner and review are placeholders**: every pattern's `owner` is
  `@platform-team` and CODEOWNERS still names that placeholder team.

## MCP server and search (v3)

- **"Nothing fits" is the weak spot.** 2 of 15 held-out negatives matched above
  the threshold (FastAPI sign-up → CSV importer at 14.70, forgot-password →
  pbkdf2 at 12.01); the first scores above the lowest held-out positive, so no
  BM25 threshold separates it. *Fix:* rerank the top hits with embeddings or a
  cheap LLM judgment of `use_when`, or let `search_patterns` return a "partial
  fit" band instead of a hard cut.
- **Terse queries fall below the threshold.** "throttle API calls per client"
  scores 6.92 (< 9.08) although `ratelimit.token_bucket.check` is the right
  answer; agents wrote descriptive queries in the evaluation, people may not.
  *Fix:* synonyms in `keywords` (throttle), or return below-threshold hits
  marked as weak.
- **Agents still change patterns after fetching them.** 18 of 140 end-to-end
  samples fetched the right pattern and changed its structure: request-driven
  (xlsx input, pandas) but also a silent regression (`http_retry` narrowed to
  `requests.Timeout`, dropping connection-error retries) and an unasked check
  reading SQLAlchemy's private `_order_by_clauses`. `check_code` reported `none`
  and the agent submitted anyway. *Addressed in v4:* `check_code` and `pcat lint`
  now report what differs; agents mostly approve rather than fix (see v4 gaps).
- **The evaluation favours the server.** One model (claude-sonnet-5-5), only the
  pcat tools allowed, an explicit repo note, requests written by the same model
  family from needs I wrote, a 13-pattern catalog. *Fix:* rerun with file/shell
  tools, no note, real developer requests, a larger catalog and another model.
- **Dev set contamination.** Metadata and dev negatives were written by the
  author of the v2.1 tasks; dev numbers are optimistic. Use only held-out-style
  sets to judge future search changes.
- **Search is lexical and English-only**, rebuilt per process from `index.json`
  (fine at 13 patterns; untested at hundreds).
- **`check_code` matches only entry points and exports**, by whole-function
  fingerprint; a pattern inlined into a larger function, or split differently,
  is `none`.
- **FastMCP logs INFO lines to stderr** on every request; harmless for stdio
  clients but noisy in terminals. *Fix:* set the SDK's log level in `serve`.
- **Cost figures are CLI estimates** (`total_cost_usd`), which may reflect plan
  usage rather than billing.
- **The tool-call log grows without bound** and has timestamps (it is
  evaluation output, not a deterministic artifact). *Fix:* rotate, or keep it
  out of repositories.

## Deviation linter (v4)

- **Approvals are written by agents.** *Addressed in v4.1:* new approvals are
  proposals until an approver confirms the pull request (`pcat approvals check`).
- **Removing the marker escapes CI.** *Addressed in v4.1* by PC111, with limits
  (see v4.1 gaps).
- **Guards cover only what was written down.** v4.1 added `must_include` and the
  429 guard; other unguarded behaviour changes stay low. *Fix:* propose guards
  from observed deviations.
- **Severity is rule-based.** v4.1 graded PC103 and stopped PC110 repeating lines;
  severities are still fixed per rule, not per pattern.
- **Guard matching is by name.** `must_call: hmac.compare_digest` rejects the
  identical `secrets.compare_digest`; `must_catch` knows builtin superclasses but
  not third-party ones (`requests.RequestException`); a `min_value`/`max_value`
  whose target was inlined or renamed beyond alignment is "not checked". *Fix:*
  alternatives in guard names (`a | b`), a small superclass table per library.
- **Alignment is heuristic.** Helpers, parameters and constants pair by name and
  then by position; in heavy rewrites messages and the diff can name the wrong
  counterpart. Code split differently from the pattern (logic moved into a new
  helper) shows as many PC105/PC108/PC110 lines.
- **Inference margin is narrow and fitted.** Threshold 0.56 sits between the
  lowest derived (0.54) and highest non-derived (0.58) function of the
  calibration set it was chosen on; derived labels were themselves picked by
  similarity. Small validators score near `parse_bool`. Advisory only.
- **Guards are not in `index.json`** (deliberately, to keep the format stable);
  out-of-process tools cannot see them. *Fix:* add `guards` in the next index change.
- **The replay was not blind** (the v3 write-up named the misses; three miss samples
  were inspected while building the analyzer). Future rule changes should be judged
  on new samples, e.g. another feedback run.
- **`check_code` is skipped when the agent thinks nothing changed** (11/20 pagination
  feedback samples called it). Harmless here; `pcat lint` in CI is the backstop.
- **`--changed-since` runs git once per file**; slow on very large trees.

## Human approval (v4.1)

- **Nothing makes the gate required.** `pcat-approvals` fails, but the pull
  request can still be merged unless branch protection lists it as a required
  check. *Fix:* the owner adds `pcat-approvals / approvals` as a required status
  check on `main`.
- **Solo mode in this repository.** `.pcat/approvers.yaml` has `allow_author: true`,
  so the author confirms their own proposals: the check proves a human looked,
  not a second human. GitHub also refuses self-approving reviews, so here the
  only route is the `/pcat approve` comment.
- **Comment confirmations trust commit dates.** A comment counts if posted after
  the head commit's committer date, which the author can set. The review route
  (bound to `commit_id`) is stronger. *Fix:* compare against the time the head
  commit was pushed (the `synchronize` event / timeline API).
- **A confirmation covers the whole pull request**, not one proposal; an approver
  cannot confirm one proposal and reject another except by changing the code.
- **CODEOWNERS support is partial**: users only (no `@org/team`), simplified
  pattern matching, last matching rule wins.
- **Re-running needs `actions: write` and runs from the default branch's workflow.**
  Pull requests from forks get read-only tokens, so the comment/review run cannot
  re-run the original check there; the comment-triggered run itself is not shown
  on the pull request.
- **The hash covers the function only.** Changing a helper or a module constant
  does not make an approval stale (`must_include`/value guards still check
  constants). *Fix:* hash the unit (function + helpers + constants it reads).
- **PC111 needs a base ref and the same qualname.** Renaming the function while
  removing the marker, or linting without `--changed-since`, escapes it; it also
  relies on inference (threshold 0.56).
- **The confirmation path was not exercised on GitHub.** The demo pull request
  shows the failing state; the passing path (comment → re-run → green) is covered
  by mocked tests only until the owner confirms the demo.

