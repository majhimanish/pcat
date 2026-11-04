# Decisions

Assumptions and choices made while building v1 where the spec
(`docs/specs/v1-catalog.md`) was ambiguous or silent. Newest sections at the
bottom; add to this file whenever you make a call the spec does not dictate.

## Repository and packaging

1. **Repo root is the `pattern-catalog/` root.** The spec's layout shows a
   `pattern-catalog/` folder; this git repository (`pcat`) *is* that folder.
2. **Python 3.11+, CI pinned to 3.11.** `ast.unparse` output can change between
   Python versions, so CI uses one version. Seed fingerprints were checked to be
   identical on 3.11, 3.12 and 3.13.
3. **`pytest` is a runtime dependency**, because `pcat validate` runs pattern
   tests. The `[dev]` extra exists (as the spec requires) and also lists pytest.
4. **`pytest` with no arguments runs `tests/` only** (`testpaths`). Every
   pattern test imports a module named `impl`, so pattern tests cannot share one
   pytest session; `pcat validate` runs them one folder at a time.
   `tests/test_seed_catalog.py` runs `pcat validate` on the real catalog, so a
   plain `pytest` still exercises every seed's tests.
5. setuptools build backend, `src/` layout, console script `pcat = pcat.cli:app`.

## Catalog layout and identity

6. **Folder = `catalog/<category>/<id without category>`**, with `@v<N>` suffix
   only for version ≥ 2: `search.binary_search.iterative` v1 is in
   `catalog/search/binary_search.iterative/`, v2 in `…/binary_search.iterative@v2/`.
   Ids need at least two segments (`retry.with_exponential_backoff` is valid).
7. **Uniqueness is per (id, version).** Versioning reuses the id, so "unique id"
   means unique id+version; the folder rule enforces it.
8. **References:** `id` or `id@vN`. On the CLI a bare id means the highest
   version; `replaced_by` may use either form.
9. **Root discovery:** `--root`, else `PCAT_ROOT`, else the nearest directory at
   or above the current directory that contains `catalog/`.

## Canonicalization

10. **Entry point.** `canonicalize(source, entry_point=None)`: when no entry
    point is given (e.g. `pcat canonical` without `--entry`) the first top-level
    function is the entry point.
