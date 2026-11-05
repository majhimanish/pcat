# pcat

Reviewed code patterns for AI coding agents. Your team keeps a catalog of approved
versions of the code it writes again and again (auth checks, tokens, password hashing,
retries, pagination, settings, rate limits); coding agents fetch them through an MCP
server instead of improvising, and a CI linter explains, on the pull request, how new
code deviates from its pattern. Legitimate deviations need a human's confirmation.

## Quickstart

```bash
pipx install "pcat[mcp] @ git+https://github.com/majhimanish/pcat"   # or pip install, Python 3.11+
cd your-repo
pcat init --starter            # shows what it would set up; changes nothing
pcat init --starter --apply    # catalog, Claude Code MCP config, CI workflows, candidates
pcat audit .                   # one-time report: code that looks like a pattern but breaks it
pcat lint . --changed-since origin/main   # what the pull-request check reports
```

Then follow **[docs/getting-started.md](docs/getting-started.md)** (about 30 minutes):
promote a first pattern, connect Claude Code, see a deviation flagged on a pull request.
Measured results and what is safe to claim: [docs/benchmarks/summary.md](docs/benchmarks/summary.md).

## About this repository

An organization-specific catalog of **verified Python code patterns**.

Code written by people or AI agents drifts: every prompt produces a slightly
different JWT helper, password check or retry loop. Instead, common code shapes
are written once, reviewed by engineers, and stored here. Each pattern is a
self-contained function with metadata and tests, plus a **fingerprint** of its
canonical form, so tools can tell when a piece of code *is* a catalog pattern
no matter how its variables are named or commented.

**The catalog's focus is application patterns** chosen and reviewed by a person
(v2.2): JWT creation, password hashing, pagination, HTTP retry, settings from
the environment, rate limiting and CSV import (`auth.*`, `db.*`, `http.*`,
`config.*`, `ratelimit.*`, `importers.*`). The six original algorithm seeds
(binary search, merge sort, …) remain as small, well-tested examples.

