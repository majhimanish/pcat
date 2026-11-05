# pcat: reviewed code for AI coding agents

**Make the code agents write predictable: the reviewed version every time, and a human
decision whenever it differs.**

## The problem

Ask a coding agent for the same thing twice and you get two different functions. Every
version of a password check, an access check or an HTTP retry is new code that someone
has to review, and a weak version that lands in the repository becomes the example the
next agent copies. Rules files and style guides steer the model, but nothing checks
what it actually wrote.

## What pcat does

- **A catalog of reviewed patterns** from your own code (auth, tokens, retries,
  pagination, config, rate limiting), approved through ordinary pull requests. Each
  pattern lists **guards**: what a reviewer cares about, such as "must call
  `hmac.compare_digest`" or "must retry on 429".
- **An MCP server** so agents (Claude Code today) search the catalog and fetch the
  reviewed version instead of improvising. They mark what they used: `# pcat: id@v1`.
- **A CI linter** that compares marked code with its pattern and fails the pull request
  when a guard breaks. A deliberate difference is approved in the code with a hash and a
  reason, and stays red until a named person confirms it.

## Three results (simulated, with caveats)

1. **Agents rarely write the same code twice.** Asked for the same function 20 times,
   the agent wrote 15.7 effectively distinct versions on average (20 would mean all
   different); with a reference in the prompt, 2.0. *Lab prompts, one model, 8 tasks,
   480 samples.*
2. **For code a repository doesn't have yet, the catalog decides the outcome.** In three
   open-source apps used as stand-in organizations, agents with pcat reproduced the house
   function 12/12 times on the 4 tasks where it existed nowhere else in the repository;
   without pcat, 2/12. *Self-reviewed catalogs, 3 samples per task, one model. Where
   similar code already sits nearby, agents copy it with or without pcat.*
3. **Nothing high-severity ships without a human decision.** In 20 of 60 lab runs the
   code broke a guarded property of the reviewed pattern; all 20 were flagged and held
   for a person to confirm, 0 went through. With markers, no correct code failed CI in
   144 runs inside the three apps. *One rule set; the lab requests themselves asked for
   the deviation; self-reviewed catalogs.*

Supporting only: with a flawed function planted next to the work, 3/54 agents without
the catalog inherited the flaw and 0/54 with it, but all 3 were in the 2 tasks where the
flaw was the obvious stand-in (*planted by us, 6 runs carry the effect*).

## How a team tries it

```bash
pipx install "pcat[mcp] @ git+https://github.com/majhimanish/pcat"
cd your-repo && pcat init --starter --apply   # catalog, MCP config, CI workflows
pcat audit . --out pcat-audit                 # one-time report on existing code
```

`docs/getting-started.md` walks through it in about 30 minutes: 7 starter patterns, your
first own pattern, Claude Code connected, a deviation flagged on a pull request.

## What is not proven yet

- **No real team has used it.** Everything ran on open-source apps with catalogs the
  builder reviewed, one model (through Claude Code), and small samples.
- **Code an agent copies from a neighbour has no marker**, so default CI does not check
  it. The opt-in check for that, and the audit, are noisy.
- **No savings figures.** Shorter reviews and fewer repeated flaws are hypotheses for a
  4-week pilot (`pilot-plan.md`); every number above is sourced in `claims.md`.
