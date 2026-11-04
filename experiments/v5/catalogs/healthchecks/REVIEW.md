# healthchecks catalog — review record (v5)

**Reviewer:** the agent that built v5 (Claude), *not* a healthchecks maintainer or the
pcat owner. This is a self-review: treat every pattern as reviewed by one person
who did not write the original code and could not ask its authors.

**Source:** healthchecks v5.0.3 (`51a503531d845fc11d5ef270d576c59c300e3620`).

## What was reviewed, and how

For each house pattern I:
1. picked it from the mining report (`experiments/v5/mining/healthchecks/`) or as a
   clear house idiom, and read every other occurrence in the app;
2. extracted it with `pcat add` (function, its same-file helpers, constants and
   imports), so `impl.py` is the app's code verbatim, except where listed below;
3. wrote `pattern.yaml` (summary, behavior, keywords, `use_when`, `usage`, guards);
4. wrote `test_impl.py` with normal, edge and failure cases. Django and the `hc`
   package are **stubbed** with small fakes (neither is installed here), so the
   tests check the pattern's logic against my understanding of Django's API, not
   against Django itself. They were not run inside the app.

The 7 generic patterns are copied unchanged from `catalog/` (reviewed by the owner in v2.2).

## Patterns

| Id | Source | Occurrences in app | Notes |
|---|---|---|---|
| `integrations.add_url_channel` | `hc/integrations/msteamsw/views.py:add_msteams` | 6 (msteamsw, mattermost, rocketchat, pagertree, spike, victorops) | ctx key order differs in two copies (different shape, same behaviour) |
| `access.channel_for_user` | `hc/front/views.py:_get_channel_for_user` + `_get_rw_channel_for_user` | 3 pairs (check, channel, project) | the check variant adds `preload_owner_profile` |
| `api.authorize_read` | `hc/api/decorators.py:authorize_read` (+ `error`, `_get_api_version`) | 2 (`authorize`, `authorize_read`) | hand-assembled: `ApiRequest` is a class in the same module, so `impl.py` imports it from `hc.api.decorators`; body verbatim |
| `views.require_setting` | `hc/front/decorators.py:require_setting` | 1 (used ~40 times) | |
| `accounts.allow_redirect` | `hc/accounts/views.py:_allow_redirect` | 1 | security: blocks open redirects (netloc check + route allowlist) |
| `integrations.help_page` | `hc/integrations/pd/views.py:pd_help` | 3 | trivial view |
| `badges.check_signature` | `hc/lib/badges.py:check_signature` | 1 | **concern:** compares signatures with `==`, not `hmac.compare_digest`; kept verbatim (house code), flagged here |
| `emails.templated_send` | `hc/lib/emails.py:login` | 7 one-line senders | hand-assembled: `send` uses the module's `EmailThread` class, so `impl.py` imports `make_message, send` from `hc.lib.emails` |
| `emails.templated_send_blocking` | `hc/lib/emails.py:report` | 5 senders with headers/blocking | same as above |

Candidates skipped: `TokenBucket.authorize_*` and other model methods (patterns cannot
contain classes); `checks.post_action` (`remove_check`), because extracting it pulled in
`_get_check_for_user`, the target of a v5 task.