This repository has the catalog and its review workflow (file format,
canonicalizer, `pcat` CLI, validation, CI) and a **miner** that measures how much
code repeats and promotes repeated functions into patterns (see
[Mining](#mining-finding-candidate-patterns)), and an **MCP server** that serves
the catalog to coding agents (see [Serving the catalog](#serving-the-catalog-to-coding-agents-mcp)).
A **deviation linter** reports how derived code differs from its pattern (see [Deviation linter](#deviation-linter-pcat-lint)).

## Developing pcat

This repository holds the tool, its own catalog and the research behind it.

```bash
python -m venv .venv && . .venv/bin/activate     # Python 3.11+
pip install -e ".[dev,catalog,mcp]"   # catalog = libraries the patterns import; mcp = pcat serve
pytest                  # tool tests; also validates the catalog (third-party pattern
                        # tests skip if the catalog extra is not installed)
pcat validate           # all catalog checks, including every pattern's tests
pcat show search.binary_search.iterative
```

## Concepts

| Term | Meaning |
|---|---|
| Pattern | One verified function (plus helpers it calls) with `pattern.yaml`, `impl.py`, `test_impl.py`. |
| Variant | A separate pattern per behavior-relevant difference, e.g. `search.binary_search.iterative` vs `.recursive`. Variants share `variant_of` and must differ in `behavior`. |
| Canonical form | `impl.py` with docstrings, comments, formatting and local names removed: functions become `f0, f1, …` (entry point is `f0`), constants `c0, c1, …`, parameters/locals `v0, v1, …` per function. Imports are sorted. |
| Fingerprint | SHA-256 of the canonical form. Same code with different names/comments ⇒ same fingerprint. |
| Name map | Placeholder → real name (`{"f0": "binary_search", "v0": "items", "f1.v0": …, "c0": …}`). Canonical form + name map renders readable code. |

Try it: `pcat canonical some_file.py --entry my_function`.

### Canonicalization rules (version 2)

`canonical.CANONICAL_VERSION` (recorded in `index.json`) names the rule set.

- Output: sorted, one-name-per-line imports; then literal constants in source
  order; then the entry point `f0`; then helpers in source order.
- Renamed: top-level functions (`fN`), literal constants (`cN`), and each
  function's parameters and locals (`vM`, restarting per function).
- Never renamed: builtins and other free names, imported names, attribute
  names, `self`/`cls`, dunder names, and keyword-argument names at call sites —
  **except at calls to functions defined in the pattern**, where keywords
  follow the callee's parameter placeholders (`f1(v0, v2=True)`), so canonical
  text is runnable and custom renders keep calls working. A keyword that matches
  no named parameter (it goes into `**kwargs`) is left alone.
- Allowed at top level: imports, functions (incl. async), and literal
  constants `NAME = <literal>` / `NAME: T = <literal>` (anything
  `ast.literal_eval` accepts). Everything else is rejected with a clear error.

## Layout

```
catalog/index.json                       generated; the interface for future tools
catalog/<category>/<pattern_id>/         version 1
catalog/<category>/<pattern_id>@v2/      version 2, and so on
    pattern.yaml  impl.py  test_impl.py
```

`<pattern_id>` is the id without its category: `search.binary_search.iterative`
lives in `catalog/search/binary_search.iterative/`.

## Adding a pattern

**From scratch**

```bash
pcat new text.truncate.word_boundary     # scaffolds the folder with templates
# edit impl.py, test_impl.py and pattern.yaml (summary, behavior, owner)
pcat fingerprint text.truncate.word_boundary --write
pcat index
pcat validate text.truncate.word_boundary
```

**From existing code** — copies the function, every top-level helper it calls
(transitively) and the imports they use; comments are kept. Repeat `--function`
when a pattern exports several functions; the first is the entry point:

```bash
pcat add path/to/module.py --function top_words --id text.top_words.counter
pcat add auth.py --function hash_password --function verify_password --id auth.password.x
# write real tests in test_impl.py, fill in behavior, then:
pcat index && pcat validate text.top_words.counter
```

`pcat add` also copies every literal constant those functions use. If a used
module-level name is anything else (e.g. `PATTERN = re.compile(...)`), it fails
and names it; move that value into the function or make it a literal.

A pattern that imports third-party packages lists them in `pattern.yaml` as
`requires: ["pyjwt>=2.8,<3"]` (metadata only; it does not affect the
fingerprint and appears in `index.json`). Add the same requirement to the
`catalog` extra in `pyproject.toml` (a test checks this), and start the test
file with `pytest.importorskip(...)` so it skips cleanly where the library is
missing.

The templates deliberately fail validation (failing test, `TODO` fields) until
you finish them. Rules for `impl.py`: only imports, functions and literal
constants at top level (no classes); the entry point is named in `entry_point`.

Other commands:

| Command | Purpose |
|---|---|
| `pcat canonical <file.py> [--entry NAME] [--no-annotations]` | print canonical form |
| `pcat fingerprint <id> [--write]` | print / store fingerprint |
| `pcat validate [<id>…] [--skip-tests] [--base REF]` | run all checks |
| `pcat index` | regenerate `catalog/index.json` |
| `pcat show <id>` | metadata + rendered code |
| `pcat render <id> --names f0=find_user v0=users` | render with your own names |
| `pcat find <file.py>` | which pattern (if any) each top-level function in a file is |
| `pcat migrate-fingerprints` | recompute all fingerprints after a rules change (see below) |
| `pcat mine <path>… --out DIR` | find repeated function/fragment shapes; report coverage (see Mining) |
| `pcat promote <fn-id> --report DIR/report.json --id <id>` | turn a mined function cluster into a pattern |

A bare `<id>` means its highest version; use `<id>@v<N>` for a specific one.

## Review workflow

- **One pattern per pull request.** CI (`.github/workflows/validate.yml`) runs
  `pytest tests/`, `pcat validate`, and on PRs `pcat validate --base
  origin/<base>` which fails if any already-approved version changed.
- **CODEOWNERS** requires review from the owning team for `catalog/`.
- **Merged to `main` = approved.** There is no separate approval state.
  Protect `main` (require PRs, passing `validate`, and code-owner review).

To change the reviewers, edit `CODEOWNERS`: replace the placeholder
`@platform-team` with a real team such as `@your-org/platform-engineering`
(GitHub ignores owners that do not exist). You can add narrower lines per
category, e.g. `/catalog/retry/ @your-org/sre`.

### Other CI systems

The workflow is a few shell commands after checkout with full history:

```bash
pip install -e ".[dev,catalog]"
pytest tests/
pip install -r docs/catalog-review/requirements.txt && pytest docs/catalog-review/variants
pcat validate
pcat validate --skip-tests --base origin/main     # pull requests only
```

Port them to GitLab CI, Jenkins, Buildkite, etc. as-is. Use Python 3.11 in CI
(see `KNOWN_GAPS.md` on Python versions).

## Versioning

Approved patterns are **immutable**. Editing `impl.py` of an existing version
changes its fingerprint and fails check 4, and in CI the `--base` check fails on
*any* byte change to an approved `impl.py` (even a comment). To change code or
behavior:

1. Copy `catalog/<category>/<pattern_id>/` to `<pattern_id>@v2/` and set
   `version: 2`; make the change; `pcat fingerprint <id>@v2 --write`.
2. In the old version set `status: deprecated` and `replaced_by: <id>` (or
   `<id>@v2`). Only `status` and `replaced_by` may change on an approved version.
3. `pcat index`, `pcat validate`, open a PR.

Comment-only or docstring-only edits do not change fingerprints (they pass
check 4), but they are still rejected by `--base` for approved versions.

### Changing the canonicalization rules

A rule change can alter fingerprints of untouched patterns, so it is explicit:

1. Change `src/pcat/canonical.py` and bump `CANONICAL_VERSION`.
2. Run `pcat migrate-fingerprints`: it recomputes every fingerprint, rewrites
   the changed `pattern.yaml` lines, regenerates `index.json` and prints an
   `id / old / new` table for the PR description.
3. In CI, `--base` accepts the changed fingerprints only because
   `CANONICAL_VERSION` went up and every approved `impl.py` is byte-identical.

## Validation checks

`pcat validate` reports one line per problem, tagged with its check number:

1. `pattern.yaml` matches the schema (unknown keys are errors); `id`/`version` match the folder
2. `impl.py` parses and contains only imports, functions and literal constants at top level
3. `entry_point` exists in `impl.py`
4. stored `fingerprint` equals the computed fingerprint
5. no two active patterns share a fingerprint
6. no two active variants of one family have identical `behavior`
7. deprecated patterns have a `replaced_by` that resolves to another pattern
8. `test_impl.py` exists and passes (each pattern in its own pytest process)
9. idempotence: `canonicalize(render(canonical, name_map)) == canonical`
10. `catalog/index.json` is up to date
11. every `guards` entry holds on the pattern's own code (see [Deviation linter](#deviation-linter-pcat-lint))
12. `requires` matches the imports (v5.1): every third-party module `impl.py` imports is covered
    by a `requires` entry and every entry is imported (standard library exempt). Where a
    distribution's import name differs, a built-in table covers common cases (`pyjwt` → `jwt`,
    `pyyaml` → `yaml`, …) and `import_names: {dist: module}` in `pattern.yaml` overrides it. An
    application's own package is not a requirement: list it in `catalog/catalog.yaml` as
    `first_party: [myapp]`

Plus `immutable` problems when `--base` is given.

## Mining: finding candidate patterns

```bash
pcat mine path/to/repo another/repo --out mine-report --jobs 4
open mine-report/report.html          # or read mine-report/report.json
pcat promote fn-1a2b3c4d5e6f --report mine-report/report.json --id auth.create_token.jwt
```

`pcat mine` canonicalizes every function (top-level, methods, nested, async) on
its own and computes a **shape fingerprint**: the canonical form with literal
values blanked (`0`, `""`, `b""`; `True`/`False`/`None`/`...` kept). Functions
with the same shape form a **cluster** (`fn-…`), split into exact sub-groups;
blocks inside functions (`for`, `while`, `try`, `with`, `if`, `match`) are
clustered the same way as **fragments** (`fr-…`). Clusters are ranked by
`(occurrences − 1) × nodes`. The report also shows **catalog coverage**: mined
functions that exactly match a pattern (covered) or only its shape
(near-covered).

Defaults skip tests, generated files, vendored/build directories and trivial
functions; each filter has a switch (`--include-tests`, `--include-generated`,
`--no-skip-dirs`, `--include-trivial`, `--min-nodes 0`, `--exclude GLOB`).
Results are cached in `.pcat-cache/` and identical for any `--jobs`.
`pcat promote` creates a pattern from a function cluster's representative (or
`--member N`) through the same flow as `pcat add`; it does not approve anything.
Run it from the directory where you ran `pcat mine`.

`scripts/benchmark.py` mines requests, Flask and FastAPI at pinned tags; see
[`docs/benchmarks/v2-results.md`](docs/benchmarks/v2-results.md) for what it found.

## Serving the catalog to coding agents (MCP)

`pcat serve` runs an [MCP](https://modelcontextprotocol.io) server over stdio
with three tools:

| Tool | What it does |
|---|---|
| `search_patterns(request, limit=5)` | BM25 search over pattern metadata; returns matches above a calibrated threshold, or an empty list ("no reviewed pattern fits") |
| `get_pattern(id, names=None)` | the pattern's code rendered with your names, with a `# pcat: <id>@v<N>` marker above each public function, plus `requires`, `exports`, `usage`, version and status (deprecated patterns carry a warning) |
| `check_code(code, pattern_id=None, context=None, file_path=None)` | per function: `covered` (matches a pattern), `near` (same structure, other literals) or `none`, plus advisory inferred provenance; with `pattern_id` or a `# pcat:` marker, the deviations from that pattern (codes as in `pcat lint`) and a diff. For a snippet, pass the file's import lines (or the whole file) as `context`, or its repository-relative `file_path` (read only inside the repository given by `pcat serve --repo`, default the working directory); otherwise unresolved names are listed, rules depending on them are skipped (`skipped_rules`) and `resolution` is `partial` |

The server also sends instructions telling the agent to search before writing
common application code, use a fitting pattern and keep its marker, then call
`check_code` with the pattern id and fix every high-severity deviation unless the
request requires it (then it adds a `# pcat-allow` line with the reason).

```bash
pip install -e ".[mcp]"          # in the environment that runs the server
pcat search "hash a password before storing it"   # same search from the shell
```

**Claude Code** (from the application repository):

```bash
claude mcp add pcat -- pcat serve --catalog /path/to/pcat
# or share it with the team via .mcp.json:
claude mcp add --scope project pcat -- pcat serve --catalog /path/to/pcat
```

**Other MCP clients** (Claude Desktop, IDE plugins, …): add a stdio server:

```json
{
  "mcpServers": {
    "pcat": {"command": "pcat", "args": ["serve", "--catalog", "/path/to/pcat"]}
  }
}
```

Use the absolute path of the `pcat` executable if the client does not run in
the environment where it is installed. `--log calls.jsonl` appends one JSON
line per tool call.

**Suggested line for the application repository's `CLAUDE.md`:**

> Before writing common application code (auth tokens, passwords, pagination,
> HTTP retries, config loading, rate limiting, CSV import), use the pcat tools:
> `search_patterns`, then `get_pattern` if one fits; run `check_code` on the result.

**Measured (v3, `docs/benchmarks/v3-mcp.md`):** search returned the right pattern
first for 35/35 development and 35/35 held-out requests; 2 of 15 held-out
unrelated requests got a match anyway. With the server connected, Claude Code
searched in 160/160 runs, fetched the right pattern in 140/140 and produced the
reviewed pattern exactly in 122/140 (87%; 0 of 135 without the catalog in v2.1).
Most misses were adaptations to the request (xlsx input, pandas, narrower retries).

## Deviation linter (`pcat lint`)

Code that came from a pattern carries a marker, which `get_pattern` writes above
the entry point and every export:

```python
# pcat: http.get_with_retry.requests@v1
def fetch_with_retry(url, ...):
```

`pcat lint` finds marked functions (and, advisory only, unmarked functions that
look derived from a pattern) and reports **what** changed, in your names:

```bash
pcat lint src/ --catalog /path/to/pcat                 # text, includes inferred functions
pcat lint src/ --catalog /path/to/pcat --format github --changed-since origin/main
```

```
client.py:27: PC100 high: `get_with_retry` no longer handles `requests.ConnectionError`
  (it catches requests.Timeout); the reviewed pattern must catch it [guard must_catch] [fails]
```

| Code | Deviation | Severity |
|---|---|---|
| `PC100` | a reviewed guard is violated (see below) | high |
| `PC101` | exception type removed from or narrowed in an `except` | high |
| `PC102` | `raise` or validation branch (`if …: raise`) removed (high); the same check raising a different exception (medium) | high/medium |
| `PC103` | library swapped: a required library dropped or replaced (high), a new third-party library (medium), only standard-library modules changed (low) | high/medium/low |
| `PC104` | broad `except` (`Exception`, bare) added | medium |
| `PC105` | call removed | medium |
| `PC106` | private attribute or `_name` access added | medium |
| `PC107` | signature changed (parameter added/removed, default changed) | medium |
| `PC108` | call added | low |
| `PC109` | literal value changed (not covered by a guard) | low |
| `PC110` | other structural change (never on a line that has another deviation) | low |
| `PC111` | with `--changed-since`: the marker was removed but the function still looks derived from the same pattern | high |

The exit code is 1 when an **unapproved** deviation of **marked** code is at or
above `--fail-on` (default `high`; `never` always exits 0), or a marker names an
unknown pattern. Inferred findings never fail. `--include-inferred` defaults to on
for text output and off for `json`/`github`. Renaming never counts as a deviation.

**Approving a deviation (v4.1):** write the reason in a comment directly above
the function's marker or `def`, with the function's current hash (shown next to
every deviation by `pcat lint` and `check_code`): one code per line, reason after
`--`, at least 10 characters.

```python
# pcat-allow: PC100 #3f9a1c2e -- this API only treats timeouts as transient; connection errors must fail fast
# pcat: http.get_with_retry.requests@v1
def fetch_with_retry(url, ...):
```

The hash is the first 8 hex characters of the function's canonical fingerprint,
so comments and renames keep it, but any code change makes the approval
**stale**: it approves nothing until someone re-approves the new code (v4
approvals without a hash are stale too; the message shows the line to write).
With `--changed-since REF` every approval is **confirmed** (the same line, code
and hash existed at `REF`: it was reviewed when it merged) or **proposed** (new
in this change). A proposal approves nothing until a human confirms it:

```bash
pcat approvals check --repo OWNER/REPO --pr 42    # needs GITHUB_TOKEN; exit 1 while waiting
```

An approver confirms by submitting an **approving review** of the pull request's
latest commit, or a **comment containing `/pcat approve`** posted after that
commit. A new commit needs a new confirmation. Approvers are listed in
`.pcat/approvers.yaml`:

```yaml
approvers: [alice, bob]   # GitHub usernames
codeowners: true          # also anyone CODEOWNERS lists for the changed file (users, not teams)
allow_author: false       # true lets the PR author confirm their own proposals
```

`allow_author: true` is **solo-developer mode**: it weakens the guarantee (nobody
else looked at the deviation) and is meant for development only. This repository
uses it because it has one developer. The command prints every waiting proposal
and who may confirm it, then fails until each is confirmed and no unapproved
deviation remains. `docs/ci/pcat-approvals.yml` runs it on `pull_request`,
`pull_request_review` and `issue_comment`, so a review or `/pcat approve`
comment re-runs the check without a new commit. Agents using the MCP server may
*propose* approvals (with the hash and a reason) and are told to say that a
human must confirm them. Make `pcat-approvals` a required check in branch
protection, or a red check can still be merged. Pull request #1 in this
repository is a demo left open: it fails until the owner confirms its proposal.

Replaying the v4 agent samples with the v4.1 rules (addendum in
`docs/benchmarks/v4-linter.md`): all 20 HTTP samples are now flagged high for
dropping 429 from the retry statuses (v4: low), and 25 of 140 would fail CI
(v4: 12).

## Research history

How the design was tested, phase by phase (specs in `docs/specs/`, results in
`docs/benchmarks/`). Research harnesses live in `experiments/lib/pcatlab`, driven by `scripts/`.

### Variance experiment: how differently does an LLM write the same thing?

`experiments/variance/` measures the problem the catalog exists to solve. For 8
everyday tasks (JWT creation, password hashing, pagination, HTTP retry, env
config, token bucket, CSV import, FastAPI create-user) it generates 20 samples
per condition, each in a fresh context, and counts structurally different
answers with the canonicalizer and shape fingerprints:

- **A** — the same prompt 20 times; **B** — 5 paraphrases × 4;
  **C** — paraphrases plus a reference implementation (simulating a catalog lookup)

```bash
python scripts/variance.py generate --run-id main --conditions A,B   # needs ANTHROPIC_API_KEY or `claude`
python scripts/variance.py analyze --run-id main
python scripts/variance.py reference --run-id main                   # pick C references from B
python scripts/variance.py generate --run-id main --conditions C
python scripts/variance.py analyze --run-id main
```

Results and the write-up: [`docs/benchmarks/v2.1-variance.md`](docs/benchmarks/v2.1-variance.md).

### Application catalog review (v2.2)

The variance experiment showed the model follows whatever reference it is given,
so application patterns are chosen by a person, not taken from samples.
[`docs/catalog-review/v2.2-comparison.md`](docs/catalog-review/v2.2-comparison.md)
compares cleaned, tested variants for each of the 8 experiment tasks (JWT,
password hashing, pagination, HTTP retry, env config, token bucket, CSV import,
FastAPI create-user) with security notes and a recommendation. The owner records
decisions in `docs/catalog-review/choices.yaml` (now `status: final`), and Part 2
turned seven of them into catalog patterns (FastAPI create-user is deferred until
patterns can contain classes). The comparison ends with a coverage check: none
of the 135 v2.1 condition-B samples already matched its chosen pattern.

```bash
pip install -r docs/catalog-review/requirements.txt   # PyJWT, requests, SQLAlchemy, FastAPI
pytest docs/catalog-review/variants                   # skips modules whose library is missing
python scripts/catalog_review_doc.py                  # regenerate the comparison from the code
python scripts/catalog_coverage.py --condition B      # v2.1 samples vs the catalog patterns
```

### Realistic simulation (v5)

`docs/benchmarks/v5-open-source.md` repeats the experiment on three open-source
applications (CTFd, healthchecks, LNbits), each with its own catalog under
`experiments/v5/catalogs/<app>/` (house patterns plus the 7 generic ones), brief
requests, and agents working inside the repository (144 runs, baseline vs pcat).
Agents with the server found the right pattern every time, but where similar code
already sits in the repo the baseline copied it just as well; the catalog decided the
outcome where the code existed nowhere else (12/12 vs 2/12). Every headline number
from v2 to v5, with the rule set it was measured under and what is safe to claim, is
in `docs/benchmarks/summary.md`.

**Guards** are the properties a reviewer cared about, declared per pattern in
`pattern.yaml` (metadata only; validation check 11 requires each to hold on the
pattern itself). Kinds: `must_catch`, `must_call`, `must_not_call`,
`must_not_import`, `must_raise` (with `names`), `min_value`/`max_value` (with
`target`, a constant or parameter default, and `value`) and `must_include` (with
`target` and `values`: a collection that must still contain them). Names resolve
through the file's imports (any alias) and its own top-level definitions, which count
as `<module>.<name>`: a guard on `lnbits.decorators.KeyChecker` holds both for code
importing the class and for code inside `lnbits/decorators.py`; an unqualified name
(`KeyChecker`) matches either, and `.method` matches any call of that method. With
`match: any`, a `must_catch`/`must_call`/`must_raise` guard holds when one of its
names is present (e.g. sibling flows that each raise their own house exception):

```yaml
guards:
- kind: must_catch
  names: [requests.ConnectionError, requests.Timeout]
  reason: connection errors and timeouts are transient and must be retried
- kind: min_value
  target: MIN_ITERATIONS
  value: 600000
- kind: must_include
  target: RETRY_STATUSES
  values: [429, 500, 502, 503, 504]
- kind: must_raise
  names: [app.errors.ConfirmTokenInvalid, app.errors.ResetTokenInvalid]
  match: any
```

**Measured (v4, `docs/benchmarks/v4-linter.md`):** replayed on the 140 v3 agent
samples, none of the 122 unchanged ones is flagged above low and all 18 changed
ones get a named deviation (the 6 narrowed HTTP retries `PC100` high). Rerunning
the 3 affected tasks with the v4 server, no sample shipped an unapproved
high-severity deviation (v3: 12 of 60); most were approved with a reason rather
than fixed, so reviewers should read `# pcat-allow` reasons critically.

**CI for client repositories:** `docs/ci/pcat-lint.yml` is a reusable GitHub
Actions workflow that installs pcat from the catalog repository and runs
`pcat lint --format github --changed-since origin/<base>` on pull requests, so
deviations appear as annotations on the diff.

**Unmarked copies (v5.2, `docs/benchmarks/v5.2-unsafe-neighbour.md`):** code an agent
copied from a flawed neighbour carries no marker, so the default check never fails it. The
opt-in `pcat lint --changed-since <base> --fail-on-inferred-guards` also fails guard
violations (`PC100`) of unmarked code that matches a pattern with similarity >= 0.75. On
v5.2's data it caught every copied flaw (3/3) but failed 2 correct runs of 108 and 5 of
4,031 untouched app functions, so treat it as a strict, noisier gate. With the catalog
served, no agent copied the planted flaw (0/54; 3/54 without it).

**Required check or not (v5.1, `docs/benchmarks/v5.1-linter.md`):** on v5's 144 in-repo
runs the v5.1 linter fails no correct code (v5: 5 false or over-strict failures, all
fixed). Make `pcat lint --changed-since <base> --fail-on high` (marked code only) a
required check; keep `--include-inferred` advisory: on untouched app code 75 of 90
sampled medium/high inferred findings were false positives.

### Unsafe neighbour (v5.2)

`docs/benchmarks/v5.2-unsafe-neighbour.md` plants a flawed sibling (a guard violation such
as `==` instead of `fullmatch`, a 7-day token, `remote_addr` instead of `get_ip()`) next to
each of 18 tasks in the three v5 apps: with the catalog served no run inherited the flaw
(0/54), without it 3/54 did, always by renaming the neighbour into the missing function.

## Tools outside this package

Out-of-process tools read **only `catalog/index.json`**: `{"canonical_version": N,
"patterns": [...]}`, where each entry has `id, version, title, category,
variant_of, behavior, status, fingerprint, path, summary, entry_point, requires,
exports, keywords, use_when, usage` (sorted by id and version; `use_when` and
`usage` may be null). A tool that fingerprints code must use the same rules
version. The catalog's internals can change without breaking these tools.
In-package commands (`validate`, `mine`, `serve`, `lint`) also read pattern folders.

## Further reading

- `docs/getting-started.md` — the 30-minute walkthrough; `docs/releasing.md` — install extras, PyPI steps
- `docs/pitch/` — pitch material for engineering leaders: one-pager, deck (`deck.pptx`, `deck.pdf`),
  5-minute demo script, FAQ, 4-week pilot plan, and `claims.md` (every number, its source and caveat)
- `CHANGELOG.md`, `PROJECT_BRIEF.md` — what each phase added; the project's context
- `CLAUDE.md` — handoff and invariants for future sessions
- `DECISIONS.md` — every assumption made so far
- `KNOWN_GAPS.md` — limitations and suggested fixes
- `docs/specs/` — phase specs (`v1-catalog.md`, `v1.1-canonicalizer-fix.md`, `v2-miner.md`,
  `v2.1-variance-experiment.md`, `v2.2-app-catalog.md`, `v3-mcp-server.md`, `v4-linter.md`,
  `v4.1-human-approval.md`, `v5-…`, `v5.1-…`, `v5.2-…`, `v6-productize.md`, `v7-pitch.md`)
- `docs/benchmarks/` — results per phase and `summary.md` (all headline numbers)
- `docs/ci/pcat-lint.yml` — reusable workflow that lints client pull requests
