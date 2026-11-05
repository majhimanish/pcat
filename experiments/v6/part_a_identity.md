# v6 Part A — outputs before and after moving research code out of the package

Every analysis step that needs no new generation (27 commands: variance analyze ×2,
reference, report; catalog_coverage; catalog_review_doc; mcp_eval retrieval and
e2e-analyze; lint_eval calibrate, replay ×2, feedback-analyze ×3; v5 mining-summary,
references, retrieval; v5_e2e analyze; v5_1 lint-e2e, compare-e2e, compare-samples,
survey; v5_2 prepare, verify, analyze, labels, calibrate) was run twice: in a git worktree
of the commit before the move (`6e1c7e7`) and in a worktree of the Part A commit
(`f62ad3a`). All 27 exited 0 in both.

**Result: every output is byte-identical between the two checkouts.**

In both, 13 files differ from their committed copies, identically, for reasons older than
v6 (they were never regenerated after later, deliberate changes, and are left as
committed):

| Files | Why they differ from the committed copy |
|---|---|
| `experiments/variance/runs/{main,smoke}/mine-*/report.{json,html}` (10), `runs/smoke/analysis.json` | written when the catalog had 6 patterns; coverage now lists 13 |
| `experiments/linter/inference_calibration.json` | written before `INFERENCE_THRESHOLD` was set to the calibrated 0.56 (`"constant"` field) |
| `experiments/linter/replay_v4.1.json` | the v4.1 replay predates the v5.1 linter fixes (v5.1 wrote its re-score to `experiments/v5.1/rescore/` instead) |
