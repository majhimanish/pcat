# v6 Part C — `pcat audit` on the v5 apps and the planted v5.2 neighbours

`python scripts/v6_audit.py` (a measurement; the threshold is v5.2's opt-in 0.75,
unchanged). Each app is audited whole with its own v5 catalog; each planted v5.2 working
copy (target removed, neighbour planted) is audited on the task's file.

| App | Functions scanned | Resemble a pattern (>= 0.75) | Findings on untouched code |
|---|---|---|---|
| CTFd | 810 | 28 | 0 |
| healthchecks | 767 | 51 | 0 |
| LNbits | 2,509 | 48 | 5 |

The 5 LNbits findings are the ones v5.2 reviewed by hand (`experiments/v5.2/inference/
mode_check.json`): 3 false (an id lookup without `.lower`, `LightKeyChecker` by design
twice), 2 debatable (`re.match` with `^…$` accepts a trailing newline).

**Planted neighbours surfaced: 10 of 18.** Found: `throttle`, `members_only`,
`generate_invite_token`, `add_splunk_oncall`, `authorize_ping_key`, `authorize_metrics`,
`create_share_token`, `get_account_by_login`, `is_valid_wallet_name`, `is_valid_tag`, each
with the guard the manifest names. Missed (all 8 below 0.75 similarity to their pattern):
`admins_only_api` (0.748 to `admins_only`, just below), `api_authed_only` (0.69),
`verify_invite_token` (0.74, closest to the pattern's `remove` function), `_allow_next_url`
(0.47), `_get_rw_notification_for_user` (0.53), `_get_notification_for_user` (0.71),
`check_webhook_url` (0.53), `require_wallet_key` (0.66). The flaw itself often makes the
code look less like the pattern (a `startswith` check instead of parsing, no
`get_object_or_404`), which is the limit of similarity-based inference.
