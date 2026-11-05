# Pilot plan: 4 weeks with one real team

Everything pcat has shown so far was simulated: open-source apps as stand-in
organizations, catalogs reviewed by the builder, one model, small samples
(`claims.md`). A pilot answers the question the simulations cannot: does a real team,
with its own reviewers and its own pull requests, get predictable code from it without
being slowed down?

The success criteria below are fixed **before** the pilot starts. They are not changed
afterwards, and the results are reported even if they miss.

## What the team provides

- **One Python repository** under active development, on GitHub, where engineers already
  use Claude Code (other agents are out of scope for this pilot).
- **A pattern owner**: one senior engineer, about half a day in week 1 and an hour a week
  after, to pick, review and approve patterns.
- **Two to five approvers** listed in `.pcat/approvers.yaml`, who confirm or reject
  deviations on pull requests.
- **Permission to add two CI checks** (`pcat-lint`, `pcat-approvals`) and to make them
  required on the main branch from week 2.
- **Read access for the evaluator** to pull-request metadata (titles, diffs, review
  comments, timings) for the 4 weeks, plus the 4 weeks before as a baseline. No
  production data or secrets are needed.
- **Two short interviews**: the pattern owner and one approver, in week 4.

## The plan

| Week | Setup and work | Collected |
|---|---|---|
| 0 (before) | Agree the success criteria below; export the previous 4 weeks of pull-request metadata as the baseline | baseline review times and comment counts |
| 1 | `pcat init --apply` on a branch; read `.pcat/candidates.md` and the audit report together; write and review 3–5 patterns for code the team writes often (access checks, tokens, client calls, pagination); merge them through normal review | time spent per pattern; audit candidates judged true / debatable / false |
| 2 | Engineers work as usual with Claude Code; the two checks become required | every `pcat` tool call (server log), every marker, every flagged deviation |
| 3 | Same; add or fix patterns where agents missed or misused them | as week 2, plus pattern changes and why |
| 4 | Same; interviews; write-up | as week 2; interview notes |

pcat runs locally and in CI. The server log (`pcat serve --log`) records searches and
fetches; nothing leaves the team's machines except what CI already sees.

## What to measure (adapted from the benchmarks)

| Metric | From | How, on real pull requests |
|---|---|---|
| **Catalog use** | v5 search and fetch rates | Share of pull requests touching a covered area where the agent searched and fetched a pattern (server log + markers) |
| **First-time code matches the reviewed version** | v5 same-function tasks | For new functions in covered areas, similarity to the pattern (`pcat lint` inference report), marked vs unmarked |
| **Deviations become decisions** | v4.1 / v5 Part A | Every high deviation on marked code: confirmed, rejected, or fixed before merge. Nothing high merged uncovered |
| **False CI failures** | v5.1 re-score | Required-check failures that the approver judges wrong, per week, with the reason |
| **Audit precision** | v5.1 survey, v6 audit | Of the audit's candidates, how many the pattern owner calls true, debatable or false |
| **Review effort** (hypothesis H1) | none yet | Review time and review-comment count on pull requests with marked code vs similar pull requests without, and vs the baseline weeks |
| **Pattern cost** (hypothesis H5) | none yet | Hours to write and review each pattern; changes needed in weeks 2–4 |
| **Would they keep it** | none yet | Interview: keep the checks required, keep advisory, or remove |

## Success criteria (decided in advance)

The pilot **succeeds** if all of these hold:

1. **Use:** in at least 70% of pull requests where an agent wrote code in a covered area,
   the agent fetched the pattern.
2. **Nothing high slips:** 0 high-severity deviations on marked code merged without a
   recorded human decision.
3. **Quiet CI:** at most 1 false required-check failure per week on average, each
   explained.
4. **Affordable:** a pattern takes at most 2 hours to write and review, on average.
5. **Kept:** the team chooses to keep at least the lint check after week 4.

It is **promising** if 1–3 hold but 4 or 5 does not (the cost or the workflow needs
work). It **fails** if 2 or 3 does not hold: a gate that lets high deviations through,
or one that cries wolf, is worse than none.

Review effort (H1) is measured and reported, but it is not a success criterion: 4 weeks
and one team are too few to separate it from normal week-to-week variation.

## What the pilot will not show

- Other languages, other agents or models.
- Long-term effects: pattern upkeep over months, `@v2` migrations at scale.
- A savings figure that would hold for other teams.

## Risks and what to do about them

- **Agents skip the catalog** on brief requests (seen in LNbits): add the team's own
  words to `keywords` and `use_when`; check with `pcat search "<request>"`.
- **A guard is too narrow** for a legitimate variant: approve with a reason, then fix the
  guard in a new pattern version.
- **Noise**: keep inferred findings out of required checks (they are advisory by
  default); use the audit once, not as a gate.
