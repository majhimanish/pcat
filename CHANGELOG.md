# Changelog

All versions so far are 0.1.0 development phases on `main`; the phase specs are in
`docs/specs/` and the measured results in `docs/benchmarks/`.

## 0.1.0 — v6: productize

- The installed package holds only product code; research harnesses moved to
  `experiments/lib/pcatlab` (used by `scripts/`).
- `pcat --version`; a starter catalog (7 reviewed application patterns) ships in the package.
- `pcat init`: sets pcat up in a repository (config, catalog, Claude Code MCP config,
  CLAUDE.md note, GitHub Actions workflows, approvers template, mining candidates).
- `pcat audit`: a one-time, human-reviewed report on existing code that looks like a
  pattern but breaks its guards (HTML + JSON).
- Fixes: markers between decorators and `def`; unnecessary approvals reported; catalogs
  with unknown metadata keys refused with an upgrade message; module paths for `src/`
  layouts and namespace packages.
- `docs/getting-started.md` and a README quickstart, checked by following them on a fresh app.

## Earlier phases (research, same package)

- **v5.2** — planted flawed neighbours; opt-in `pcat lint --fail-on-inferred-guards`.
- **v5.1** — linter on real code: one symbol table per unit, partial code in `check_code`,
  validation check 12 (`requires` vs imports), guard `match: any`.
- **v5** — three open-source apps as simulated organizations with their own catalogs.
- **v4.1** — hashed approvals, proposals confirmed by a human on the pull request
  (`pcat approvals check`), PC111, `must_include` guards.
- **v4** — deviation linter: markers, inference, guards, PC100–PC110, `pcat lint`.
- **v3** — MCP server (`pcat serve`) and BM25 search.
- **v2 – v2.2** — miner (`pcat mine`, `pcat promote`), LLM variance study, the owner-chosen
  application catalog.
- **v1 – v1.1** — catalog, canonicalizer, fingerprints, validation, CLI.