11. **Output order:** sorted imports, then `f0` (entry point), then helpers in
    source order (v1.1: literal constants go between imports and functions, #54). So moving a helper above or below the entry point does not
    change the fingerprint, but reordering helpers does.
12. **Imports** are split to one name per statement (`import a, b` → two
    statements; same for `from x import a, b`), deduplicated by their unparsed
    text and sorted by that text, with `from __future__` first.
13. **Docstrings:** *all* leading string-constant statements of the module and
    of every (nested) function are removed, not just the first, so that
    canonicalization is idempotent. An emptied function body becomes `pass`.
14. **One flat scope per top-level function.** Bindings anywhere inside it
    (nested functions, lambdas, comprehensions, `except … as`, walrus, `match`
    captures, `nonlocal`) share one `v0, v1, …` numbering. It is a consistent
    bijective rename, so behaviour is preserved.
15. **"Never rename builtins" = never rename free names.** A name is renamed iff
    it is bound in the function. A local that shadows a builtin (`list = …`) is
    renamed; every unbound use of a builtin is not. This avoids depending on the
    version-specific `dir(builtins)` list.
16. **Never renamed:** free/global names, names declared `global`, names bound by
    imports (top level or inside functions), `self`, `cls`, dunder names,
    attribute names and keyword-argument names at call sites.
    *(v1.1: keyword names at calls to the pattern's own functions are renamed,
    #51; `global` names that refer to constants/functions are renamed, #57.)*
17. ~~Keyword names at call sites are never renamed, even for calls to helpers in
    the same snippet.~~ *Superseded in v1.1 by #51.*
18. **Decorators, default values and signature annotations of a top-level
    function** are treated as module scope (as Python evaluates them): only
    function names are renamed there.
19. **Placeholder collisions are errors.** A name that would not be renamed but
    looks like a placeholder (`f3`, `v0`), e.g. an imported `f1`, is rejected.
20. **Numbering order:** parameters in signature order (positional-only, regular,
    `*args`, keyword-only, `**kwargs`), then a pre-order depth-first walk of the
    body following `ast` field order (a `match` mapping's `**rest` capture is
    numbered after its key captures).
21. **Annotation stripping** (`keep_annotations: false`) runs before renaming:
    parameter/return annotations removed, `x: T = v` becomes `x = v`, bare
    `x: T` is dropped (empty bodies get `pass`).
22. **Rejected constructs:** anything at top level other than imports, functions
    and a module docstring; classes inside functions; duplicate top-level
    function names. Async functions are allowed. *(v1.1: literal constants are
    allowed at top level, #53.)*
23. **Name map keys:** `fN` for functions, `vM` for locals of `f0`, `fN.vM` for
    locals of helper `fN`. The spec's flat example (`"v0": "items"`) cannot
    represent per-function numbering, so helper locals are qualified. `f0.vM` is
    accepted as an alias of `vM` when rendering.

## Metadata schema

24. Required: `id, version, title, summary, category, behavior, entry_point,
    owner, status`. Optional with defaults: `variant_of: null`,
    `replaced_by: null`, `keep_annotations: true`, `fingerprint: null`.
25. `version` must be an integer ≥ 1 (no coercion from strings/bools);
    `category` must equal the first segment of `id`; `entry_point` must be an
    identifier; `behavior` is a mapping of strings to scalars (str/int/float/
    bool/null), possibly empty.
26. `replaced_by` is required when `status: deprecated` and forbidden when
    `active`.
27. `fingerprint: null` is schema-valid (a pattern being written) but fails
    check 4.

## Index

28. **`index.json` uses the stored `fingerprint` from `pattern.yaml`** (the
    approved value), not a recomputed one; check 4 guarantees they agree on a
    valid catalog. Entries are sorted by `(id, version)`; `path` is the folder
    relative to the repo root (POSIX slashes); JSON uses `sort_keys=True,
    indent=2`, ASCII escaping, `\n` line endings and one trailing newline.

## Validation

29. Checks 5 and 6 consider **active** patterns only (a deprecated v1 and its
    v2 may legitimately share behavior).
30. Check 7: `replaced_by` must resolve to a pattern other than itself; a bare id
    equal to the pattern's own id requires a higher version to exist.
31. Check 8 runs `python -m pytest -q -p no:cacheprovider --rootdir=<folder>
    --confcutdir=<folder> test_impl.py` with `PYTHONDONTWRITEBYTECODE=1`, cwd =
    the pattern folder, 300 s timeout per pattern, using the same interpreter as
    `pcat`.
32. Check 9 uses the name map extracted from `impl.py`.
33. `pcat validate <id>…` runs per-pattern checks only for the selected
    patterns, reports cross-pattern problems (5, 6, 7) only when they involve a
    selected pattern, and always runs check 10.
34. **Extra (beyond spec): `pcat validate --base <git-ref>`.** For every
    pattern version present at the ref, `id, version, behavior, entry_point,
    keep_annotations, fingerprint` must be unchanged and the pattern must not be
    removed. Otherwise anyone could edit `impl.py` and re-run
    `pcat fingerprint --write`, defeating immutability. CI runs it on PRs.
35. **Extra: `--skip-tests`** for fast local iteration.
36. Problems print as `<id>@v<N>: [check <n>] <message>`, one per line, on
    stderr, followed by a count; exit code 1.

## CLI

37. `pcat new <id>`: `entry_point` = second id segment (`binary_search` for
    `search.binary_search.iterative`); `variant_of` = first two segments when the
    id has three or more; `owner: "@platform-team"`. Templates intentionally fail
    validation (test raises, fingerprint unset) until completed.
38. `pcat add`: copies function source verbatim (comments kept) with every
    transitively referenced top-level function, in source order, plus only the
    imports whose names they use (star imports always kept); other top-level
    statements are ignored. `summary` comes from the docstring's first line;
    fingerprint is written immediately; test template fails until replaced.
39. `pcat fingerprint --write` replaces the `fingerprint:` line in place (or
    appends one) so comments and key order in `pattern.yaml` survive.
40. `pcat show` prints the validated metadata re-serialized as YAML, a `---`
    line, then the rendered code (docstrings/comments are not part of it).
41. `pcat render`: accepts the spec's syntax (`--names f0=a v0=b`) and repeated
    `--names`. Placeholders not mentioned keep their real names. It refuses name
    maps that make names collide (detected by re-canonicalizing the output).
42. `pcat find`: reads only `catalog/index.json`. For each top-level function it
    extracts the function + helpers + used imports (as `add` does), computes the
    fingerprint with and without annotations, and reports every index entry
    matching either (so patterns with `keep_annotations: false` match). Exit code
    0 whether or not anything matches.
43. Errors are printed as `error: <message>` on stderr with exit code 1.

## Seed patterns

44. `binary_search.*` return *some* index for duplicates; midpoint is
    `low + (high - low) // 2`. The recursive variant recurses on index bounds via
    a helper (no slicing), to show helper numbering (`f1`).
45. `merge_sort.recursive` returns a new list, stable, accepts any sequence.
46. `group_by.dict_of_lists` keeps first-seen key order and input order within
    groups; works on unsorted input (unlike `itertools.groupby`).
47. `retry.with_exponential_backoff` has no family (`variant_of: null`); keyword-
    only options, `sleep` injectable (default `time.sleep`), delay before retry n
    is `min(max_delay, base_delay * factor ** (n - 1))`, no jitter, re-raises the
    last error, non-matching exceptions propagate immediately.
48. `slugify.ascii` uses NFKD + ASCII-ignore, so characters without an ASCII
    decomposition (e.g. `ß`, CJK) are dropped, not transliterated.
49. Owner of every seed is the placeholder `@platform-team`.

## Process

50. Work is committed on the session's designated branch
    (`claude/new-session-woele0`) rather than `main`; merging it to `main` is
    the first "approval".

## v1.1 — canonicalizer fixes (`docs/specs/v1.1-canonicalizer-fix.md`)

51. **Keyword arguments at calls to snippet functions** are renamed to the
    callee's placeholder when the call's `func` is a bare name that resolves to a
    top-level function of the snippet (not shadowed by a local or a local
    import), including recursive calls. All functions are analysed before any
    renaming, so definition order does not matter. `render` does the reverse.
52. **Positional-only parameters are not matched by keywords** (deviation from
    the spec's list "positional, positional-only, keyword-only"). In Python a
    keyword never binds a positional-only parameter; with `**kwargs` it lands in
    kwargs under its literal name (`def b(a, /, **kw)`; `b(1, a=2)` gives
    `kw == {"a": 2}`), so renaming it would change behaviour.
53. **Literal constants:** a top-level `NAME = value` or `NAME: T = value` with a
    single plain name target, where `ast.literal_eval(value)` succeeds. Rejected
    with a clear error: other assignments (non-literal values, tuple targets,
    chained `A = B = 1`, augmented assignment, bare `NAME: T`), and a name bound
    twice. Constants are renamed `c0, c1, …` in source order; name-map key `cN`.
54. **Constants are placed right after the imports, in source order, before all
    functions** (deviation from "constants keep their source position relative
    to functions"). With v1's entry-point-first ordering, keeping positions puts
    a function above a constant its default uses (`def f(limit=LIMITS[1])` moved
    into an earlier slot), and canonical and rendered text then fail with
    `NameError` at import. Constants are dependency-free literals, so hoisting
    them is always safe; it also makes the fingerprint independent of where in
    the file constants sit.
55. **`pcat add` / `extract_function`** copy every literal constant used by the
    function or its helpers (transitively), in source order, as their source
    segment (inline comments after the value are dropped). A used module-level
    name bound by anything else (non-literal assignment, class, loop target,
    rebinding, `A += 1`) fails with a message naming it. Helpers and constants are
    now found by real free-name analysis, so a local that shadows a module name
    no longer pulls that module name in.
56. **Placeholder namespace now includes `cN`**: a free name like `c0` that is
    not renamed is rejected, as `f0`/`v0` were.
57. **`global NAME`** inside a function now resolves `NAME` through the module
    map, so `global COUNT` + `COUNT += 1` becomes `global c0` + `c0 += 1`.
    Before, global names were never renamed (no constants existed, so this only
    changes code that declared a top-level function name `global`).
58. **`CANONICAL_VERSION = 2`** lives in `canonical.py`. v1 rules = 1.
59. **`index.json` is now an object** `{"canonical_version": N, "patterns":
    [...]}` (spec: "write `canonical_version` at the top level"). A bare list
    (v1 format) is read as `canonical_version: 1`. The entries are unchanged.
60. **`pcat migrate-fingerprints`** is all-or-nothing (any load/canonicalization
    error aborts before writing), rewrites only the `fingerprint:` line of
    changed files, regenerates the index, and prints every pattern as
    `id@vN  old  new  changed|unchanged` with full fingerprints plus a summary.
61. **`validate --base` rules:** `impl.py` of an approved version must be
    byte-identical to the base (stricter than v1: comment-only edits now fail
    under `--base`, though they still pass check 4); a changed `fingerprint` is
    allowed only if `impl.py` is unchanged and `CANONICAL_VERSION` is greater
    than the version recorded in the base's `catalog/index.json` (1 if absent or
    in v1 format). The base version is read from the catalog's index rather than
    from `src/` so it works for catalogs whose code lives elsewhere. An `impl.py`
    change is reported once (not also as a fingerprint change).
62. **Multi-problem errors** from library calls (e.g. a failed migration) are
    printed as one `error: …` line per problem.
63. **Changed v1 test expectations** (none deleted; each still asserts the same
    rejection): `X = 1` / `CACHE = {}` as examples of forbidden top-level
    statements became `X = make()` / `CACHE = dict()` because literals are now
    legal; error-message substrings now say "only imports, function definitions
    and literal constants"; `test_index_format` reads `doc["patterns"]`; the
    `--base` rewritten-fingerprint test now matches the more precise
    "impl.py changed" message.
64. **Seed migration:** 0 of 6 seed fingerprints changed under rules v2 (no seed
    calls its own functions with keywords or uses constants); verified on
    Python 3.11 and 3.13.

## v2 — pattern miner (`docs/specs/v2-miner.md`)

65. **v1.1 CI** (run #2 on `d8a5889`) had passed on GitHub before v2 work began;
    nothing to fix.
66. **Modules:** `shape.py` (literal blanking, `SHAPE_VERSION = 1`), `miner.py`
    (discovery, per-file analysis, cache, clustering, coverage, promotion target),
    `report_html.py` (renderer). Existing canonicalization is untouched; the miner
    reuses `canonical`'s internal scope/rename helpers read-only for fragments.
67. **Mined function canonicalization:** decorators removed, the function unparsed
    alone as a module and run through `canonical.analyze` with itself as entry
    point and `keep_annotations=True`. Qualified names follow Python's
    `__qualname__` (`Cart.describe.<locals>.label`); kinds are `function`,
    `method` (directly in a class body) and `nested` (inside a function); a
    `top_level` flag marks functions directly in the module body.
68. **`node_count`** is the number of AST nodes of the shape tree (the `def` node
    or fragment statement included). It drives `--min-nodes`,
    `--min-fragment-nodes` and the score; all members of a cluster share it.
69. **Trivial body:** after docstring removal, exactly one statement that is
    `pass`, `return` (with any value), `raise` or `...`.
70. **A function that cannot be canonicalized on its own** (class inside it,
    placeholder-like free name) is counted under `functions_filtered.cannot_canonicalize`;
    its file is not skipped.
71. **File discovery:** only `*.py`; directories in the skip list are pruned
    during the walk and their files are not counted. `files_seen` counts the rest;
    `files_mined = files_seen − skipped`. Skip reasons: `test`, `excluded`,
    `generated`, `parse_error`.
72. **Tests:** a path component `tests`/`test`, or a file named `test_*.py`,
    `*_test.py`, `conftest.py`. Functions named `test_*` in other files are not
    filtered (see KNOWN_GAPS).
73. **`--exclude GLOB`** is matched (`fnmatchcase`, `*` crosses `/`) against the
    path relative to its input and against the file name.
74. **Extra flags so every filter can be switched off:** `--include-generated`,
    `--include-trivial`, `--no-skip-dirs` (plus `--min-nodes 0`), and
    `--min-fragment-nodes`, `--cache-dir`, `--no-cache`.
75. **Generated files are always analyzed and flagged by the worker**; skipping is
    decided afterwards, so the cache does not depend on `--include-generated`.
76. **`settings` in the report excludes `jobs` and cache options**: the spec
    requires identical bytes for `--jobs 1` and `--jobs 4`, and neither changes
    results.
77. **Inputs are recorded as given** (POSIX form), not resolved, so reports do not
    embed absolute machine paths when relative inputs are used. Git info
    (`commit`, exact-match `tag`) is recorded only when the input is the top level
    of a work tree; a subfolder of a repository gets `git: null`.
78. **Clusters:** members sorted by (input, path, line, column, qualname) and given
    a 0-based `index`; `exact_groups` sorted by size, then first member; clusters
    sorted by score desc, then id, then full shape fingerprint. Per-cluster fields
    (shape text, node count) are not repeated on members.
79. **Coverage** uses every pattern with valid metadata (any status): exact = the
    whole pattern's canonical fingerprint or its entry point mined like any
    function; shape = the same two after literal blanking. Covered wins over
    near-covered; percentages are of mined functions, rounded to 2 decimals.
    A cluster's `catalog_matches` lists pattern keys with `exact` if any member
    exactly matches that pattern, else `shape`.
80. **The miner reads pattern folders (via `catalog.py`) rather than only
    `index.json`**, because the index has no shape or entry-point fingerprints.
    CLAUDE.md invariant 3 now says in-package commands may do this; out-of-process
    tools must still use only `index.json` (adding these fingerprints to the index
    is in KNOWN_GAPS).
81. **Fragments** belong to the innermost enclosing function (the walk does not
    enter nested functions, classes or lambdas). Candidates include `try*` on
    Python 3.11+. An `if` that is the only statement of its parent `if`'s `else`
    is treated as `elif` (this also matches `else:` + nested `if`). The
    whole-body check ignores a leading docstring.
82. **Fragment renaming** uses the enclosing function's flat scope (as in
    canonicalization): parameters and locals become `v0…` in order of first
    appearance in the fragment; keyword names at call sites are not renamed.
83. **Redundancy suppression:** a fragment cluster is dropped if some other cluster
    with more nodes and the same occurrences has, for every member, a member whose
    (line, column) span strictly contains it. Containment chains collapse to the
    largest cluster.
84. **Cache:** one JSON file per analyzed file content in `.pcat-cache/` (relative
    to the working directory), named `<sha256>-c<CANONICAL>-s<SHAPE>-m<MINER>-fr<N>.json`,
    written atomically. `MINER_VERSION` (now 2) versions the per-file format; it
    was bumped when fragments were added. The cache is never pruned.
85. **`--jobs N`** uses a process pool (`map`, chunksize 8) whose order-preserving
    results are merged exactly as in the sequential path.
86. **Promote:** representative = members of the largest exact sub-group(s), then
    shortest relative path, then path, then lowest line. `--member` takes the
    0-based `index` from the report. Refused: fragment clusters (with the
    location to extract by hand), methods, nested/non-top-level functions, a
    missing source file (paths resolve like the recorded input, i.e. relative to
    the directory `pcat mine` ran in), and a source file whose SHA-256 differs
    from the mined `file_hash`. Then it runs the same code as `pcat add`.
87. **HTML** uses `<details>` rows (no JavaScript) and inline CSS with a
    phone layout; it is rendered from the JSON text just written.
88. **Benchmark:** tags all existed (no fallback). The script also runs a
    library-only pass (`--exclude 'docs_src/*' --min-occurrences 2`) because the
    default run is dominated by FastAPI tutorial copies; timings are from a cold
    cache with `--jobs` = CPU count.
89. **Changed tests:** none of the v1/v1.1 tests changed. `tests/conftest.py` sets
    `collect_ignore = ["fixtures"]` because miner fixtures include files named
    `test_*.py` and `conftest.py`.
90. Parse-error messages come from the running Python and can differ between
    versions; reports are byte-identical per interpreter version.

## v2.1 — LLM output variance experiment (`docs/specs/v2.1-variance-experiment.md`)

91. **Backend: headless Claude CLI** (`claude -p`, v2.1.316). `ANTHROPIC_API_KEY` was
    not set, so the API backend was skipped; the CLI was found and worked. Model
    requested: `claude-sonnet-5-5`. The CLI exposes no temperature setting, so
    `temperature` is recorded as `null` (CLI default). The recorded `model` is
    the one with the most output tokens in the CLI's `modelUsage` (the CLI also
    makes a small housekeeping call to a Haiku model).
92. **Isolation per sample:** one `claude -p` process per sample, run in a new
    empty temporary directory, `--no-session-persistence`, `--strict-mcp-config`
    (no MCP servers), all file/shell/web/agent tools disallowed (every sample
    took 1 turn), and `CLAUDE_ADDITIONAL_DIRECTORIES` /
    `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD` removed from the environment
    so no CLAUDE.md is loaded. A probe confirmed no instruction files were
    seen. Not removable: Claude Code's own system prompt and a small
    harness-injected context (user e-mail, commit-attribution guidance). Up to
    8 processes ran in parallel; they share only the server-side prompt cache
    of that system prompt.
93. **Logic lives in `src/pcat/variance.py`** (importable and tested like the
    rest of the package); `scripts/variance.py` is a thin driver.
94. **Snippet fingerprinting** uses the unchanged canonicalizer and shape rules
    after an experiment-only normalization: `if __name__ == "__main__":` blocks
    and a module docstring are dropped; other top-level statements that are not
    imports, functions or literal constants (`app = FastAPI()`,
    `ctx = CryptContext(...)`, `SECRET = os.getenv(...)`) are moved in order into
    a synthetic last function `_module_level`, and the names they bind are
    renamed `g0, g1, …` everywhere (except where a function binds the same name
    locally) and declared `global` there. So a global's name does not affect
    the fingerprint, as with locals.
95. **Validity:** invalid reasons are `syntax_error`, `contains_class` (any class,
    as the spec says), `no_function` (added: code with no top-level function),
    `cannot_fingerprint` (canonicalizer error after normalization) and
    `generation_failed`. Metrics use valid samples only.
96. **Supplementary metric (not in the spec):** the smoke run showed every
    `fastapi_create_user` sample defines Pydantic models, against the
    instruction. Prompts were frozen, so the spec's rule stands; separately,
    "classes removed" shape metrics cover valid samples plus samples whose only
    problem is top-level classes, with those classes dropped and their names
    treated like renamed globals.
97. **Extraction:** the first fenced block tagged `python`, `py`, `python3` or
    untagged; otherwise the whole response.
98. **Descriptors:** entry point = first top-level function in source order;
    parameter count includes `*args`/`**kwargs`; function count = top-level
    functions. Import sets use the root module of every import anywhere in the
    code (`from jwt import encode` → `jwt`; relative imports ignored);
    "third-party" = roots not in `sys.stdlib_module_names`.
99. **Metrics:** effective shapes = `exp(Shannon entropy)` with natural log,
    rounded to 2 decimals; top-shape share rounded to 4.
100. **Sampling:** samples numbered from 1; sample *n* in conditions B and C uses
     paraphrase `((n − 1) mod 5) + 1`. Retries: 3 retries (4 attempts) with 5,
     10, 20 s waits; permanent failures are stored with `status: failed`.
101. **References:** chosen from condition B of run `main` by the spec's rule; the
     most common shape's ties go to the shape containing the lowest sample
     number, likewise for exact sub-groups. The reference file is the sample's
     extracted code verbatim (comments and docstrings included). Reference match
     rate compares shape fingerprints; an exact-match rate is also reported.
102. **Runs kept:** `runs/smoke` (2 samples per task and condition, the spec's
     smoke test) and `runs/main`. `pcat mine` reports per condition use
     `--min-occurrences 1` with trivial functions kept, no cache.
103. **Supplementary similarity metrics (not in the spec):** exact shape equality
     counts `x + n` vs `x + int(n)` as different shapes, so analysis also reports
     the median pairwise similarity of shape texts
     (`difflib.SequenceMatcher(autojunk=False).ratio()`) and the number of
     near-shape groups: single-linkage clusters of samples with similarity
     ≥ 0.90. The threshold is a judgment call, chosen before looking at
     condition C; the spec's metrics stay the headline.
104. **CLI artifacts are kept, not regenerated.** Two `jwt_create` C samples are
     the CLI answering as its `/security-review` skill instead of writing code;
     they are stored as generated and count as `syntax_error`. Re-rolling them
     would select on the outcome. 31 samples report 2–3 turns although all tools
     were disallowed; their responses are ordinary code, so they are kept.
105. **References fall back to sample 01.** Every condition-B shape was unique for
     seven tasks, so the spec's tie-break chose B sample 01 there (02 for
     `fastapi_create_user`, whose only valid samples are 02 and 06). The write-up
     notes that the references are effectively arbitrary.
106. **Committed run data:** samples, `analysis.json`, `table.md` and the `pcat
     mine` reports (JSON and HTML) for runs `smoke` and `main`; nothing is
     regenerated after commit. Analysis of a full run takes about 1.5 minutes,
     mostly the pairwise similarity metric.
107. **Write-up averages** ("mean effective shapes") use only task/condition cells
     with at least 10 valid samples, which excludes `fastapi_create_user` A and B.

## v2.2 Part 1 — application catalog review (`docs/specs/v2.2-app-catalog.md`)

108. **Part 1 only.** `docs/catalog-review/choices.yaml` did not exist, so this
     session prepared the comparison and stopped; Part 2 waits for `status: final`.
109. **Grouping:** the 40 A+B samples per task (including those invalid in v2.1
     because of classes) were classified by regex features for each design
     decision, then checked by reading the shortest sample of each group. Two
     regex counts were wrong and were redone: `env_config` (5 schema-parameter
     loaders, not 21) and `paginate_query` (13 legacy `Query`, 27 `select`).
110. **Representative = shortest sample of the group** (a proxy for "cleanest");
     the comparison names it per variant ("cleaned from sample …").
111. **Variant module names are globally unique** (`jwt_minimal_claims`,
     `bucket_bool`, …) because all variant tests run in one pytest session with
     rootdir-based imports.
112. **Variant rules:** catalog-ready (the unchanged canonicalizer accepts every
     file), stdlib preferred, secrets/URLs/clocks/`sleep`/randomness/transports
     passed in, lines ≤ 100 characters for phones, code blocks about 40 lines
     (`csv_text_stream` is 45). Defaults such as `timedelta(minutes=15)` are
     allowed in signatures (only module-level constants must be literals).
113. **Security parameters:** HS256 secret ≥ 32 bytes; scrypt N=2^17, r=8, p=1
     with `maxmem` 256 MiB (p ≤ 16 when verifying); PBKDF2 600,000 iterations
     (≤ 10,000,000 when verifying); page size ≤ 100; `Retry-After` capped at
     `max_delay`; CSV `max_rows` 10,000 and email ≤ 254 characters with no
     regex (the samples' regex is quadratic: 0.7 s on 16 KB); FastAPI password
     12–128 characters.
114. **Class-free FastAPI** interprets "validated dict input" as per-field
     `Annotated[..., Body(...)]` parameters (what the 3 class-free samples did):
     FastAPI still validates them and documents them in OpenAPI. Routes are added
     by `register_routes(app_or_router)` because catalog rules forbid a
     module-level `router`; repository and hasher dependencies fail closed.
115. **Recommendations against the majority:** `env_schema_loader` (5/40) because
     a catalog pattern must be reusable unchanged; `paginate_page_dict` (5/40)
     to standardise response shapes; `defer` for FastAPI to avoid spreading
     non-idiomatic code. The rest follow the majority.
116. **Dependencies:** `docs/catalog-review/requirements.txt` with version ranges;
     variant tests use `pytest.importorskip`; pytest `testpaths` include the
     variants; CI installs the requirements and runs them in their own step.
117. **`scripts/catalog_review_doc.py`** regenerates the comparison from the
     variant files and never overwrites an existing `choices.yaml`.

## v2.2 Part 2 — application catalog patterns

118. **Owner's choices** (`choices.yaml`, final): recommendations accepted except
     `password_hash` → PBKDF2. The owner asked to keep all proposed ids, but the
     proposed `auth.password.scrypt` named the wrong algorithm; asked, the owner
     chose `auth.password.pbkdf2`. FastAPI is deferred.
119. **Multi-function patterns (fixes the KNOWN_GAPS entry):** `extract_function`
     takes one name or a list; each name is a root for the same transitive
     helper/constant/import collection, and a single name gives exactly the old
     output. `pcat add` accepts `--function` repeatedly; the first is the entry
     point (`entry_point`, `f0`), the others are exported alongside. Simplest
     design: no schema change (other exported functions are helpers to the
     canonicalizer, which already includes every top-level function).
     `migrate-fingerprints` confirmed 0 of 6 fingerprints changed.
120. **Pattern files:** each pattern was created with `pcat add`; when the result
     was canonically identical to the documented variant file, that file
     (module docstring and comments included) was kept as `impl.py` — the
     fingerprint is the same either way.
121. **Owner notes for PBKDF2:** `hash_password` refuses fewer than 600,000 (or more
     than 10,000,000) iterations; the count is stored in the hash; `ITERATIONS`
     (default) and `MIN_ITERATIONS` (floor) are separate constants so the default
     can be raised; `verify_password` still accepts lower legacy counts, and a
     third function `needs_rehash(stored, iterations=ITERATIONS)` says when to
     re-hash after a successful login (also True for malformed or foreign hashes).
122. **`requires`:** optional list of pip requirement strings (name, extras,
     version specifiers; no markers or URLs; one entry per distribution). It is
     metadata only (not in the fingerprint, not an immutable field, so ranges can
     be widened later). `index.json` includes a sorted `requires` key only for
     patterns that declare some, so existing entries and their test stay
     byte-identical; consumers should read `entry.get("requires", [])`.
123. **`catalog` extra** in `pyproject.toml` = union of all `requires`;
     `tests/test_catalog_requires.py` fails if a pattern's requirement is missing
     from it. CI installs `.[dev,catalog]`.
124. **Clean skips:** third-party pattern tests start with `pytest.importorskip`.
     pytest then exits 5 ("no tests ran"); check 8 treats exit 5 as a pass only
     when the summary reports skips and no failures or errors, so `pcat validate`
     and `pytest` pass without the extra. A test file with no tests still fails.
125. **Changed test expectations (catalog grew by design):** five tool tests
     hard-coded the 6-seed catalog. They now derive counts from the catalog; the
     index-format test checks a seed entry; "catalog contains exactly the seeds"
     became "all seeds present with their v1 fingerprints" (pinned values, equal
     to the v1 commit). The Part 1 guard test that required choices to equal the
     recommendations now only requires a valid documented option.
126. **Behavior maps and families:** each pattern's `variant_of` is its id's first
     two segments (e.g. `auth.password`), so later alternatives (scrypt) become
     variants of the same family; `behavior` records the decisions from the
     comparison (algorithm, return shape, limits).
127. **Coverage check:** `scripts/catalog_coverage.py` compares v2.1 samples with
     each pattern as a whole snippet (v2.1 normalization) and by main function
     (miner-style), shape and exact, plus the closest similarity. Result for B:
     0 of 135 matched (closest 0.39–0.85); A and C also 0. Sanity-checked: a
     pattern matches itself, and a renamed/re-commented copy matches by shape.

## v3 — MCP server (`docs/specs/v3-mcp-server.md`)

128. **Metadata authorship.** `keywords`, `use_when` and `usage` for all 13
     patterns were written from each `impl.py`, its tests and `summary` only,
     without opening `tasks.yaml`. The same author had read the v2.1 tasks in
     earlier phases, so the dev set is contaminated in spirit; the held-out set is
     the real retrieval measurement.
129. **Field rules.** `exports`: identifiers, unique, not the entry point, each a
     top-level function in `impl.py` (check 3). `keywords`: 5–15 non-empty,
     unique case-insensitively. `use_when`/`usage`: optional non-empty strings
     (multi-line `usage` is written as a YAML literal block). All are metadata
     only: not in fingerprints and not immutable, so they can be improved on
     approved versions; `--base` still rejects any `impl.py` change.
130. **Index format.** Every entry now always has `summary`, `entry_point`,
     `requires` (sorted, `[]` when none — supersedes 122's "only when non-empty"),
     `exports`, `keywords`, `use_when`, `usage` (`null` when unset), so the
     server and later the linter never need pattern folders for search.
     `canonical_version` and the existing keys are unchanged.
131. **Search.** BM25 with k1 = 1.5, b = 0.75 and Lucene's smoothed idf
     `ln((N - df + 0.5) / (df + 0.5) + 1)` (always positive). Document = id
     tokens, title, summary, category, keywords, use_when, entry point, exports.
     Query terms are de-duplicated. Tokenizer: lowercase, split on anything not
     `a-z0-9`, fixed stop-word list (function words plus "function", "python",
     "code", "helper", "implement", "make", "create", which appear in nearly
     every request), then one ordered suffix rule (`ations`, `ation`, …, `s`;
     words ending in `ss` untouched; stem must keep ≥ 3 characters). "get" is
     not a stop word (`http.get_with_retry`). Ties: id, then version.
132. **Threshold.** Calibrated on the 45 dev requests only: candidates are the
     midpoints between adjacent distinct top-1 scores (plus 0 and above the
     max); accuracy = positives whose top-1 is right *and* ≥ threshold plus
     negatives whose best score is below it; among equally accurate candidates
     the median is taken, rounded to 2 decimals. Result 9.08 (dev accuracy 1.0;
     best negative 5.76, worst positive 12.41). A test pins the constant to the
     value the calibration reproduces.
133. **Serving reads folders.** `get_pattern` needs the code and `check_code`
     needs per-function fingerprints, neither of which is in the index, so
     `serving.py` (in-package, like `validate`/`mine`) loads patterns through
     `catalog.py`; search uses only `index.json` (invariant 3 updated).
134. **`get_pattern`.** Accepts `id` or `id@vN`; renders with the existing
     `render` and rejects unknown name keys (listing the valid ones) and names
     that collide (re-canonicalizing the rendered code must give the pattern's
     canonical text). Deprecated versions are returned with a `warning`.
135. **`check_code`.** Reuses the miner's per-function analysis (no fragments).
     A function is `covered` when its exact fingerprint equals a catalog entry
     point's or export's, `near` when only its shape fingerprint does. Only
     active patterns; private helpers are not matched on their own. Syntax
     errors return `{"error": …, "functions": []}`.
136. **Server.** FastMCP from the `mcp` SDK (`mcp>=1.2,<2`, tested with 1.30),
     stdio only. `mcp_server.py` is the only module importing `mcp`; tool errors
     (`PcatError`) become MCP tool errors. Instructions are generated from the
     active patterns' categories and titles. `--catalog` accepts a repo root or
     its `catalog/` folder and is resolved before anything else, so the server
     works from any working directory. The log is JSONL with a result
     *summary* (ids, scores, statuses), not full results, plus a timestamp
     (the log is evaluation output, not a generated catalog file).
137. **Dev negatives.** 10 common tasks I wrote with no pattern
     (`experiments/mcp/dev_negatives.json`), including a FastAPI endpoint.
138. **Held-out set.** 7 positive needs and 15 negative needs, one sentence each,
     written from the task descriptions (not metadata). Each request came from a
     fresh `claude -p` (claude-sonnet-5-5) in an empty folder with all tools
     disabled, 5 per positive need and 1 per negative; `clean_request` keeps the
     first paragraph without quotes or a "Request:" label. A usage-limit
     interruption failed 36 of 50 on the first run; `--resume` regenerated only
     the failed ones. Committed (`5a68b6e`) before evaluation.
139. **No improvement round.** Held-out top-1 was 100%, above the spec's 80% bar,
     so tokenizer and metadata were left as calibrated on dev.
140. **End-to-end setup.** v2.1's `CliGenerator` plus `--mcp-config` (one config
     per sample pointing at `pcat serve --catalog <repo> --log <sample log>`),
     `--strict-mcp-config` (already in the generator), `--disable-slash-commands`
     (v2.1 saw skill output) and `--allowedTools` for the three pcat tools only;
     stdin is `/dev/null` so `claude -p` never waits for input. 20 samples per
     task cycle its 5 held-out requests; 20 negatives cycle the 15 negative
     requests. claude-sonnet-5-5, 6 parallel jobs.
141. **End-to-end scoring.** *Correct retrieval* = `get_pattern` called with the
     task's pattern id (any version). *Pattern match* = every pattern function
     (entry point + exports) appears as covered/near for that pattern in
     `check_code` of the final code block (shape = covered or near; exact =
     covered). *Library agreement* = the code imports every `requires` library,
     or none of the catalog's third-party libraries for stdlib patterns.
     *Similarity* = v2.1 shape-text similarity of the whole snippet to the
     pattern's `impl.py`. Each miss gets the first applicable outcome:
     did_not_search, search_missed, found_but_not_fetched, fetched_other_pattern,
     fetched_but_changed. Whether a fetched-but-changed sample adapted for the
     request or rewrote unasked, and whether a negative's pattern use was a
     fitting sub-task, was judged by reading the code (recorded in
     `docs/benchmarks/v3-mcp.md`).
142. **`mcp` extra in CI.** CI installs `.[dev,catalog,mcp]`; server tests skip
     cleanly without `mcp` (`importorskip`). The stdio test starts `pcat serve`
     as a subprocess from another directory.

## v4 — deviation linter (`docs/specs/v4-linter.md`)

143. **Marker placement.** `get_pattern` puts `# pcat: <id>@v<N>` directly above
     the entry point *and every export* (`hash_password`, `verify_password`,
     `needs_rehash` all get one), since exports are reviewed public functions
     whose guards (e.g. `hmac.compare_digest` in `verify_password`) should be
     able to fail CI. The marker must be in the contiguous comment block directly
     above the function (above its decorators); a blank line breaks the block.
     A marker without `@vN` means the latest active version. Malformed `# pcat:`
     lines and a second marker on one function are reported, not fatal. Markers
     work on methods and nested functions too. The response also has a `marker` key.
144. **Inference measure.** v2.1's difflib ratio between the function's shape
     text (miner's per-function canonicalization: the function alone, literals
     blanked) and each catalog entry point's and export's shape text; the best
     match wins (ties: pattern id, version, function). Only active patterns.
145. **Inference calibration** (`scripts/lint_eval.py calibrate`,
     `experiments/linter/inference_calibration.json`). Derived: in each of the
     140 v3 positive samples, the function most similar to each function of the
     pattern it fetched (one-to-one), 200 functions. Not derived: every
     non-trivial function of the 40 v2.1 FastAPI A/B samples and the 20 v3
     negative samples, except functions `check_code` marks covered/near (the
     two PBKDF2 sub-task uses are really derived), 187 functions. Trivial
     functions (single return/pass) are skipped. Rule as in v3 (decision 132):
     maximise accuracy, take the median of the best range, round to 2 decimals.
     Result **0.56**: 199/200 derived found, 1/187 not-derived flagged (a
     hand-rolled PBKDF2 `hash_password` in a v2.1 sample, 0.583). The labelling
     uses similarity itself, so the derived scores are an optimistic upper bound.
146. **Guard format.** `guards:` is a list of `{kind, names | target+value,
     function?, reason?}`. `names` are dotted names resolved through the file's
     imports (`from hmac import compare_digest as cd` -> `hmac.compare_digest`)
     or `.method` for a method on any value; names compare by first and last
     segment, so `requests.exceptions.Timeout` equals `requests.Timeout`.
     `function` (default: entry point) must be the entry point or an export.
     Guards are metadata only: not in fingerprints, not immutable, not in
     `index.json` (the index-format test stays unchanged; `pcat lint` reads
     pattern folders through `catalog.py` like `serve`).
147. **`max_value` added** next to the spec's `min_value`: several reviewed
     limits are caps (`MAX_PAGE_SIZE`, `MAX_ROWS`, `MAX_ITERATIONS`, `max_delay`)
     that must not go *up*. Same rules as `min_value`.
148. **Guard semantics.** Checked on the *unit*: the function plus same-file
     top-level functions it calls (transitively), the constants it reads and the
     imports it uses (`codeunit.py`; never fails on classes or scripts in the
     file). `must_catch`: some handler catches the type, a broad handler
     (`except:`, `Exception`, `BaseException`) or a builtin superclass counts;
     third-party superclasses (`requests.RequestException`) are not known.
     `must_raise`: a `raise T`/`raise T(...)` exists. `must_call`/`must_not_call`:
     any call resolving to the name (a `raise T(...)` target is not a call).
     `must_not_import`: an import the unit uses or contains has that module or a
     submodule as origin. `min_value`/`max_value`: the target is a parameter of
     the function (its default, a literal or a file constant) or a file constant;
     an absent target is "not checked" (other codes report removed checks).
149. **Guards were written** from the v2.2 security notes and each pattern's
     code, for the 7 application patterns only (seeds have none), and committed
     before Part F. Caveat: the v3 write-up (`docs/benchmarks/v3-mcp.md`) already
     described the misses (HTTP narrowed to timeouts, a private SQLAlchemy
     attribute, pandas), so the HTTP `must_catch` guard was not written blind.
     The v3 miss samples themselves were not opened while writing guards.
150. **Check 11:** every guard holds on the pattern's own code (all results ok,
     every min/max target found). Runs with `--skip-tests` too (no execution).
151. **Deviation analysis compares facts, not text.** Both sides are units
     (decision 148). Calls, exception types and raised types are compared as
     resolved names; statements are compared as keys with locals -> `_v`, unit
     functions -> `_f`, constants -> `_c`, imports -> origin, annotations and
     docstrings removed, so renaming (including import aliases) never produces a
     deviation. Statement keys feed a `difflib` alignment for PC109/PC110.
152. **Alignment.** Helpers pair by name, then in source order; a pattern helper
     the user calls but does not define is assumed to be provided elsewhere and
     left out of the comparison. Entry-point parameters pair by name, then by
     equal position. Constants pair by name, then by order among same-typed
     values. Locals map by canonical numbering when the function's structure is
     identical, else by walking matching statements in parallel; import
     bindings map by origin. Used only for messages and the diff.
153. **Code semantics.** PC101: a type the pattern catches is caught by no user
     handler (broad handlers and builtin superclasses count). PC102: pattern
     raises are matched to user raises by type and the shape of the guarding
     `if` test, then by type; unmatched ones are reported (bare `raise` counts).
     PC103: a `requires` library is no longer used, or a pattern import root was
     dropped *and* a non-stdlib root was added (adding a library alone is not a
     swap; roots count only when used outside annotations). PC104: more broad
     handlers than the pattern. PC105/PC108: resolved call names missing/new
     (calls to locals are ignored). PC106: `_name` attributes or imported/free
     `_names` not in the pattern (the file's own top-level privates are fine).
     PC107: parameters added/removed, kind changed, `*args`/`**kwargs`
     changed, or a default whose shape changed; a default differing only in a
     literal is PC109. PC109: constant values, literal-only defaults, and literals
     in statements of the same shape (only when the function's statement
     alignment ratio is >= 0.8, so rewrites do not produce nonsense pairs).
     PC110: one per function summarising unexplained added/missing statements,
     plus added/removed helpers.
154. **Guards take precedence** for the same fact: a violated `must_catch`
     replaces PC101 for that type, `must_call` replaces PC105, `must_not_call`
     PC108, `must_not_import` PC103; any value guard (passing or not) replaces
     PC109 for its target, since the reviewer bounded that value. A guard
     violation is reported even when the code otherwise matches the pattern's
     shape exactly (a lowered security constant is the point of guards).
155. **Messages and diff** use the user's names (functions, parameters,
     constants, locals where aligned, import aliases); guard messages keep the
     reviewer's spelling of library names. Output is sorted by severity, code,
     line, message. The diff (pattern in the user's names vs the user's code,
     comments and docstrings removed) is capped at 80 lines.
156. **`pcat lint` scope.** Files come from the miner's discovery with default
     filters (tests, generated files and skip-dirs excluded). Every function
     (top-level, methods, nested) is considered. A marked function is compared
     with the pattern function of the same name, else the most similar public
     function of that pattern. Inferred functions are compared with the
     function inference picked. `--catalog` (repo root or its `catalog/`)
     defaults to `--root`/the nearest catalog, like `serve`.
157. **Failing.** Exit 1 iff (a) a marked function has an unapproved deviation
     at or above `--fail-on`, or (b) a marker names an unknown pattern (marked
     code that cannot be checked must not pass silently); `--fail-on never`
     always exits 0. Malformed markers, invalid or stale approvals, unparsable
     files and markers of deprecated patterns are warnings.
158. **Approvals** apply per code to the function whose comment block holds
     them and approve every deviation with that code there. Invalid approvals
     (no reason, reason < 10 characters, several codes, unknown code) approve
     nothing. Stale = a valid approval whose code has no deviation.
159. **`--changed-since REF`:** lines from `git diff --unified=0 REF -- file`
     (new side; a pure deletion touches the line after it); untracked files
     count as fully changed. A function is selected when its span, including
     its marker/approval comment block, touches a changed line.
160. **Formats.** `text` (default) shows deviations and, when an unapproved
     medium/high deviation exists, the diff (`--no-diff` hides it). `json` is the
     full deterministic report. `github` prints workflow commands: `error` for
     failing deviations, `warning` for others and inferred ones, `notice` for
     approved ones. `--include-inferred` defaults to on for text, off otherwise.
161. **PC110 explanation.** A changed region is not reported as PC110 when every
     new statement in it is already explained by a specific deviation (narrowed
     handler, added broad except, private access, added call) and it replaces at
     most as many pattern statements, or all removed statements are explained.
162. **`check_code(code, pattern_id=None)`.** v3 keys (`functions` with name,
     line, status, pattern, pattern_function; `summary`; `legend`; the syntax
     error result) are unchanged; v4 adds `marker` and advisory `inferred`
     (pattern, function, similarity, likely_derived) per function, plus
     `deviations` (one analysis per marked function, and with `pattern_id` the
     best-matching function for each public function of that pattern: the entry
     point always, exports only when similarity >= INFERENCE_THRESHOLD),
     `unapproved_high`, `next_step` and, for unknown markers, `problems`.
     Approvals in the code are honoured as in `pcat lint`. An unknown
     `pattern_id` is a tool error listing the known ids (like `get_pattern`).
163. **Instructions** now say: keep the marker; after writing code from a
     pattern call `check_code` with the final code and the pattern id; fix every
     high-severity deviation unless the request explicitly requires it, and then
     add `# pcat-allow: <code> -- <reason>` above the function's marker.
164. **Replay method.** Each v3 sample is linted with `check_code(code,
     pattern_id)` (the analysis `pcat lint` uses), where `pattern_id` is the
     task's pattern if the tool log shows it was fetched (all were), standing in
     for the marker the v3 code does not have. Outcome labels (exact match vs
     fetched-but-changed) come from `experiments/mcp/e2e_results.json`.
     "Switched library" for CSV = imports pandas/openpyxl/polars/xlrd and no
     longer imports `csv` (4 samples, all pandas).
165. **Feedback run.** `scripts/mcp_eval.py`'s v3 job builder and runner are
     reused unchanged (same held-out requests, cycling, prompt, repo note, model
     and CLI flags), loaded as a module with its output directory redirected to
     `experiments/linter/feedback/`; only the server (now v4) differs. "High
     shipped unapproved" = the final code, analysed with its markers (or the
     pattern id), has an unapproved high deviation. Approvals counted are those
     in the final code. v3 baselines for these tasks come from the replay.
166. **v3 erratum.** The v3 write-up said both pagination misses read
     `_order_by_clauses`; the replay showed only sample 12 does (sample 17 adds a
     `tiebreaker` parameter). A dated erratum was added to
     `docs/benchmarks/v3-mcp.md`; no v3 data changed.

## v4.1 — human approval and linter fixes (`docs/specs/v4.1-human-approval.md`)

167. **Approval hash** = first 8 hex characters of the function's exact
     fingerprint as the miner computes it (the function canonicalized on its own,
     current rules = v1.1/v2, decorators dropped). So comments (markers,
     approvals), docstrings, formatting and names never change it, but any code
     change in the function does. Helpers and module constants are not part of
     it: changing `RETRY_STATUSES` does not invalidate an approval on the
     function. Hashes compare case-insensitively (stored lower-case).
168. **Stale approvals** approve nothing and are warnings: no hash (v4 format;
     the message prints the line to write with the current hash), a different
     hash, or (as in v4) a code that no longer occurs.
169. **`check_code` treats approvals as proposals.** In the agent's context
     nothing has been reviewed, so a matching approval is `proposed`
     (`approved: false`), excluded from `unapproved_high`, counted in
     `awaiting_human_confirmation`; `next_step` tells the agent to say a human
     must confirm it. Each analysis has `hash` and an `approval_template`.
170. **Deliberately changed v4 tests:** `test_lint.py` (valid approval, stale,
     GitHub format) now write approvals with the hash and expect the state in the
     output (`approved (confirmed)`); `test_serving.py` expects a code approval
     to be `proposed`, and the instructions to show `#<hash>` and to say a human
     must confirm.
171. **Approval states.** With `--changed-since REF`, an approval is `confirmed`
     when `REF`'s version of the file has a well-formed approval with the same
     function (qualname), code and hash (the reason may differ), `proposed`
     otherwise; `stale` as in 168. Without a base ref every current approval is
     `confirmed` and the output says so (text note, JSON `approval_states`).
     A `proposed` approval approves nothing in `pcat lint`, so its deviation still
     fails; only `pcat approvals check` can turn it into `proposed-confirmed`.
172. **`pcat approvals check` is the whole pull-request gate.** It lints the
     changes since the merge base of the PR base and `HEAD` (marked code only),
     reads reviews/comments, marks proposals confirmed, re-lints with them
     applied and fails on waiting proposals *or* remaining failing deviations.
     A confirmation is PR-wide: one valid confirmation by a user who may confirm
     a proposal's file confirms that proposal (all proposals are visible in the
     PR at the head commit). It warns if the checked-out commit is not the PR head.
