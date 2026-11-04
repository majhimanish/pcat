# v5.1 false-positive survey (Part E)

`pcat lint --include-inferred` with each app's own catalog over the untouched app code at the
pinned commits (`.bench/apps/`), tests/docs/migrations excluded (DECISIONS 218). No code carries
markers, so every finding is inferred and advisory. Files: `survey_v5.json` (v5 linter, v5-era
catalogs), `survey_before.json` (after Parts A-D), `survey_after.json` (after the Part E fixes),
`classification.json` (manual verdicts for 30 random medium/high findings per app, from `before`).

| App | Files | Functions checked | Linter | Inferred derived | High | Medium | Low | Functions with medium/high |
|---|---|---|---|---|---|---|---|---|
| ctfd | 178 | 806 | v5 | 118 | 41 | 237 | 332 | 94 |
| ctfd | 178 | 806 | before | 118 | 36 | 240 | 321 | 94 |
| ctfd | 178 | 806 | after | 109 | 34 | 188 | 299 | 85 |
| healthchecks | 228 | 767 | v5 | 125 | 67 | 287 | 699 | 101 |
| healthchecks | 228 | 767 | before | 125 | 66 | 248 | 501 | 92 |
| healthchecks | 228 | 767 | after | 120 | 66 | 234 | 488 | 88 |
| lnbits | 175 | 2458 | v5 | 179 | 105 | 332 | 573 | 165 |
| lnbits | 175 | 2458 | before | 179 | 102 | 333 | 569 | 163 |
| lnbits | 175 | 2458 | after | 179 | 102 | 319 | 567 | 163 |

## Manual classification (30 per app, sampled from `before`)

| App | Medium/high findings | True deviation | Debatable | False positive | Removed by Part E fixes |
|---|---|---|---|---|---|
| ctfd | 276 | 0 | 2 | 28 | 8 (all false positives: True) |
| healthchecks | 314 | 0 | 3 | 27 | 2 (all false positives: True) |
| lnbits | 435 | 0 | 10 | 20 | 7 (all false positives: True) |

Every item, with its one-line reason, is in `classification.json`.
