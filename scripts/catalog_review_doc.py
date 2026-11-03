"""Regenerate docs/catalog-review/v2.2-comparison.md from the variant files.

Run from the repository root: python scripts/catalog_review_doc.py
Code blocks are copied from docs/catalog-review/variants/, so the doc cannot drift
from the tested code. choices.yaml is only written if it does not exist yet, so
the owner's edits are never overwritten.
"""

import ast
from pathlib import Path

ROOT = Path("docs/catalog-review")
VAR = ROOT / "variants"


def code_of(task, variant, excerpt=None):
    src = (VAR / task / f"{variant}.py").read_text()
    tree = ast.parse(src)
    doc = tree.body[0]
    lines = src.splitlines()
    if isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant):
        lines = lines[doc.end_lineno:]
    while lines and not lines[0].strip():
        lines.pop(0)
    if excerpt:
        start = next(i for i, l in enumerate(lines) if excerpt[0] in l)
        end = next(i for i, l in enumerate(lines) if excerpt[1] in l)
        lines = lines[start:end + 1] + ["    # ... row validation identical to text_stream ..."]
    return "\n".join(lines)


TASKS = [
    {
        "task": "jwt_create",
        "title": "Create a JWT access token",
        "split": "All 40 samples used PyJWT with HS256. 31 added the registered claims "
                 "iss/aud/nbf/jti, 9 used only sub/iat/exp. 37 read the secret from an "
                 "environment variable inside the function; 26 used epoch integers, 14 "
                 "timezone-aware datetimes.",
        "variants": [
            {
                "label": "jwt_minimal_claims", "count": "9 of 40", "from": "B09",
                "decision": "Minimal claims: `sub`, `iat`, `exp` only.",
                "changes": [
                    "Secret is a parameter (was read from `JWT_SECRET` at import time).",
                    "Rejects secrets shorter than 32 bytes, non-positive expiry and naive `now`.",
                    "Clock injectable via `now` (aware datetime); type hints added.",
                ],
                "security": [
                    "Weak HMAC keys are brute-forceable: minimum 32 bytes enforced (RFC 7518).",
                    "No `aud`/`iss`: a token minted for one service is accepted by any other "
                    "service sharing the secret.",
                    "Verifiers must pin `algorithms=[\"HS256\"]` (prevents `alg` confusion); "
                    "this pattern only creates tokens.",
                ],
                "pros": ["Smallest token and code; fine when one service both issues and verifies."],
                "cons": ["No revocation handle (`jti`) and no audience binding."],
            },
            {
                "label": "jwt_registered_claims", "count": "31 of 40", "from": "A07",
                "decision": "Registered claims: adds `iss`, `aud`, `nbf` and a random `jti`.",
                "changes": [
                    "Epoch integers from `time.time()` replaced by an injectable aware datetime.",
                    "Same input validation and 32-byte secret minimum as the minimal variant.",
                    "`issuer`/`audience` are required parameters instead of optional.",
                ],
                "security": [
                    "`aud`/`iss` bind the token to one issuer and one consumer (blocks "
                    "cross-service replay) once verifiers check them.",
                    "`jti` (128-bit random) makes deny-listing a single token possible.",
                    "Same key-length and algorithm-pinning notes as the minimal variant.",
                ],
                "pros": ["What most samples converged on; safe default for multi-service systems."],
                "cons": ["Two more required parameters; verifiers must pass `audience=` and `issuer=`."],
            },
        ],
        "recommend": "jwt_registered_claims",
        "reason": "It is what 31 of 40 samples produced unprompted, and audience/issuer "
                  "binding is cheap insurance once more than one service shares a key. "
                  "`jti` costs nothing and keeps revocation possible later.",
        "pattern_id": "auth.jwt.create_access_token",
    },
    {
        "task": "password_hash",
        "title": "Hash and verify passwords",
        "split": "No sample used a third-party library. 29 used `hashlib.scrypt`, 11 "
                 "PBKDF2-HMAC-SHA256; all 40 stored the parameters in the hash string and "
                 "compared with `hmac.compare_digest`.",
        "variants": [
            {
                "label": "password_scrypt", "count": "29 of 40", "from": "B08",
                "decision": "Memory-hard scrypt (N=2^17, r=8, p=1).",
                "changes": [
                    "Base64 decoded with `validate=True`; malformed input returns `False`.",
                    "Rejects `p > 16` and bounds memory with `maxmem` so a tampered hash "
                    "cannot demand unbounded resources.",
                    "Cost parameters overridable (tests use cheap ones; verify reads them from the hash).",
                ],
                "security": [
                    "Memory hardness makes GPU/ASIC cracking far costlier than PBKDF2.",
                    "Constant-time comparison; per-hash 16-byte random salt.",
                    "Each hash needs about 128 MiB: 100 concurrent logins need about 12.5 GiB. "
                    "Rate-limit login, or lower N (e.g. 2^16 with p=2).",
                ],
                "pros": ["Strongest of the standard-library options."],
                "cons": ["High memory per hash; not FIPS-approved."],
            },
            {
                "label": "password_pbkdf2", "count": "11 of 40", "from": "B01",
                "decision": "PBKDF2-HMAC-SHA256 with 600,000 iterations.",
                "changes": [
                    "Iteration count bounded (1..10,000,000) when verifying.",
                    "Base64 decoded with `validate=True`; malformed input returns `False`.",
                ],
                "security": [
                    "OWASP 2023 minimum iteration count; constant-time comparison; random salt.",
                    "Not memory-hard: GPUs crack it much faster than scrypt for the same CPU cost.",
                ],
                "pros": ["FIPS 140 approved; tiny memory use; predictable cost."],
                "cons": ["Weaker against offline cracking than scrypt."],
            },
        ],
        "recommend": "password_scrypt",
        "reason": "Memory hardness is the property that matters for stored passwords, it is "
                  "in the standard library, and most samples chose it. Pick PBKDF2 instead "
                  "if FIPS compliance is required or login traffic cannot be rate-limited.",
        "pattern_id": "auth.password.scrypt",
    },
    {
        "task": "paginate_query",
        "title": "Paginate a SQLAlchemy query",
        "split": "27 samples took a session and a 2.0-style `select()`, 13 a legacy `Query` "
                 "object. 34 returned `(items, total)`, 5 a dict with page metadata. 31 "
                 "raised on a bad page number, 9 clamped it. All counted over a subquery.",
        "variants": [
            {
                "label": "paginate_tuple", "count": "27 (2.0 API); 34 (tuple)", "from": "B18",
                "decision": "2.0 `select()` + session; returns `(items, total)`.",
                "changes": [
                    "Moved from the legacy `Query` API (sample B18) to `session.execute(select)`.",
                    "Page size capped at 100; entity selects return objects, column selects rows.",
                ],
                "security": [
                    "Unbounded `page_size` lets a client request the whole table: capped.",
                    "Large page numbers still mean large OFFSETs (slow scans); keyset "
                    "pagination is the fix if that matters.",
                    "The caller builds the select, so parameter binding stays SQLAlchemy's job.",
                ],
                "pros": ["Smallest interface; composes with any response format."],
                "cons": ["Every endpoint recomputes page counts its own way."],
            },
            {
                "label": "paginate_page_dict", "count": "5 of 40", "from": "B19",
                "decision": "2.0 `select()` + session; returns `items, total, page, page_size, pages`.",
                "changes": [
                    "Page size capped at 100; `pages` computed with integer arithmetic.",
                    "A page past the end returns empty items with real totals (not an error).",
                ],
                "security": ["Same page-size cap and OFFSET note as the tuple variant."],
                "pros": ["One standard paginated response shape across services."],
                "cons": ["Fixes the metadata field names for everyone."],
            },
            {
                "label": "paginate_legacy_query", "count": "13 of 40", "from": "B18",
                "decision": "Legacy ORM `Query` object (`session.query(...)`), `query.count()`.",
                "changes": ["Page size capped at 100; `order_by(None)` before counting."],
                "security": ["Same page-size cap and OFFSET note as the tuple variant."],
                "pros": ["Fits code bases still on the 1.x Query API."],
                "cons": ["SQLAlchemy 2.0 calls this API legacy; new code should not adopt it."],
            },
        ],
        "recommend": "paginate_page_dict",
        "reason": "The 2.0 API is the one to standardise on, and returning the page metadata "
                  "removes the most common place endpoints diverge (field names and page "
                  "maths). If you prefer the smallest building block, choose `paginate_tuple`.",
        "pattern_id": "db.pagination.select_page",
    },
    {
        "task": "http_retry",
        "title": "GET a URL with retries and exponential backoff",
        "split": "32 samples used `requests`, 8 the standard library's `urllib`. 36 retried "
                 "429 and 5xx, 23 honoured `Retry-After`, all 40 added random jitter, only 2 "
                 "made `sleep` injectable.",
        "variants": [
            {
                "label": "retry_requests", "count": "32 of 40", "from": "A08",
                "decision": "`requests` with an injectable `Session`.",
                "changes": [
                    "Session, `sleep` and the random source injected (tests use no network or clock).",
                    "Added `Retry-After` (seconds form), capped at `max_delay`; full jitter.",
                    "Always passes a timeout; 4xx (except 429) fails immediately.",
                ],
                "security": [
                    "If the URL comes from users this is an SSRF vector: validate hosts before calling.",
                    "Server-controlled `Retry-After` is capped so it cannot stall the caller.",
                    "Only GET is retried; retrying non-idempotent requests could duplicate effects.",
                ],
                "pros": ["Idiomatic, connection pooling via the session, rich errors."],
                "cons": ["Third-party dependency (`requests>=2.31,<3`)."],
            },
            {
                "label": "retry_urllib", "count": "8 of 40", "from": "B19",
                "decision": "Standard library `urllib.request`.",
                "changes": [
                    "Rejects non-http(s) URLs: `urlopen` would otherwise read `file://` paths.",
                    "`urlopen`, `sleep` and the random source injected; `Retry-After` added.",
                    "Stopped retrying 408 (kept 429 and 5xx) to match the requests variant.",
                ],
                "security": [
                    "`file://` local-file reads blocked; SSRF note as above.",
                    "Returns the whole body in memory: cap response size for untrusted servers.",
                ],
                "pros": ["No dependency."],
                "cons": ["No connection pooling; lower-level error handling."],
            },
        ],
        "recommend": "retry_requests",
        "reason": "Most services already depend on `requests`, the session makes it testable "
                  "and pooled, and it avoids `urllib`'s `file://` trap. Choose `retry_urllib` "
                  "if dependency-free code matters more.",
        "pattern_id": "http.get_with_retry.requests",
    },
    {
        "task": "env_config",
        "title": "Load and validate settings from environment variables",
        "split": "35 samples hard-coded the settings and parsed each one, 5 took a schema "
                 "parameter. 33 collected every error before raising, 7 stopped at the "
                 "first. 15 defined a custom exception class (invalid under catalog rules).",
        "variants": [
            {
                "label": "env_collect_errors", "count": "28 of 40", "from": "A16",
                "decision": "Fixed fields; collect all errors, raise once.",
                "changes": [
                    "Reads an injectable mapping (`os.environ` by default).",
                    "`ValueError` instead of a custom exception class.",
                    "`DATABASE_URL` is never echoed in errors (it often contains a password).",
                ],
                "security": [
                    "Secrets in error messages end up in logs: the URL value is never printed.",
                    "Fails at startup instead of running half-configured.",
                ],
                "pros": ["Readable; one deploy shows every misconfiguration."],
                "cons": ["The field list is app-specific, so each service edits it."],
            },
            {
                "label": "env_fail_fast", "count": "7 of 40", "from": "B03",
                "decision": "Fixed fields; raise on the first error.",
                "changes": ["Same fields, parsing and secret handling as the collecting variant."],
                "security": ["Same as the collecting variant."],
                "pros": ["Simplest control flow."],
                "cons": ["Fix-one-redeploy-repeat when several values are wrong."],
            },
            {
                "label": "env_schema_loader", "count": "5 of 40", "from": "B04",
                "decision": "Generic loader: the caller passes `{name: (parser, default)}`.",
                "changes": [
                    "Required values marked with `...`; `secret_names` keeps values out of errors.",
                    "`ValueError` listing all errors; injectable mapping.",
                ],
                "security": [
                    "Caller lists secret variables; their values are never echoed.",
                    "Parsers are caller code: a parser that logs its input would leak secrets.",
                ],
                "pros": ["Reusable unchanged by every service: only the schema differs."],
                "cons": ["One level of indirection; types come from the parsers, not annotations."],
            },
        ],
        "recommend": "env_schema_loader",
        "reason": "A catalog pattern has to be reusable without editing; the fixed-field "
                  "variants are templates every service would change, so their fingerprints "
                  "would never match. The schema loader keeps the collect-all-errors and "
                  "no-secret-echo behaviour and moves only the field list to the caller.",
        "pattern_id": "config.env.load_settings",
    },
    {
        "task": "token_bucket",
        "title": "Token-bucket rate limit in a dict",
        "split": "All 40 samples kept a token count and timestamp per key in the dict (36 "
                 "named it `last`), started new keys full and used `time.monotonic()` with an "
                 "injectable `now`. 26 returned `bool`, 14 `(allowed, retry_after)`.",
        "variants": [
            {
                "label": "bucket_bool", "count": "26 of 40", "from": "B08",
                "decision": "Returns `True`/`False`.",
                "changes": ["Rejects non-positive capacity, refill rate and cost; type hints."],
                "security": [
                    "The dict grows with every new key: with client-chosen keys (IPs, tokens) "
                    "evict idle buckets or cap the dict, or it is a memory DoS.",
                    "Per process, not thread-safe: use a lock or a shared store (Redis) for "
                    "multi-worker limits.",
                    "Key choice matters: trusting `X-Forwarded-For` lets clients pick their own key.",
                ],
                "pros": ["Simplest interface."],
                "cons": ["Callers cannot tell clients when to retry."],
            },
            {
                "label": "bucket_retry_after", "count": "14 of 40", "from": "A06",
                "decision": "Returns `(allowed, retry_after_seconds)`.",
                "changes": [
                    "`cost > capacity` raises `ValueError` (the sample returned `inf` seconds).",
                    "Same input validation as the bool variant.",
                ],
                "security": ["Same as the bool variant."],
                "pros": ["Gives the value for an HTTP `Retry-After` header on 429 responses."],
                "cons": ["Tuple return is slightly more to handle."],
            },
        ],
        "recommend": "bucket_retry_after",
        "reason": "Rate limiters usually answer HTTP clients, and a correct `Retry-After` "
                  "needs the wait time that only the limiter knows. It is a superset of the "
                  "bool variant (`allowed, _ = ...`).",
        "pattern_id": "ratelimit.token_bucket.check",
    },
    {
        "task": "csv_import",
        "title": "Import users from CSV with per-row errors",
        "split": "All 40 samples used `csv.DictReader` and checked the header. 30 accepted "
                 "text or a file object, 10 a file path. 36 returned a list of error "
                 "records, 4 a dict keyed by row. All 40 checked email with a regex; 23 used "
                 "exactly `^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$`.",
        "variants": [
            {
                "label": "csv_text_stream", "count": "30 of 40", "from": "A09",
                "decision": "Input is CSV text or a text stream.",
                "changes": [
                    "Email checked without a regex. The samples' regex backtracks "
                    "quadratically: measured 0.7 s on a 16 KB field, and CSV allows 128 KB fields.",
                    "Row limit (`max_rows`), email length limit, too-many-fields detection.",
                    "Error messages never echo field values (PII in logs); BOM-safe header.",
                ],
                "security": [
                    "ReDoS removed; bounded work per file via `max_rows`.",
                    "Values not echoed in errors.",
                    "If imported data is ever exported to a spreadsheet, escape leading "
                    "`= + - @` (CSV formula injection).",
                ],
                "pros": ["Works for uploads and files alike; easy to test."],
                "cons": ["Callers open files themselves."],
            },
            {
                "label": "csv_file_path", "count": "10 of 40", "from": "B07",
                "decision": "Input is a file path, streamed from disk.",
                "changes": [
                    "Same validation as `csv_text_stream`.",
                    "Opens with `newline=\"\"` and `utf-8-sig` (handles Excel's BOM).",
                ],
                "security": [
                    "Same as `csv_text_stream`. Never pass a user-supplied path (path traversal).",
                ],
                "pros": ["Convenient for batch jobs reading local files."],
                "cons": ["Tied to the filesystem; HTTP uploads need a temp file."],
            },
        ],
        "recommend": "csv_text_stream",
        "reason": "Accepting text or any stream covers both uploads and files without "
                  "touching the filesystem, and most samples chose it. The validation logic "
                  "is identical, so this only fixes the input type.",
        "pattern_id": "importers.users_csv.parse",
        "excerpts": {"csv_file_path": ("def import_users_file", "missing = [c")},
    },
    {
        "task": "fastapi_create_user",
        "title": "FastAPI create-user endpoint",
        "split": "37 of 40 samples defined Pydantic model classes (catalog patterns cannot "
                 "contain classes yet). 3 validated individual `Body()` fields instead. 26 "
                 "were `async`, 12 used `Annotated` dependencies, all 40 returned 409 on conflict.",
        "variants": [
            {
                "label": "fastapi_body_params", "count": "3 of 40", "from": "B11",
                "decision": "Class-free: each JSON field is a validated `Body()` parameter.",
                "changes": [
                    "Routes registered by `register_routes(app)` (no module-level `app`).",
                    "Repository and password hasher injected; both fail closed until wired.",
                    "Removed the sample's in-memory store; minimum password length 12.",
                ],
                "security": [
                    "The password is hashed by an injected hasher and never returned or echoed.",
                    "Field length limits and a non-backtracking email pattern.",
                    "Uniqueness is the repository's job: a unique constraint is needed to "
                    "avoid races. Add rate limiting before exposing signup.",
                    "409 reveals that an account exists (enumeration); usually acceptable at signup.",
                ],
                "pros": ["Works today under catalog rules; OpenAPI still documents the fields."],
                "cons": ["Not how FastAPI code is normally written; no reusable request/response models."],
            },
            {
                "label": "defer", "count": "37 of 40 used Pydantic models", "from": None,
                "decision": "Wait until patterns can contain classes, then catalog the Pydantic version.",
                "changes": [], "security": [],
                "pros": ["The catalog would teach idiomatic FastAPI."],
                "cons": ["No FastAPI pattern until class support is built."],
            },
        ],
        "recommend": "defer",
        "reason": "v2.1 showed the model copies a reference faithfully, so a class-free "
                  "endpoint would spread non-idiomatic FastAPI across every service. Better "
                  "to add class support to patterns first. The tested class-free variant "
                  "stays here as a fallback.",
        "pattern_id": "web.fastapi.create_user",
    },
]


