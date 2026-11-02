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