173. **What counts as a confirmation.** A user's latest decisive review
     (APPROVED / CHANGES_REQUESTED / DISMISSED) whose `commit_id` is the head
     commit, if APPROVED; or a comment matching `/pcat approve` (as a word, case-
     sensitive) created after the head commit's committer date. Committer dates
     can be set by the author; the review route is the stronger one. Logins
     compare case-insensitively.
174. **Who may confirm** = `approvers` ∪ (with `codeowners: true`) the users the
     last matching CODEOWNERS rule names for the file (`.github/`, root or
     `docs/` CODEOWNERS; gitignore-like matching, simplified); teams and e-mail
     owners are not resolved. Without `allow_author`, the PR author is removed.
     The config must name approvers or enable codeowners; unknown keys are errors.
175. **Re-running on reviews and comments.** Comment-triggered runs do not show on
     the PR, and a review run shows next to the earlier failed `pull_request` run.
     So after a passing review/comment run, the workflow re-runs failed
     `pull_request` runs of `pcat-approvals.yml` for the head commit (`gh run
     rerun --failed`, needs `actions: write`); they then see the confirmation.
176. **`--changed-since` speed and nested clones.** Changed files come from one
     `git diff --name-only REF --` plus the untracked list per repository; files
     in a repository where `REF` is not a commit (e.g. gitignored clones under
     `.bench/`) are skipped with a warning; if no repository knows `REF`, it is an
     error.