def bullets(items):
    return "\n".join(f"- {i}" for i in items)


def main():
    out = [
        "# v2.2 — application catalog: variants to choose from",
        "",
        "Part 1 of `docs/specs/v2.2-app-catalog.md`. For each of the 8 tasks from the v2.1 "
        "experiment, the 40 samples of conditions A and B were grouped by the design "
        "decisions they made (not by fingerprint). One sample per group was cleaned to "
        "catalog rules and tested. **Recommendations are marked ✅; choose in "
        "`choices.yaml`.**",
        "",
        "- Code: `docs/catalog-review/variants/<task>/<variant>.py`, tests next to it.",
        "- Third-party versions: `docs/catalog-review/requirements.txt`.",
        "- Counts are out of the 40 A+B samples per task (including samples that were "
        "invalid in v2.1 because they defined classes).",
        "- Common cleanup: standalone functions, literal-only constants, no classes; "
        "secrets, URLs, clocks, `sleep`, randomness and transports are parameters.",
        "",
        "## Decisions for the owner",
        "",
        "1. `fastapi_create_user`: defer (recommended) or the class-free variant?",
        "2. `env_config`: the recommended schema loader is a minority choice (5/40), "
        "picked because it is reusable unchanged.",
        "3. `password_hash`: scrypt's 128 MiB per hash vs PBKDF2's FIPS approval.",
        "4. `http_retry`: accept the `requests` dependency, or prefer the standard library?",
        "5. `paginate_query`: page-metadata dict (recommended) or plain `(items, total)`?",
        "6. Pattern ids in `choices.yaml` are proposals.",
        "",
        "## Recommendations at a glance",
        "",
    ]
    for t in TASKS:
        out.append(f"- **{t['task']}** → `{t['recommend']}`")
    choices_path = ROOT / "choices.yaml"
    if choices_path.exists():
        import yaml

        final = yaml.safe_load(choices_path.read_text())
        if final.get("status") == "final":
            out += ["", "## Owner's decisions (final)", ""]
            for task, choice in final["choices"].items():
                rec = next(t["recommend"] for t in TASKS if t["task"] == task)
                note = "" if choice["variant"] == rec else " (differs from the recommendation)"
                target = "deferred" if choice["variant"] == "defer" else f"pattern `{choice['pattern_id']}`"
                out.append(f"- **{task}** → `{choice['variant']}`, {target}{note}")
    for t in TASKS:
        out += ["", "---", "", f"## {t['task']} — {t['title']}", "", f"**How the samples split:** {t['split']}", ""]
        for v in t["variants"]:
            mark = " ✅ recommended" if v["label"] == t["recommend"] else ""
            out += [f"### `{v['label']}`{mark}", "", f"**Decision:** {v['decision']}  ", f"**Samples:** {v['count']}"
                    + (f" (cleaned from sample {v['from']})" if v["from"] else ""), ""]
            if v["label"] != "defer":
                excerpt = t.get("excerpts", {}).get(v["label"])
                out += ["```python", code_of(t["task"], v["label"], excerpt), "```", ""]
            if v["changes"]:
                out += ["**Changed from the sample:**", bullets(v["changes"]), ""]
            if v["security"]:
                out += ["**Security notes:**", bullets(v["security"]), ""]
            out += ["**Pros:** " + " ".join(v["pros"]) + "  ", "**Cons:** " + " ".join(v["cons"]), ""]
        out += [f"### Recommendation: `{t['recommend']}`", "", t["reason"], ""]
    coverage = ROOT / "v2.2-coverage.md"  # Part 2 coverage check, appended verbatim
    if coverage.exists():
        out += ["", "---", "", coverage.read_text().rstrip()]
    (ROOT / "v2.2-comparison.md").write_text("\n".join(out).rstrip() + "\n")

    y = [
        "# Owner's choices for v2.2 Part 2 (docs/specs/v2.2-app-catalog.md).",
        "# Change status to final when done; Part 2 then turns each choice into a catalog",
        "# pattern. variant: one of the labels listed for the task, or defer.",
        "status: draft          # owner changes to: final",
        "choices:",
    ]
    for t in TASKS:
        labels = ", ".join(v["label"] for v in t["variants"] if v["label"] != "defer")
        y += [
            f"  {t['task']}:",
            f"    # options: {labels}, defer",
            f"    variant: {t['recommend']}",
            f"    pattern_id: {t['pattern_id']}",
            '    notes: ""',
        ]
    if not (ROOT / "choices.yaml").exists():
        (ROOT / "choices.yaml").write_text("\n".join(y) + "\n")


main()
