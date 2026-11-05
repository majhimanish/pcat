# FAQ: honest answers to likely objections

Every number here is in `claims.md` with its source and caveat.

### Why not just put this code in a shared library?

Do that where you can: a library call is better than any copy. pcat is for the code
that does not fit a library well: the access check inside a view, the token helper that
needs the app's settings, the client call with this service's retry rules. That glue is
written again and again, slightly differently each time, and agents now write most of
it. A library also says nothing about the code that does *not* call it; pcat's linter
checks the code that was written, against what reviewers said matters (guards).

Real code also repeats less than you'd think: in the three open-source apps we studied,
the miner found only 3, 6 and 8 repeated function shapes in 587, 608 and 1,768
functions. So a catalog comes from review ("this is how we do access checks"), not from
mining.

### How is this different from rules files, `CLAUDE.md` or skills?

Rules files and skills tell the model what to do. pcat also checks what it did. The
catalog gives the agent the reviewed code (not a description of it), the agent marks
what it used, and CI compares the result with the pattern. When the code breaks a guard,
the pull request fails until a person decides. A rule the model ignored is invisible; a
broken guard is a red check with an explanation.

They work together: `pcat init` adds one line to `CLAUDE.md` telling agents to use the
catalog.

### Who writes and reviews the patterns, and how long does it take?

Your engineers. `pcat init` mines your repository for repeated shapes and lists them in
`.pcat/candidates.md`; one command turns a candidate (or any function) into a draft
pattern. A senior engineer then edits its description and guards and writes tests, and
the team reviews it as an ordinary pull request. The getting-started guide budgets 10
minutes for the mechanics. How long a real review takes is not measured yet; the pilot
times it (hypothesis H5 in `claims.md`).

### What if agents ignore the catalog?

Then nothing gets worse, and you can see it. In our runs inside real repositories the
agent searched the catalog in 71/72 runs and fetched the right pattern every time it
needed one (54/54). Search was weaker on brief requests where pattern metadata was thin:
the right pattern ranked first 0.94, 0.89 and 0.67 of the time across the three apps.
The fix is better keywords in the team's own words, and `pcat search "<request>"` shows
what an agent would find.

Agents also did not force patterns onto unrelated work (0/36). And when similar code
already sits next to the work, agents copy it with or without pcat; the catalog's
measured value is for code the repository does not have yet (12/12 with pcat vs 2/12
without, on 4 tasks).

### Will it flood our CI with false positives?

The required check is narrow on purpose: it fails only marked code, only on
high-severity deviations, only in functions the pull request changed. With that scope,
no correct code failed CI in 144 runs inside three apps (0/72 runs with pcat; an earlier
version failed 5, all explained and fixed). The narrow scope also has a gap today: a
change to a module-level constant alone, outside the function, is not yet counted as a
change to the function on pull requests (`KNOWN_GAPS.md`).

Findings on code nobody marked are a different story: of 90 sampled medium/high findings
on untouched app code, 75 were false positives, 15 debatable, 0 true. So they stay
advisory and are off in pull requests by default. The opt-in check for copied code
(similarity 0.75 or more) caught 3/3 copied flaws in our study but also failed 2/108
correct runs and 5 of 4,031 untouched functions: use it with care.

### What if a pattern is wrong?

Patterns are versioned and an approved version never changes. You publish a fixed
`@v2`, mark `@v1` deprecated, and every function marked `@v1` is findable by its marker.
Until then, code that legitimately differs from a pattern is approved in place with a
reason and a hash of the function, confirmed by a named approver on the pull request.

The weakness: a wrong pattern is copied faithfully. The catalog is only as good as its
review, which is why patterns go through normal code review and list their guards.

### Does it work for languages other than Python?

Not yet. The canonicalizer, the linter and the starter patterns are Python only
(Python 3.11 or newer). The approach is not specific to Python, but each language needs
its own parser and rules.

### What does it cost?

pcat itself is a command-line tool and an MCP server that run on your machines; it calls
no paid service. The agent's cost barely changes: median $0.10 per run with pcat vs $0.09
without in our real-app runs ($14.59 for all 144). These are the Claude Code CLI's own
estimates and may reflect plan usage rather than billing.

The real cost is people: writing and reviewing patterns, and deciding on flagged
deviations. That is what the pilot measures.

### Why are the samples so small?

Each run is a real agent session in a fresh copy of a real repository, with a usage
limit. We chose depth over breadth: 3 samples per task in the real-app studies and 20
per prompt in the lab, with every caveat written down. The results are evidence for a
pilot, not proof at scale. The main real-app effect rests on 4 tasks; the planted-flaw
result (3/54 without the catalog vs 0/54 with it) rests on 6 runs in 2 tasks
(3/6 vs 0/6).

### Wasn't all of this tested on your own catalogs?

Yes. Three open-source apps stood in for organizations, and the builder of pcat picked
and reviewed every pattern; no maintainer of those apps did. Everything used one model
through Claude Code. That is the most important caveat, and the reason the next step is
a pilot with a real team and its own reviewers.

### Does it replace code review?

No. It moves review earlier (to the pattern, once) and makes the remaining review
sharper: a reviewer sees "this function no longer retries on 429" instead of re-reading
a retry loop. Every deviation still needs a human decision.