177. **This repository** installs the gate (`.github/workflows/pcat-approvals.yml`,
     `.pcat/approvers.yaml` = `majhimanish`, `allow_author: true` because there is
     one developer; documented as solo-developer mode).
178. **PC111 (marker removed, high).** Only with `--changed-since REF`: a function
     whose qualname had a marker in `REF`'s version of the file, has none now,
     and infers as derived (>= INFERENCE_THRESHOLD) from the *same pattern id*.
     Checked for every function of a changed file, not only touched ones (the
     deletion is above the function). The finding (`provenance: marker-removed`)
     also lists the deviations from that pattern, but only PC111 fails; it is
     approved like any other code (`# pcat-allow: PC111 #<hash> -- reason`, a
     proposal until confirmed). A deleted function (qualname gone) or one that no
     longer infers as derived from that pattern reports nothing.
179. **`must_include`** takes `target` (constant or parameter default, resolved
     like `min_value`) and `values`; it fails when the target is no longer a
     collection or lacks a value, and (like the other value guards) replaces
     PC109 for its target. Added to `http.get_with_retry.requests`:
     `RETRY_STATUSES` must include 429, 500, 502, 503, 504.
180. **No other `must_include`.** The other application patterns have one
     collection constant, `importers.users_csv.parse` `REQUIRED_COLUMNS`
     (`name`, `email`). The v2.2 security notes for that pattern cover ReDoS, row
     limits, not echoing values and formula injection, not required columns, so
     no guard was added. `config.env.load_settings`' `secret_names` defaults to
     `()` (nothing to include) and its boolean spellings are inline literals, not
     constants. The other patterns have no collection constants or defaults.
