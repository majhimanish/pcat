# CTFd catalog — review record (v5)

**Reviewer:** the agent that built v5 (Claude), *not* a CTFd maintainer or the pcat
owner: a self-review by one person who did not write the code.

**Source:** CTFd 3.8.9 (`5f345fbaa424e6a22b51addf7f27430927879ae2`).

## What was reviewed, and how

Same procedure as the healthchecks catalog: picked from the mining report or as a house
idiom, every other occurrence read, extracted verbatim with `pcat add`, metadata and
guards written, tests written with Flask and the `CTFd` package **stubbed** (not
installed here), so tests check the logic against my reading of Flask's API, not
Flask itself; not run inside the app. The 7 generic patterns are copied unchanged.

## Patterns

| Id | Source | Occurrences | Notes |
|---|---|---|---|
| `decorators.authed_only` | `CTFd/utils/decorators/__init__.py:authed_only` | 2 (`authed_only`, `registered_only`) | |
| `decorators.admins_only` | same file `admins_only` | 1 (used widely) | |
| `decorators.ratelimit` | same file `ratelimit` | 1 (used on auth and team forms) | overlaps the generic `ratelimit.token_bucket.check` topic; counter per IP+endpoint in the shared cache |
| `decorators.require_verified_emails` | same file | 1 | |
| `security.email_confirm_token` | `CTFd/utils/security/email.py` (generate/verify/remove confirm token) | 2 trios (confirm, password reset) | 256-bit nonce from `os.urandom`; guard caps the default lifetime at 30 min |
| `config.mail_provider_configured` | `CTFd/utils/config/__init__.py:mailgun` | 2 (`mailgun`, `mailserver`) | |
| `user.cached_lookup` | `CTFd/utils/user/__init__.py:get_team_place` | 4 (user/team place/score) | |
| `helpers.flash_for` | `CTFd/utils/helpers/__init__.py:info_for` | 2 (`info_for`, `error_for`) | |
| `challenges.decay_linear` | `CTFd/plugins/dynamic_challenges/decay.py:linear` (+ `get_solve_count`) | 2 copies (`plugins/challenges/decay.py` duplicates it) | `== False` comparisons are SQLAlchemy expressions (kept) |

Candidates skipped: model methods (`Users.score`, `get_fields`, …) and Flask-RESTX
resources (classes); form builders that return classes.
