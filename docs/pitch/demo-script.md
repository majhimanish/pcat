# Live demo (5 minutes)

What the audience sees: `pcat init` setting up a repository, a coding agent fetching a
reviewed pattern, a pull request flagged for breaking a guard, a `/pcat approve`
confirmation turning the gate green, and an audit finding in old code.

The local commands below were rehearsed on 2026-11-05 with pcat 0.1.0 and Claude Code
2.1.318 (the agent step through `claude -p`, as in the dogfood runs in
`experiments/v6/dogfood/`); outputs are shortened with `…`. The GitHub part (checks on the
pull request, `/pcat approve`) was not rehearsed for this script. It is the flow of this
repository's demo pull request #1, whose `pcat-approvals` check fails as designed while
its proposal waits; the green step after `/pcat approve` has not been seen end to end yet.
Doing the full dry run before the talk is not optional.

## Before the talk (about an hour, the day before)

You need: Python 3.11+, git, Claude Code signed in, a GitHub account, and a second
GitHub account or a colleague to be the approver (or use solo mode, see step 4).

**1. Install pcat with the `mcp` extra** (without it the agent cannot reach the catalog):

```bash
pipx install "pcat[mcp] @ git+https://github.com/majhimanish/pcat"
pcat --version                       # pcat 0.1.0
```

**2. Build the sample repository** (a small app with one old, copied HTTP client):

```bash
mkdir -p pcat-demo/app pcat-demo/.github/workflows && cd pcat-demo
git init -q -b main
printf '[project]\nname = "pcat-demo"\nversion = "0.1.0"\ndependencies = ["requests"]\n' > pyproject.toml
touch app/__init__.py
cat > app/profiles.py <<'PY'
"""Profile service client. Copied from the billing client last year."""

import random
import time

import requests

RETRY_STATUSES = (429, 500, 502, 503, 504)


def retry_after(value):
    return float(value) if value and value.strip().isdigit() else None


def fetch_profile(url, session=None, attempts=4, base_delay=0.5, max_delay=30.0,
                  timeout=10.0, sleep=time.sleep, rand=random.random):
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    session = session or requests.Session()
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            response = session.get(url, timeout=timeout)
        except requests.Timeout:
            if last:
                raise
            hint = None
        else:
            if response.status_code not in RETRY_STATUSES or last:
                response.raise_for_status()
                return response
            hint = retry_after(response.headers.get("Retry-After"))
        backoff = min(max_delay, base_delay * 2 ** attempt) * rand()
        sleep(min(max_delay, hint) if hint is not None else backoff)
    raise AssertionError("unreachable")
PY
git add -A && git commit -qm "Profile client"
```

`fetch_profile` is a copy of the starter HTTP pattern that retries timeouts but not
connection errors: the audit finding for step 5.

**3. Make the GitHub copy and the pull request.** In `pcat-demo`:

```bash
pcat init --starter --apply
# edit .pcat/approvers.yaml: approvers: [your-colleague]
#   presenting alone? your own username and allow_author: true (solo mode; say so on stage)
git add -A && git commit -qm "Set up pcat"
claude    # trust the folder, approve the pcat server, ask for the password helpers (step 2)
git add -A && git commit -qm "Password helpers"
```

Create an empty GitHub repository `pcat-demo`, add it as `origin` and push `main`. In the
repository settings, protect `main` and require the `pcat-approvals` check. Then:

```bash
git checkout -b plain-compare
sed -i 's/return hmac.compare_digest(key, expected)/return key == expected/' app/auth.py
git commit -qam "Compare password keys directly" && git push -u origin plain-compare
```

Open the pull request and wait until both checks are red (`pcat-lint` shows the PC100
annotation on the diff). Then add the approval line from stage step 4 (below) above the marker of
`verify_password`, with the hash the annotation shows, commit and push. `pcat-approvals`
stays red and its log lists the proposal as waiting. Keep this tab open: on stage you only
comment `/pcat approve`.

**4. Make the live copy.** Run the script from step 2 again in another folder (say
`~/live/pcat-demo`) and open `claude` there once to trust the folder. Stop there: the
audience sees `init` and the agent run in this copy. It has no remote, so nothing on
stage depends on pushing.

**5. Record a screen capture** of the whole run as a fallback.

## On stage

### 1. Set up the repository (0:00–0:45)

```bash
cd pcat-demo
pcat init --starter            # dry run
```

```
detected: python=yes (2 files), framework=none, git=yes, CI=github, default branch=main
catalog: pcat-catalog (starter)
  would create pcat-catalog/catalog — catalog seeded with the 7 starter patterns
  …
  would create .mcp.json — Claude Code project MCP server: `pcat serve` with this catalog
  …
  would create .github/workflows/pcat-approvals.yml — pull requests: wait for a human to confirm proposed approvals
dry run: nothing was changed. Run again with --apply to make these changes (pcat mine runs then too).
```

```bash
pcat init --starter --apply
git add -A && git commit -qm "Set up pcat"
```

**Say:** "One command sets up three things: a catalog of reviewed patterns in the repo,
the MCP config so Claude Code can search it, and two pull-request checks. The dry run
shows every file first. These 7 starter patterns are examples; a team adds its own from
its own code, through normal review."

### 2. The agent fetches a pattern (0:45–2:00)

In Claude Code (`claude` in the folder), type:

> Add helpers to app/auth.py that hash and verify user passwords.

(Headless alternative, as rehearsed:
`claude -p "Add helpers to app/auth.py that hash and verify user passwords." --allowedTools mcp__pcat__search_patterns mcp__pcat__get_pattern mcp__pcat__check_code Read Write Edit`.)