181. **PC103 levels.** High: a library from the pattern's `requires` is no longer
     used (dropped or replaced). Medium: a third-party root the pattern does not
     use appears (whether or not something stdlib was dropped). Low: only
     standard-library roots differ (dropped and/or added). Roots count only when
     used outside annotations (decision 153).
182. **PC110 suppression.** A changed region's new statements on a line that
     carries any other deviation are not counted; a region with no such free
     statements is skipped when it replaces at most as many pattern statements
     or its removed statements are explained; a pure removal whose reported line
     carries another deviation is skipped too.
183. **Deliberately changed v4 tests:** `test_lint.py::test_fail_on_levels` and
     `::test_github_format` use a `base_delay` default change as the low
     deviation, since dropping 429 is now high; `test_deviation.py::
     test_adding_a_third_party_import_alone_is_not_a_swap` expects PC103 low for
     a stdlib import (`json`) and medium for a third-party one.
184. **Replay output.** The v4.1 replay writes `experiments/linter/replay_v4.1.json`
     (default of `replay --out`); `replay.json` stays the frozen v4 result.
185. **Demo pull request.** Branch `pcat-approval-demo` adds
     `examples/approval-demo/` (narrowed `get_with_retry` with its marker and an
     agent-style `# pcat-allow: PC100 #6db40061 -- …`), PR #1 to `main`, left open.
     Its `pcat-approvals` run failed with the proposal listed as WAITING. The PR's
     author is the owner (opened with the owner's GitHub credentials), and GitHub
     refuses self-approving reviews, so the owner confirms with a `/pcat approve`
     comment (counts because `allow_author: true`). I did not confirm it myself:
     a confirmation by the agent would defeat the purpose.
186. **CLAUDE.md** was compressed (status merged per phase, checklist folded) to
     stay at 150 lines.

## v5 — realistic simulation on open-source applications (`docs/specs/v5-open-source-simulation.md`)

187. **Apps** (`experiments/v5/apps.yaml`, pinned to release tags and commits):
     CTFd 3.8.9 (Flask, Apache-2.0), healthchecks v5.0.3 (Django, BSD-3),
     LNbits v1.6.2 (FastAPI, MIT). Rejected from the list: the FastAPI template
     (3k lines), mealie (AGPL), netbox (420k lines, class-based throughout).
     No listed FastAPI candidate fit, so two outside the list were checked:
     Netflix/dispatch (last commit 2025-09-02, not maintained) and polar (659k
     lines); LNbits fits. "Lines of Python" = all `.py` files at the tag (also
     reported without tests/migrations/docs).
188. **Mining** uses `pcat mine` defaults (tests excluded) plus excludes for
     `migrations/`, `migrations.py` (LNbits keeps migrations in files), `docs/`
     and `examples/`, run from each app's root so reports hold relative paths;
     the cache lives in `.bench/mine-cache`. Reports are reproducible
     (`scripts/v5.py mine`, checked byte-identical on a rerun).
189. **Part A** reruns v4's feedback run unchanged (same 60 held-out requests,
     prompt, model, flags, server = current v4.1 code) into
     `experiments/linter/feedback_v4.1/<task>/`; `feedback --dir` and
     `feedback-analyze --dir/--out` keep v4's `feedback/` and
     `feedback_results.json` untouched (writing to the latter is refused). The v4
     samples are re-scored under v4.1 rules into `feedback_v4.1/v4_rescored.json`;
     the v3 baseline comes from `replay_v4.1.json`. "High unapproved" counts a
     deviation covered only by a proposal as unapproved (v4.1 semantics);
     `high_not_covered_by_a_proposal` excludes those. The approval census classes
     every `# pcat-allow` line in the final code as confirmable (hash matches the
     function), stale_hash, no_hash (v4 format) or invalid.
