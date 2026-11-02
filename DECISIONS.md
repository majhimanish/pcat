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