Point at the tool calls as they appear: `search_patterns`, `get_pattern`, `check_code`.
Then show the file:

```bash
grep -n "pcat:" app/auth.py
```

```
21:# pcat: auth.password.pbkdf2@v1
31:# pcat: auth.password.pbkdf2@v1
45:# pcat: auth.password.pbkdf2@v1
```

**Say:** "The agent didn't invent a password hasher. It searched the catalog, fetched the
reviewed version, checked its code against it, and marked each function with the pattern
it came from. That marker is what CI checks. In our runs inside three open-source apps,
agents with pcat reproduced the house version 12/12 times on code the repo didn't have
yet, against 2/12 without it. Those apps were stand-ins, the catalogs were mine, and it
was one model, so this is evidence for a pilot, not a guarantee."

Commit it: `git add -A && git commit -qm "Password helpers"`.

### 3. A deviation is flagged on a pull request (2:00–3:15)

Make the change a hurried engineer (or agent) might make:

```bash
git checkout -b plain-compare
sed -i 's/return hmac.compare_digest(key, expected)/return key == expected/' app/auth.py
pcat lint . --changed-since main
```

```
app/auth.py:32: PC100 high #e96d53e0: `verify_password` no longer calls `hmac.compare_digest`,
which the reviewed pattern requires (constant-time comparison of the derived key) [guard must_call] [fails]
```

Switch to the prepared pull request: the same change, the same message as an annotation
on the diff, and `pcat-approvals` red.

**Say:** "The test suite would pass: `==` gives the same answer. What changed is the one
property the reviewer cared about, a constant-time comparison. That property is written
down in the pattern as a guard, so the pull request fails with a sentence a reviewer can
act on, not a diff to re-read."

### 4. A human decides (3:15–4:00)

Suppose the change were intended. Add the approval the message asks for, with its hash
and a reason, directly above the marker:

```python
# pcat-allow: PC100 #e96d53e0 -- demo: plain comparison, to show the approval flow
# pcat: auth.password.pbkdf2@v1
def verify_password(password: str, stored: str) -> bool:
```

```bash
pcat lint . --changed-since main
```

```
… [proposed approval, needs confirmation: demo: plain comparison, to show the approval flow] [fails]
note: 1 proposed approval(s) since main approve nothing until confirmed in the pull request (see `pcat approvals check`)
```

On the prepared pull request this line is already pushed, and `pcat-approvals` lists it as
waiting. Now the approver comments `/pcat approve` (or approves the pull request). The
check re-runs in about a minute: show the audit (step 5) meanwhile, then come back to the
green check.

**Say:** "An agent can write this line too, and ours do. But it's only a proposal: it
approves nothing until someone on the approvers list confirms it on the pull request.
In our lab runs, every high-severity deviation ended up as one of these proposals
waiting for a person; none went through on its own. `pcat-approvals` is the required
check; `pcat-lint` stays as the annotations on the diff."

### 5. The audit finds old code (4:00–4:45)

```bash
pcat audit . --out pcat-audit
```

```
scanned 5 function(s) in … file(s); 1 resemble a pattern (similarity >= 0.75); 1 finding(s)
  app/profiles.py:15 fetch_profile ~ http.get_with_retry.requests@v1 (similarity 0.92, margin 0.60): must_catch
```

Open `pcat-audit/audit.html`: "`fetch_profile` no longer handles
`requests.ConnectionError` (it catches requests.Timeout); the reviewed pattern must catch
it."

**Say:** "The code that was already there has no markers, so CI ignores it. The audit is a
one-time report: functions that look like a reviewed pattern but break one of its guards.
This one was copied from another client and lost a retry. It's a list for a person to
read, not a build failure; on real apps many candidates turn out to be fine."

Back on the pull request: `pcat-approvals` is green.

### Close (4:45–5:00)

**Say:** "Reviewed code in, deviations flagged, a human decides. Everything I showed is in
the 30-minute guide. What we don't know yet is how it works with a real team, so the
next step is a 4-week pilot."

## If something fails

| Symptom | Likely cause | What to do on stage |
|---|---|---|
| The agent says the pcat tools "didn't connect" or "Connection closed" | pcat installed without the `mcp` extra, or not on Claude Code's PATH (seen in rehearsal) | Say what happened; show the agent still copied the catalog file, or switch to the screen capture. After: `pipx install --force "pcat[mcp] @ git+…"`; check with `pcat serve --catalog pcat-catalog` |
| `claude mcp list` shows `⏸ Pending approval` | the project server was never approved | Run `claude`, approve the server, rerun |
| The agent asks for permission to use the pcat tools | folder not trusted yet | Accept, or use the headless command with `--allowedTools` |
| The agent writes its own hasher without a marker | the search missed (brief wording) | Show `pcat search "hash and verify user passwords"`; say this happens and is why keywords matter; continue with the prepared branch |
| The hash in the lint message is not `#e96d53e0` | the agent's code differs from the rehearsal | Use the hash the message shows; the approval must carry it |
| `pcat lint` reports nothing after the edit | edited a module constant, not the function body (`--changed-since` checks the functions whose lines changed; see KNOWN_GAPS) | Make the `hmac.compare_digest` edit shown above |
| `pcat-approvals` stays red after `/pcat approve` | the commenter is not in `.pcat/approvers.yaml`, the comment came before the last push, or the PR author confirmed without `allow_author: true` | Show the check's log: it lists who may confirm. Use the screen capture |
| The re-run after `/pcat approve` takes long | GitHub Actions queue | Finish the audit, then show the green check from the dry run or the screen capture |
| `pcat audit` finds nothing | `app/profiles.py` changed | Show `pcat-audit/audit.html` from the prepared copy |
