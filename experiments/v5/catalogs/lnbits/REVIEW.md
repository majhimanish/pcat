# LNbits catalog — review record (v5)

**Reviewer:** the agent that built v5 (Claude), *not* an LNbits maintainer or the pcat
owner: a self-review by one person who did not write the code.

**Source:** LNbits v1.6.2 (`9349da153c223b008f7d80453b53a54e09c8ed3d`).

## What was reviewed, and how

Same procedure as the other catalogs. FastAPI and the `lnbits` package are **stubbed**
in the tests (not installed); async functions run with `asyncio.run`;
`auth.lnbits_access_token` uses the real PyJWT (skips without the `catalog` extra).
Not run inside the app. The 7 generic patterns are copied unchanged.

## Patterns

| Id | Source | Occurrences | Notes |
|---|---|---|---|
| `validators.regex_match` | `lnbits/helpers.py:is_valid_username` | 3 (username, email, label) | |
| `crud.get_account_by_field` | `lnbits/core/crud/users.py:get_account_by_username` | 3 (username, email, username-or-email) | **edited:** `from ..models import Account` → `from lnbits.core.models import Account` (relative import cannot work outside the package) |
| `crud.count_rows` | `lnbits/core/crud/users.py:get_accounts_count` | 2 | |
| `crud.delete_by_ext_id` | `lnbits/core/crud/db_versions.py:delete_dbversion` | 2 | |
| `auth.require_api_key` | `lnbits/decorators.py:require_admin_key` | 4 (admin/invoice × full/base) | hand-assembled imports (`KeyChecker`, `api_key_header`, `api_key_query` from `lnbits.decorators`); **tooling gap:** the parameter names shadow the module objects used in their defaults, so `pcat add` dropped those imports; restored by hand |
| `auth.check_admin` | `lnbits/decorators.py:check_admin` | 2 (`check_admin`, `check_super_user`) | hand-assembled imports (`check_account_exists` from `lnbits.decorators`) |
| `security.check_callback_url` | `lnbits/helpers.py:check_callback_url` | 1 | SSRF guard: scheme, credentials, port and origin allowlist |
| `auth.lnbits_access_token` | `lnbits/helpers.py:create_access_token` | 1 | overlaps the generic `auth.jwt.create_access_token` (same function name). **Concern:** no `iss`/`aud`/`jti`, unlike the generic pattern; kept verbatim (house code) |

Candidates skipped: wallet and fiat provider methods (`cleanup`, `paid_invoices_stream`),
Pydantic validators and `KeyChecker` (classes).
