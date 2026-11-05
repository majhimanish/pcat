# v5.2 Part E — can CI catch copied flaws without markers?

`scripts/v5_2.py labels` builds `labeled.json`; `calibrate` writes `calibration.json`;
`mode_check.json` measures the opt-in `--fail-on-inferred-guards` mode it led to.

Labeled set (517 functions; label = derived from `label_pattern`, or from no pattern):
the untouched originals of every v5 and v5.2 task (31 derived, 6 v5 negatives), v5.1's
hand-classified survey findings (14 debatable = derived siblings, 63 false positives = not
derived; nested-wrapper duplicates left out), 120 random app functions (assumed not
derived), the functions v5 runs wrote (106 derived, 35 from negative tasks) and the
functions v5.2 runs wrote (142 derived). Split by app/pattern group into a calibration
and a held-out half (no function or group in both). Features: similarity to the most
similar catalog function, overlap with its calls and imports, whether the function touches
the pattern's guarded names (`src/pcat/derivation.py`). 21 variants; the best by precision
on the calibration half with recall >= 0.5 is `sim>=0.75`: held-out precision 0.962,
recall 0.884 (default 0.56: 0.84 / 0.977).

Caveats: derived functions are 57% of this set and far rarer in real code, so precision on
a codebase is lower (see `mode_check.json`: 5 failures on 4,031 untouched functions, none a
clear flaw; 3 of 5 failing v5.2 runs were real inherited flaws). The random sample is
assumed not derived; one of them (a nested wrapper of a pattern's own source) was not.
