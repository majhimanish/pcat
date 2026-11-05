# Getting started with pcat (about 30 minutes)

For a team lead who wants to try pcat on one Python repository. You will: install pcat,
set it up with `pcat init`, turn one piece of your own code into a reviewed pattern,
connect Claude Code, watch a pull request flag a deviation, and run a one-time audit.

What you need: Python 3.11 or newer, git, a Python repository (ideally on GitHub), and
Claude Code if you want the agent part.

## 1. Install (2 minutes)

```bash
pipx install "pcat[mcp] @ git+https://github.com/majhimanish/pcat"
pcat --version          # pcat 0.1.0
```

No pipx? Use a virtualenv: `pip install "pcat[mcp] @ git+https://github.com/majhimanish/pcat"`.
The `mcp` extra is needed for `pcat serve` (the server Claude Code talks to). The `catalog`
extra only matters if you run the starter patterns' own tests (`pcat validate`).

## 2. Set pcat up in your repository (3 minutes)

```bash
cd your-repo
pcat init --starter            # dry run: shows every file it would create, changes nothing
pcat init --starter --apply    # makes the changes and mines your code for candidates
```

`--starter` seeds `pcat-catalog/` with 7 reviewed application patterns (password hashing,
JWT access tokens, HTTP GET with retries, pagination, CSV import, rate limiting, settings
from the environment). Leave it out to start with an empty catalog, or pass
`--catalog PATH` to use a catalog your organization already has.

What `init` writes, and why:

| File | Purpose |
|---|---|
| `.pcat/config.yaml` | where the catalog is, lint settings; every `pcat` command run inside the repo reads it |
| `pcat-catalog/catalog/` | your catalog (reviewed patterns live here) |
| `.mcp.json`, `.claude/settings.json` | Claude Code starts `pcat serve` for this project |
| `CLAUDE.md` | one line telling agents to use the pcat tools |
| `.github/workflows/pcat-lint.yml`, `pcat-approvals.yml` | the pull-request checks |
| `.pcat/approvers.yaml` | who may confirm a deviation (fill this in) |
| `.pcat/candidates.md`, `.pcat/mining/` | repeated code shapes found in your repo |

Running `init` again changes nothing. Not on GitHub Actions? `init` prints the two commands
to add to your CI instead.

## 3. Make your first reviewed pattern (10 minutes)

Open `.pcat/candidates.md`. Each entry is a shape your code repeats, with the command that
turns it into a pattern. Pick one that matters (an access check, a token helper, a client
call), copy its command and replace `<category>.<name>` with an id for the pattern:

```bash
pcat --root pcat-catalog promote fn-9a554c57b6ce --report .pcat/mining/report.json --id integrations.add_url_channel
```

That creates `pcat-catalog/catalog/<category>/<name>/` with `pattern.yaml`, `impl.py` and a
test stub (and `requires` filled in with the libraries it imports). Now review it like any
code:

1. Edit `pattern.yaml`: `title`, `summary`, `owner` (a team), `keywords` and `use_when`
   (agents search on these), and **`guards`**: the properties a reviewer cares about, for
   example `must_call: [hmac.compare_digest]` or `must_raise: [PermissionDenied]`.
2. Write real tests in `test_impl.py`.
3. Pin version ranges in `requires` (e.g. `django>=5,<6`), then index and check it:

```bash
pcat index
pcat validate --skip-tests     # with the pattern's libraries installed, drop --skip-tests to run its tests
```

   If you change `impl.py`, refresh its fingerprint first: `pcat fingerprint <id> --write`.

4. Commit on a branch and open a pull request. The review of that pull request **is** the
   approval of the pattern. Once merged, the version is immutable; changes go in `@v2`.

Also fill in `.pcat/approvers.yaml` (GitHub usernames) in the same pull request.

## 4. Connect Claude Code (3 minutes)