190. **v5 catalog layout.** Each app's catalog is a catalog *root*
     (`experiments/v5/catalogs/<app>/catalog/<category>/<id>/` plus `index.json`,
     with `REVIEW.md` next to `catalog/`), so `pcat --root`, `serve --catalog` and
     `lint --catalog` work unchanged. `owner: "@v5-self-review"` marks them as
     reviewed by the agent, not the owner.
191. **House patterns:** 9 (healthchecks), 9 (CTFd), 8 (LNbits), extracted with
     `pcat add` from the pinned source, bodies verbatim. Hand-assembled when the
     extractor refuses a module-level class (healthchecks `authorize_read` and the
     two email senders import the class-using pieces from their app module; LNbits
     `require_api_key`, `check_admin` import their module-level objects). Edits: one
     relative import made absolute (LNbits `get_account_by_field`). Security
     weaknesses in house code (non-constant-time badge signature compare, JWT
     without iss/aud/jti) are kept verbatim and noted in `REVIEW.md`, since the
     patterns describe the house way that tasks are compared with.
192. **Pattern tests stub the framework and the app** (`sys.modules` fakes in each
     `test_impl.py`; Django, Flask, FastAPI and the app packages are not installed),
     so they test the pattern's logic against the stubs' contract; `requires` still
     names the framework (Django/Flask/FastAPI, PyJWT, loguru) because derived code
     uses it. `tests/test_v5_catalogs.py` runs `validate` (with pattern tests) on
     every v5 catalog and checks the generic copies are byte-identical.
