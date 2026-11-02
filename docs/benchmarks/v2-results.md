# v2 miner benchmark — results

Reproduce with `python scripts/benchmark.py` (clones into `.bench/`, gitignored).
Reports: `.bench/report/` (spec run) and `.bench/report-library/` (library-only run).

## What was mined

| Repository | Tag (pinned) | Commit |
|---|---|---|
| psf/requests | `v2.32.3` | `0e322af87745` |
| pallets/flask | `3.0.3` | `c12a5d874c5a` |
| fastapi/fastapi | `0.115.0` | `40e33e492dbf` |

All three tags existed; no fallback was needed. Canonical rules v2, shape rules v1,
Python 3.11.18, `--jobs 4` on a 4-core container.

## Run time

| Run | Settings | Wall time (cold cache) |
|---|---|---|
| Spec run | defaults (`--min-occurrences 3`) | **1.1 s** |
| Library only | `--exclude 'docs_src/*' --min-occurrences 2` | 0.2 s (warm cache) |

The cold run still had 51 cache hits: identical files share a content hash, and
FastAPI's tutorial folder contains many byte-identical copies.

## Stats (spec run)

| | |
|---|---|
| `.py` files seen / mined | 1,424 / 800 |
| files skipped | 624 test files |
| functions found / mined | 2,100 / 1,215 |
| functions filtered | 777 trivial body, 106 too small, 2 cannot canonicalize |
| fragments mined | 669 |
| function / fragment clusters | **55 / 7** |
| functions inside a cluster | 257 of 1,215 (21.2%) — **all 257 from `fastapi/docs_src/`** |
| clusters spanning more than one repository | **0** |
| function clusters whose members are all exact copies | 54 of 55 |

## Catalog coverage

**0 covered, 0 near-covered (0.0% / 0.0%)** against the 6 seed patterns, in both
runs: no mined function has the exact or literal-blanked shape of a seed's
entry point or whole pattern (binary search, merge sort, group-by, retry,
slugify).

## Top 10 function clusters (spec run)

| # | Cluster | Occ. | Nodes | What the code does |
|---|---|---|---|---|
| 1 | `fn-f389e2b9e859` | 7 | 90 | `create_access_token`: copy claims, set expiry (`now + delta`, default minutes), `jwt.encode` — `Union[timedelta, None]` spelling |
| 2 | `fn-28fdf8d600b4` | 23 | 21 | `update_item` endpoint returning `{"item_id": ..., "item": ...}` |
| 3 | `fn-46bc0613945b` | 16 | 29 | `get_user`: look a username up in a fake DB dict, wrap in `UserInDB` |
| 4 | `fn-1f0485dcaf94` | 11 | 43 | `authenticate_user`: fetch user, verify password, return user or `False` |
| 5 | `fn-11c84954e9b9` | 3 | 183 | `get_current_user` with OAuth2 scopes (`Annotated[...]` parameter style) |
| 6 | `fn-a08804fe4945` | 3 | 177 | same as #5 with `= Depends(...)` default style |
| 7 | `fn-ae1a855eb9ff` | 9 | 43 | `CommonQueryParams.__init__`: store `q`, `skip`, `limit` on `self` (method) |
| 8 | `fn-df06028165ab` | 10 | 38 | test functions inside tutorial files: GET a URL, assert status and JSON (5+5 exact groups) |
| 9 | `fn-ea34a27bdcef` | 6 | 53 | `create_user` endpoint: reject duplicate email with HTTP 400, else create via CRUD |
| 10 | `fn-28b5d1e34fa7` | 4 | 86 | `create_access_token` again, `timedelta \| None` spelling of #1 |

Every one is a FastAPI tutorial snippet repeated across the docs' Python-version
and `Annotated` variants.

## Fragment clusters (spec run — only 7 exist)

