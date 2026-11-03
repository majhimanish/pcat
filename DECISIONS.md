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
