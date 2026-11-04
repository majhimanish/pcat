# v5.1 re-scoring (Part F)

No new agent runs. v5's 144 end-to-end runs were rebuilt from their saved diffs and linted as v5
scored them (`scripts/v5_1.py lint-e2e`): with the v5 linter (a worktree of the pre-v5.1 commit;
`e2e_v5.json`, identical to the saved v5 scores for 144/144 runs) and with the v5.1 linter
(`e2e_v5.1.json`). The v3-sample replay and the v4 / v4.1 feedback runs were re-scored with
`scripts/lint_eval.py ... --out ../v5.1/rescore/...` (`replay_v3_samples.json`, `feedback_v4.json`,
`feedback_v4.1.json`). Comparisons: `e2e_compare.json`, `samples_compare.json`.

## v5 end-to-end runs

| Condition | Linter | Would fail CI | High | Medium | Low |
|---|---|---|---|---|---|
| baseline | v5 | 0/72 | 16 | 75 | 314 |
| baseline | v5.1 | 0/72 | 9 | 33 | 220 |
| pcat | v5 | 5/72 | 16 | 82 | 300 |
| pcat | v5.1 | 0/72 | 7 | 18 | 193 |

Deviations by code (count at its severity; PC102 and PC103 are graded):

| Code | baseline v5 | baseline v5.1 | pcat v5 | pcat v5.1 |
|---|---|---|---|---|
| PC100 | 10 high | 6 high | 12 high | 5 high |
| PC102 | 6 high | 3 high, 3 medium | 4 high | 2 high, 2 medium |
| PC103 | 6 low, 9 medium | 3 low, 6 medium | 6 low, 8 medium | 3 low, 5 medium |
| PC104 | 3 medium | 3 medium | 2 medium | 2 medium |
| PC105 | 22 medium | 15 medium | 10 medium | 4 medium |
| PC107 | 41 medium | 6 medium | 62 medium | 5 medium |
| PC108 | 183 low | 118 low | 169 low | 98 low |
| PC109 | 23 low | 26 low | 32 low | 35 low |
| PC110 | 102 low | 73 low | 93 low | 57 low |

Runs whose CI outcome flipped: 5 (all fail -> pass); runs whose deviations changed: 46.

- `ctfd/ctfd_reset_token/pcat/sample_02`: raises the reset flow's own token exception under the same check; guard now `match: any`, PC102 medium (Part D). Before: `PC100`; `PC102`
- `ctfd/ctfd_reset_token/pcat/sample_03`: raises the reset flow's own token exception under the same check; guard now `match: any`, PC102 medium (Part D). Before: `PC100`; `PC102`
- `lnbits/lnbits_invoice_key/pcat/sample_01`: exact reproduction of the original; `KeyChecker` is a class in the same module (Part A). Before: `PC100`
- `lnbits/lnbits_invoice_key/pcat/sample_02`: exact reproduction of the original; `KeyChecker` is a class in the same module (Part A). Before: `PC100`
- `lnbits/lnbits_invoice_key/pcat/sample_03`: exact reproduction of the original; `KeyChecker` is a class in the same module (Part A). Before: `PC100`

Every high deviation left under v5.1 (16, baseline and pcat) is advisory: inference attached
`camel_to_snake` to `validators.regex_match` (6 runs) and `is_lnbits_version_ok` to
`config.env.load_settings` (5 runs). Neither derives from a pattern (DECISIONS 214, 221).

## Lab data (v3 samples, v4 and v4.1 feedback runs)

| Data | Original scoring | Samples with an unapproved high deviation: original -> v5.1 | High flips | Samples whose codes changed |
|---|---|---|---|---|
| v3_samples_vs_v4.1_replay | `experiments/linter/replay_v4.1.json` | 25 -> 25 of 140 | 0 | 0 |
| v3_samples_vs_v4_replay | `experiments/linter/replay.json` | 12 -> 25 of 140 | 15 | 26 |
| v4.1_feedback_vs_v5_part_a | `experiments/linter/feedback_v4.1/results.json` | 20 -> 20 of 60 | 0 | 0 |
| v4_feedback_vs_v4.1_rescore | `experiments/linter/feedback_v4.1/v4_rescored.json` | 21 -> 21 of 60 | 0 | 0 |

The v3-vs-v4 row differs only by the v4.1 rule changes (the 429 `must_include` guard and graded
PC103); against the v4.1 scoring nothing changed. The v5 Part A headline (25 / 21 / 20 of 60
unapproved high for v3 / v4 / v4.1) stands under v5.1, field for field.