| # | Cluster | Occ. | Nodes | What the code does |
|---|---|---|---|---|
| 1 | `fr-9503d49a55cf` | 11 | 38 | token expiry: `now(utc) + delta` if given, else a default `timedelta` |
| 2 | `fr-549ce9943bf1` | 6 | 71 | decode a JWT with scopes, require a username, build `TokenData`; re-raise as credentials error |
| 3 | `fr-79edf0f263a0` | 5 | 53 | same without scopes |
| 4 | `fr-9c04564bcce1` | 5 | 53 | websocket echo loop (`receive_text` / `send_text`) |
| 5 | `fr-046421f83ff3` | 6 | 32 | every required scope must be granted, else HTTP 401 |
| 6 | `fr-bc4a7e15c197` | 3 | 30 | per-request DB session middleware (`try` / `finally: close()`) |
| 7 | `fr-d7b569359c8c` | 3 | 27 | `fastapi/security/http.py`: missing credentials → 403 if `auto_error`, else `None` |

Only #7 is library code.

## Library-only run (`docs_src/` excluded, pairs allowed)

674 functions mined; **15 function clusters and 13 fragment clusters, all pairs except
one triple, none across repositories**; 30 functions (4.5%) are in a cluster, and 12
of the 15 function clusters are methods (which cannot be promoted). Representative:

- Flask: `Flask` and `Blueprint` share `open_resource`, `send_static_file`,
  `get_send_file_max_age`; `_make_timedelta` is duplicated in `app.py` and
  `sansio/app.py`; `AppContext.__exit__` = `RequestContext.__exit__`.
- FastAPI: `Query/Cookie.__init__` and `Form/File.__init__` (≈430 nodes each),
  `OAuth2PasswordBearer`/`OAuth2AuthorizationCodeBearer.__call__`,
  `APIRoute`/`APIWebSocketRoute.matches`, two exception `__init__`s.
- requests: one fragment shared by `parse_list_header` / `parse_dict_header`.
- Tooling noise: `.github/actions/*` and `scripts/` contribute several pairs.

## Assessment

**On this corpus, the evidence does not support the project's premise — but the
corpus is the wrong test of it, and part of the result points the right way.**

- Mature, single-team libraries barely repeat themselves: no function shape occurs
  three times in library code, and nothing repeats across the three projects. The
  duplication that exists is deliberate API symmetry (Flask/Blueprint, parameter
  classes), mostly methods, and is better solved by refactoring than a catalog.
- The seed catalog (textbook algorithms) covers nothing. A useful catalog would
  be made of *application* idioms, not algorithms.
- The one place with heavy repetition, FastAPI's tutorials, is exactly the code
  application developers copy into their own services: JWT creation and
  decoding, `authenticate_user`, `get_current_user`, scope checks, DB session
  middleware, uniqueness check before create. That is the "every prompt produces a
  slightly different variant" problem the catalog targets, but here it is
  documentation, not production code.
- So the riskiest question is still open. The next benchmark should mine
  *application* repositories (internal services, or a corpus of open-source
  FastAPI/Flask/Django apps), where these tutorial idioms land with variations.

## Noise and how filtering could improve

1. **Docs and examples dominate.** All default-run clusters come from `docs_src/`.
   Default-skip `docs_src/`, `docs/`, `examples/`, and report byte-identical files
   (51 here) separately instead of counting each copy.
2. **Annotation spelling splits clusters.** `Union[X, None]` vs `X | None` vs
   `Annotated[X, Depends()]` put the same code in different clusters (#1/#10, #5/#6).
   An annotation-insensitive shape level would merge them.
3. **Test functions in non-test files** (`test_*` functions inside `tutorialNNN.py`)
   are mined. Filter functions named `test_*` as well as test files.
4. **Exact copies, not near-misses.** 54 of 55 clusters have a single exact
   sub-group: shape matching added little because free names (called functions,
   attributes) must match exactly. A looser level that also abstracts free names
   would find idioms that differ only in which API they call — at the price of
   more noise, so it should be a separate, lower-ranked section.
5. **Trivial-body filter is large** (777 of 2,100, 37%): it removes single-`return`
   endpoints and properties, which is mostly right, but would also hide one-line
   idioms.
6. **Repository tooling** (`.github/`, `scripts/`) shows up in library-only pairs;
   consider skipping hidden directories by default.