193. **Skipped candidates:** class methods and classes (model methods, Pydantic
     validators, `KeyChecker`, Flask-RESTX resources, `TokenBucket.authorize_*`),
     and `checks.post_action`, whose extraction pulled in a v5 task's target.
194. **Tasks** (`experiments/v5/tasks.yaml`): per app 6 pattern tasks and 2 negatives no
     pattern covers. Pattern tasks are *sibling* (the pattern was promoted from
     another occurrence that stays in the repo: 4 in healthchecks, 5 in CTFd and
     LNbits) or *same* (the pattern is the removed function, its only occurrence,
     so the pcat condition can recover it verbatim: 2, 1 and 1). Removal
     deletes the top-level function(s) with their decorators, the comment block
     directly above and the following blank lines; callers and now-unused imports
     stay (an import of a removed name fails, as it would for a developer).
     References are the removed text (`experiments/v5/references/`).
195. **Requests** (`experiments/v5/requests.json`): one fresh no-tools `claude -p`
     (claude-sonnet-5-5) per need, prompt `pcat.v5.REQUEST_PROMPT` (brief, "usually
     under 15 words"), first paragraph cleaned as in v3. Generated once and kept as
     is: median 15 words, max 23, 38 of 84 above 15; they invent names and
     locations (e.g. `authorize_write`, a VictorOps view "in hc/front/views.py"), as
     real requests do. 20 extra retrieval needs per app (12 with an expected
     pattern, 8 negative) in `retrieval_needs.yaml`, written before generation.
196. **v5 retrieval** (`scripts/v5.py retrieval` → `experiments/v5/retrieval.json`)
     ranks each app's 8 task requests and 20 extra requests against that app's
     catalog index with the unchanged `MATCH_THRESHOLD` (9.08) and v3's metric code.
     "House vs generic" is data-driven: every request where at least one house and
     one generic pattern pass the threshold, and which one ranks first. "Short
     queries" = positives whose expected pattern ranks first but scores below 9.08.
197. **Run harness, and the shell restriction.** `scripts/v5_e2e.py` runs `claude -p`
     (claude-sonnet-5-5) in a fresh copy outside this repo under an opaque path,
     `--setting-sources project,local` (no user settings or memory), extra CLAUDE.md
     directories removed from the environment, `--strict-mcp-config`, slash commands
     off, 10-minute limit, stream-json transcript. **Deviation from the spec:**
     unrestricted shell access for unattended agents was refused by this
     environment's permission classifier ("create unsafe agents"), so runs get the
     file tools in full (Read, Edit, MultiEdit, Write, Glob, Grep, LS, TodoWrite) but
     the shell only via an allowlist of read-only commands (`git status/diff/log/
     grep/show`, `ls`, `head`, `wc`, `python -m py_compile`); no web, no subagents.
     Agents therefore cannot run the apps' test suites (the optional test metric is
     skipped) or install anything. Every transcript is scanned for paths outside the
     copy (this repo, `.bench/apps`, the references): the originals still exist on
     disk and there is no filesystem sandbox.
198. **Scoring a run.** The new function is the task's entry name among functions
     the diff added or changed, else the most similar (shape text vs the removed
     original) of the changed functions; similarity = v2.1 measure against the
     original. Pattern match = `check_code` status of that function; derivation =
     its marker or inference. `pcat lint --changed-since <baseline> --include-
     inferred` on the changed Python files with the app's catalog gives deviations
     and "would fail CI" (marked code only, or PC111). Search/read order comes from
     the transcript's tool calls.
199. **Pre-run metadata fix.** The smoke test showed every function derived from
     three CTFd patterns and two healthchecks email patterns flagged PC103 high
     ("no longer uses flask/django, which the pattern requires") because I had
     listed the framework in `requires` for patterns that never import it. Fixed
     before the full run (`requires` now lists only libraries the impl imports);
     the five smoke runs were discarded and rerun. The underlying gap (`requires`
     not checked against imports) is in KNOWN_GAPS.
200. **No scaling.** Smoke runs cost $0.08–0.16 (mean about $0.12), so 144 runs are
     estimated at about $18, under the $60 cap: 3 samples per task per condition.
201. **Usage limit during Part F.** The first full pass hit the account's 5-hour
     usage limit after 52 runs; the other 92 ended at once with "You've hit your
     5-hour limit". After the reset the runner resumed (completed runs are skipped,
     cut-off ones rerun from scratch), so every one of the 144 runs is a complete
     run. CLI cost estimate: $14.59 for the 144 completed runs, about $15.84
     including the cut-off attempts and the smoke test.
202. **Negatives metric.** "Forced a pattern" = the agent fetched a pattern and its
     new code carries a marker or matches a pattern; advisory inference alone
     ("inferred similar") is reported separately, since small helpers (regex or
     boolean parsers) score above 0.56 against `regex_match` / `parse_bool`.


## v5.1 — linter fixes for real codebases

203. **One symbol table per unit (Part A).** `codeunit.Unit` now knows the file's
     module path (`module_for_path`: the file name plus every enclosing folder with
     an `__init__.py`; a namespace package without one yields a shorter path) and
     its own top-level definitions (classes, functions, non-literal assignments).
     A same-file definition resolves to `<module>.<name>` (`lnbits.decorators.
     KeyChecker`), the same string an import of it resolves to, so the pattern side
     (which imports the class) and the code side (which defines it) agree. Without a
     module path a same-file definition stays a bare name. Imports nested in
     top-level `if`/`try`/`with` blocks (`if TYPE_CHECKING:`, `try: import ujson as
     json`) are now in the table too (before, those names were free names).
204. **Binding loose names (`deviation.bind`).** Names whose resolution is a guess
     (unknown names; same-file definitions when the module is unknown) are assumed
     to be what the other side means by the same name, or the only origin on the
     other side with that last segment. A helper one side defines and the other
     imports is compared as the imported name, not as a helper. Binding never
     touches names both sides resolve; a genuinely different class with the same
     name in another package still violates a qualified guard.