`init` already wrote `.mcp.json` and `.claude/settings.json`. Open the repository in
Claude Code once (`claude`): accept the "trust this folder" question and, if it asks,
approve the project's `pcat` MCP server. Trusting the folder also turns on the settings
that let the three read-only pcat tools run without a prompt each time. Check:

```bash
claude mcp list                # pcat: ... ✓ Connected
```

Running Claude Code headless (`claude -p`, CI, scripts) in a folder nobody has opened yet?
It loads the server but cannot ask for permission, so allow the tools on the command line:
`--allowedTools mcp__pcat__search_patterns mcp__pcat__get_pattern mcp__pcat__check_code`.

Then ask for something the catalog covers, for example *"add a helper that hashes and
verifies user passwords"*. The agent searches the catalog, fetches the pattern and writes
it with a marker line above the function:

```python
# pcat: auth.password.pbkdf2@v1
def hash_password(password: str) -> str:
```

The marker is what CI checks. If nothing fits, the agent writes normal code.

## 5. See a deviation on a pull request (7 minutes)

On a branch, change a marked function so it breaks one of its guards, for example compare
the password hash with `==` instead of `hmac.compare_digest`, or catch fewer exceptions in
the HTTP retry. Check locally:

```bash
pcat lint . --changed-since origin/main
```

```
app/auth.py:20: verify_password <- auth.password.pbkdf2@v1 verify_password (marked)
  app/auth.py:20: PC100 high #e96d53e0: `verify_password` no longer calls `hmac.compare_digest`, which the reviewed pattern requires (constant-time comparison of the derived key) [guard must_call] [fails]
```

`--changed-since` checks the functions whose own lines changed. A change to a module-level
constant alone (say `MIN_ITERATIONS = 1000`) is caught by `pcat lint app/auth.py`, but not
yet by the pull-request check (see `KNOWN_GAPS.md`).

Push and open a pull request: the `pcat-lint` check fails with the same message on the
diff. If the change is intended, approve it in the code, with the hash shown in the message
and a reason:

```python
# pcat-allow: PC100 #e96d53e0 -- legacy hashes are migrated in a background job
# pcat: auth.password.pbkdf2@v1
def verify_password(password: str, stored: str) -> bool:
```

That is only a **proposal**: `pcat-approvals` stays red until someone in
`.pcat/approvers.yaml` approves the pull request or comments `/pcat approve`. Make
`pcat-approvals` a required check in your branch protection, or a red check can still be
merged. It is the whole gate: it also fails on deviations nobody proposed to approve.
Keep `pcat-lint` as an advisory check for its annotations on the diff: it does not read
reviews, so it stays red on a confirmed proposal.

## 6. Run a one-time audit (5 minutes)

```bash
pcat audit . --out pcat-audit
```

Open `pcat-audit/audit.html` (it reads fine on a phone). It lists existing functions that
look like a catalog pattern (similarity of 0.75 or more) but break one of its guards, with
the margin to the second-most-similar pattern. These are candidates for a person to look
at, not confirmed bugs: some code only resembles a pattern. The audit never fails a build.

## What to expect

- Agents use the catalog when it has a fitting pattern; brief requests on thin metadata may
  not find one (`pcat search "<request>"` shows what would match).
- CI fails only marked code, on high-severity deviations of functions the pull request
  changed. Code an agent copied from a neighbour has no marker, so it is not checked;
  `pcat audit` and the opt-in `pcat lint --fail-on-inferred-guards` cover that, noisily.
- Measured results and their caveats: `docs/benchmarks/summary.md`.

## Troubleshooting

- `no catalog/ directory found`: run commands inside the repository (they read
  `.pcat/config.yaml`), or pass `--root pcat-catalog`.
- `claude mcp list` shows pcat as failed: run `pcat serve --catalog pcat-catalog` yourself
  to see the error; `pcat` must be on the PATH Claude Code uses.
- A pattern uses metadata your pcat does not know: upgrade pcat (`pipx upgrade pcat`).
