# v5.2 — catalog versus an unsafe neighbour

Spec: `docs/specs/v5.2-unsafe-neighbour.md`. Driver: `scripts/v5_2.py`; logic: `src/pcat/v52.py`.

- `tasks.yaml` — 18 tasks (6 per app). Each removes a real function covered by a guarded
  pattern of the app's v5.1 catalog and plants one flawed sibling (the manifest: file,
  anchor, planted function, intended flaw, guards it violates, why it is realistic).
- `neighbours/<app>/<task>.py` — the planted function, inserted verbatim.
- `references/<app>/<task>.py` — the removed original functions.
- `context/<app>/<task>.py` — a skeleton of the target file after removal (imports,
  literal constants, the functions the neighbour or the originals call, stubs for every
  other top-level name), so `tests/test_v52.py` checks the guards without the app checkouts.
- `verify.json` — guards on every neighbour and original, on the skeleton and on the real file.

`references/` and `context/` contain excerpts of CTFd (Apache-2.0), healthchecks
(BSD-3-Clause) and LNbits (MIT) at the commits pinned in `experiments/v5/apps.yaml`; the
neighbours are written for this experiment and were never part of those projects.