205. **Guard target matching (`codeunit.target_matches`).** Qualified targets
     compare by `name_key` as before (any alias; the defining module). An
     unqualified target (`KeyChecker`) matches a same-file definition, a builtin, or
     any import whose last segment it is (so check 11 on a pattern that imports the
     class still passes); for `must_not_call` it is strict: only the bare name or a
     same-file definition (`must_not_call: [eval]` does not match `x.eval`).
     Pattern-vs-code comparisons (PC101/PC105/PC108) keep plain `name_key`
     equality: both sides are resolved names.
206. **Display.** Messages spell same-file definitions without the module prefix
     (`adds a call to KeyChecker`, not `lnbits.decorators.KeyChecker`).
207. **Runtime roots include the file's own package** when the module is known, so
     code inside `lnbits/` that uses its own classes does not "drop" `lnbits`.
208. **Partial code (Part B).** A name the unit uses that nothing binds (no import,
     no same-file definition, not a builtin) is *unknown*. If the pattern binds the
     same name it is assumed to mean the same thing (`assumed` in the result, e.g.
     `requests -> requests` for a snippet without `import requests`); the rest stay
     unresolved. A rule whose missing item could be an unresolved name with the same
     last segment (`rq.Session` vs `requests.Session`) is skipped and listed in
     `skipped_rules`: PC100 must_call/must_catch/must_raise, PC101, PC102, PC105
     (and the paired PC108). PC103 "dropped/missing library" is skipped whenever
     unresolved names remain; a library the snippet does import is still compared.
     A call missing with nothing that could be it is still reported.
     `resolution` is `partial` when any unknown name exists (assumed or not) and
     `full` otherwise. PC110 (low) is not skipped: a differing statement is still
     shown, since it is advisory.
209. **`context` and `file_path`.** `check_code(code, pattern_id, context=…,
     file_path=…)`: `context` is the surrounding file or just its import lines; its
     top-level statements that the snippet does not redefine are merged in front of
     the snippet, so resolution (helpers, constants, imports, same-file classes) is
     the same as for the full file. A context that does not parse falls back to its
     unindented import lines. `file_path` is read only when it resolves (symlinks
     followed) to a `.py` file inside the served repository: `pcat serve --repo`
     (default: the server's working directory); it also gives the module path.
     Otherwise it is ignored with a note in `context_notes`. Full files without
     either argument behave as in v4.1 apart from Part A's resolution.
210. **`import_names` and the built-in table (Part C).** `requirements.py` maps a
     distribution to its top-level import name: `import_names` in `pattern.yaml`
     first (distribution -> module; only the first segment is used), then a small
     built-in table (pyjwt -> jwt, pyyaml -> yaml, beautifulsoup4 -> bs4, pillow ->
     PIL, python-dateutil -> dateutil, scikit-learn -> sklearn, ...), else the
     distribution name with `-` -> `_`. Names are compared after pip's
     normalization (`PyJWT`, `py_jwt` -> `pyjwt`). `import_names` is metadata only:
     not in the fingerprint and not in `index.json` (no index changes).
211. **Check 12 and first-party modules.** Check 12: every absolute import in
     `impl.py` (module level or inside functions; relative imports and
     `sys.stdlib_module_names` + `__future__` exempt) is covered by a `requires`
     entry; every entry is imported; every `import_names` key is in `requires`. An
     application's own package (`lnbits`, `CTFd`, `hc`) is first-party, not a pip
     requirement, so a catalog may list it in an optional `catalog/catalog.yaml`
     (`first_party: [lnbits]`; unknown keys are a check-12 problem). This was the
     simplest option that does not pretend the app is a distribution.
212. **Metadata fixes for check 12.** `catalog/`: none needed. v5 catalogs: 22
     patterns failed, all for the same reason — they import the app's own package
     (CTFd 8 patterns: `CTFd`; healthchecks 7: `hc`; LNbits 7: `lnbits`). Fixed by
     adding `catalog/catalog.yaml` with `first_party` to each v5 catalog; no
     `pattern.yaml`, `impl.py`, fingerprint or index changed. Deliberate test
     change: `test_requires_is_indexed_sorted_and_does_not_change_fingerprint` adds
     two requirements the impl never imports, which check 12 now reports.
213. **PC103 through the mapping.** A library swap (high) is now dropping a
     `requires` library that the pattern itself uses at run time (annotations do
     not count, as before for user code); dropping a module that is neither
     standard library nor required (e.g. first-party) is low with its own message
     instead of the mislabelled "changes standard-library modules".
214. **Guard review (Part D).** Rebuilt from the saved diffs and linted with the v5
     linter (exact reproduction: 144/144 runs, 0 differ from the saved scores),
     five guards fired in v5 (baseline and pcat, marked and inferred):
     - `auth.require_api_key` must_call `lnbits.decorators.KeyChecker` (4 functions,
       3 failing CI): **keep**. The guard is right; the code used the shared class.
       The firing was the same-module resolution bug fixed in Part A.
     - `integrations.add_url_channel` must_call `hc.front.views._get_rw_project_
       for_user` (2, advisory: the marker sat between the decorators and `def`, so
       the function was only inferred): **keep**. Same Part A bug: the helper is
       defined in the file the agent edited.
     - `security.email_confirm_token` must_raise `UserConfirmTokenInvalidException`
       (5, 2 failing CI): **fixed**. The reset-password sibling raises
       `UserResetPasswordTokenInvalidException`, which CTFd's reset view catches;
       raising the confirm exception there would be a bug. Both are CTFd's token
       exceptions, the check (`if addr is None: raise`) is identical, so the flagged
       code is as safe as the pattern. Guard now lists both with `match: any`
       (new guard option, 216); raising anything else, or nothing, still violates it.
     - `config.env.load_settings` must_raise `ValueError` on LNbits'
       `is_lnbits_version_ok` (5, advisory) and `validators.regex_match` must_call
       `re.fullmatch` on `camel_to_snake` (6, advisory): **keep**. Neither function
       derives from the pattern; inference (similarity >= 0.56) attached them. The
       guards are right for derived code; the noise is inference, recorded for Part E.
215. **No other guard changed.** No guard was loosened for any other reason.
216. **`match: any`** (schema `Guard.match`, default `all`): for must_catch,
     must_call and must_raise, the guard holds when one of its names is present; it
     reports one result (`A | B`). Validation rejects it on other kinds or with one
     name. Metadata only; not in the fingerprint or the index.
217. **PC102 for a changed exception.** When a pattern raise has no same-type raise
     in the code but the same condition (or the same unconditional position) raises
     a different exception, PC102 is reported as medium ("raises B instead of the
     pattern's A for the check `if ...`; callers that catch A will not catch it")
     instead of high "dropped". Removing the raise is still high. This is the CTFd
     reset-token case: the agent's own proposed approval said "same check kept,
     only the exception type differs".
218. **Survey scope (Part E).** Untouched app code at the pinned commits: every
     `.py` file except folders named tests/test/testing/docs/doc/migrations/alembic
     (and build/vendor folders) and files `test_*.py`, `*_test.py`, `conftest.py`,
     `tests.py`, `migrations.py`. My first pass missed LNbits' single-file
     `lnbits/core/migrations.py` (33 inferred functions, 70 medium/high findings);
     all reported numbers use the corrected scope. "Functions checked" = every
     function `pcat lint` considers (methods and nested functions included);
     every one is run through inference. Random samples of 30 use
     `random.Random(<app name>)` over the medium/high findings in file order.
219. **Fix: a method's receiver is not a parameter.** When the user's function takes
     `self`/`cls` first and the pattern function does not, the receiver is left out
     of parameter alignment and the signature comparison. Before, `get(self,
     award_id)` vs a pattern `f(user_id)` aligned `self` with `user_id` and reported
     "adds parameter `award_id`" (PC107) or "`self` is now positional".
220. **Fix: nested functions are not analyzed twice.** An inferred function nested
     inside a function that already has a finding for the same pattern is skipped:
     the outer function's unit already contains it. Before, CTFd's decorators were
     reported once for `registered_only` and again for `_registered_only`.
     Marked nested functions are still analyzed.
221. **Not fixed: inference on app code.** Most medium/high survey findings are on
     functions that do not derive from any pattern but score >= 0.56 (short CRUD
     helpers, Flask resources, decorators). That is calibration, not a bug, and the
     threshold was calibrated on v3 data; changing it would need new labeled data.
     Inferred findings are advisory and never fail CI; KNOWN_GAPS has the numbers.
222. **Fix: calls through `(conn or db)`.** A method call on `a or b` / `a if c else b`
     records `a.m` and `b.m` (named operands) as alternatives; PC105/PC108 treat a
     call matching an alternative on the other side as the same call, and guards
     check the alternatives too. Before, LNbits CRUD helpers calling `db.execute`
     were "no longer calling `.execute`" and "adding `db.execute`" against the
     pattern's `(conn or db).execute`.
223. **`.method` guard targets match any attribute call of that name.** `.fetchone`
     now matches `db.fetchone(...)` (a method on an imported object), not only calls
     on local values; for `must_not_call` this is stricter (`requests.post` now also
     violates `.post`). Deliberate behavior change; no earlier test depended on it.
224. **Survey classification.** Three verdicts: true deviation (derived code that
     really differs), debatable (a sibling of the pattern where the difference is
     legitimate or minor, e.g. LNbits CRUD helpers with positional `conn`, the house
     style, against a keyword-only pattern), false positive (the finding is wrong,
     or the function does not derive from the pattern at all). Sampled from the
     `before` survey so the effect of the Part E fixes is visible per item.
