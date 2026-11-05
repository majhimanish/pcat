# v6 Part F — dogfooding the getting-started guide

`docs/getting-started.md` followed step by step on a fresh copy of healthchecks (the v5
pinned commit, `.bench/apps/healthchecks`, new git history on `main`, no remote), with
pcat installed from the built wheel (`pcat-0.1.0-py3-none-any.whl[mcp]`, Python 3.11
virtualenv). Every friction point is listed with what happened to it.

## What happened, step by step

1. **Install.** `pcat --version` → `pcat 0.1.0`. `pipx` is not installed in this
   environment; the guide's `pip` fallback worked.
2. **`pcat init --starter`.** Dry run listed 8 files and changed nothing; detected
   Python (657 files), Django, git, GitHub Actions (`.github/` exists), branch `main`.
   `--apply` wrote them, copied the 7 starter patterns and mined 608 functions (6
   repeated shapes) into `.pcat/candidates.md`. A second run: "nothing to change".
3. **First pattern.** Copied the first command from `candidates.md` →
   `integrations.add_url_channel` (promoted from `add_spike`). Edited `pattern.yaml`
   (title, summary, owner, behavior, keywords, `use_when`, a `must_call` guard on
   `_get_rw_project_for_user` and `.is_valid`), pinned `django>=5,<6`, wrote an
   import-skip test, `pcat index`, `pcat validate --skip-tests` → 8 patterns valid.
4. **Claude Code.** `claude mcp list` shows `pcat … ⏸ Pending approval` (expected:
   interactive sessions approve a project server once). Two `claude -p` runs in copies
   of the repo, no `--mcp-config`: the server was found through `.mcp.json` (status
   connected, source project) — see "Agent runs".
5. **Deviation.** In the agent-written Rootly view (marked), replacing the form
   validation with `request.POST.get("value")` → `pcat lint . --changed-since <base>`:
   `PC100 high … no longer calls .is_valid … [fails]`, exit 1. Adding `# pcat-allow:
   PC100 #6bd3c6c2 -- …` → `[proposed approval, needs confirmation: …] [fails]`.
6. **Audit.** `pcat audit . --out pcat-audit`: 768 functions, 14 resemble a pattern, 0
   findings (the marked view is left to `pcat lint`).

## Friction found

| # | Friction | Status |
|---|---|---|
| 1 | `pipx` missing on the machine | guide already offers `pip`; nothing to fix |
| 2 | `promote` prints "run `pcat fingerprint … --write`", the guide did not mention it, and `pcat validate` fails until `pcat index` runs | **fixed in the guide**: index, then validate; fingerprint only after editing `impl.py` |
| 3 | A promoted pattern failed check 12 at once: it imports the app's own package (`hc`) and Django, and nothing listed them | **fixed**: `init` writes `catalog/catalog.yaml` with the repo's top-level packages as `first_party`; `promote`/`add` pre-fill `requires` from the impl's imports (tests added) |
| 4 | A pattern taken from app code imports the app and its framework, so its tests only run inside the app's environment | KNOWN_GAPS (the v5 catalogs stubbed them) |
| 5 | Headless `claude -p` could not call the pcat tools: Claude Code ignores a project's `permissions.allow` until the folder is trusted ("this workspace has not been trusted"), and `-p` cannot prompt; both first runs got "you haven't granted it yet" | **partly fixed**: `init` now allows the three read-only pcat tools in `.claude/settings.json` (works once the folder is trusted, i.e. after opening it in Claude Code once); headless use needs `--allowedTools mcp__pcat__…`; guide updated |
| 6 | `pcat lint .` and `pcat audit .` scanned the catalog's own `impl.py` files under `pcat-catalog/` (11 inferred findings; 11 of 25 "resemble a pattern") | **fixed**: files inside the catalog are skipped when scanning a folder that contains it (test added) |
| 7 | The GitHub workflows could not be exercised: the copy has no GitHub remote | not tested here; the workflows are the v4.1/v5.1 ones (`pcat-approvals.yml` ran on this repository's own pull request #1) |
| 8 | The agent placed the marker between the decorators and `def` | handled by the Part E fix; without it the function would only have been inferred |

## Agent runs (`agent_runs/`)

Both with the v5 tool restrictions (no web, no subagents, read-only shell) plus
`--allowedTools mcp__pcat__search_patterns mcp__pcat__get_pattern mcp__pcat__check_code`
(friction 5); the server itself came only from the `.mcp.json` that `pcat init` wrote.

| Run | Request | pcat calls | Result | Cost (CLI estimate) |
|---|---|---|---|---|
| `rootly` | "Add the view that lets a logged-in user add a Rootly webhook URL to one of their projects, like the other URL integrations." | search → `integrations.add_url_channel` (the pattern promoted in step 3), `get_pattern`, `check_code` | wrote `hc/integrations/rootly/` with the pattern and `# pcat: integrations.add_url_channel@v1`; `check_code`: near match, two expected literal changes | $0.167, 45 s |
| `tokens` | "Add helpers to hash and verify the secret of a new per-user API token before we store it." | search → no match above the threshold | wrote Django-hasher helpers and tests; said the catalog's PBKDF2 pattern is for user passwords and did not force it | $0.093, 20 s |

`agent_runs_attempt1/` holds the first two runs, where every pcat call was refused
(friction 5).
