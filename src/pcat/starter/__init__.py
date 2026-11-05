"""The starter catalog shipped with pcat: the 7 generic application patterns.

`pcat init --starter` copies `catalog/` from here into a repository. The files are copies
of the reviewed patterns in pcat's own catalog (kept identical by
scripts/sync_starter_catalog.py and tests/test_starter.py).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATTERN_IDS = (
    "auth.jwt.create_access_token",
    "auth.password.pbkdf2",
    "config.env.load_settings",
    "db.pagination.select_page",
    "http.get_with_retry.requests",
    "importers.users_csv.parse",
    "ratelimit.token_bucket.check",
)
FILES = ("pattern.yaml", "impl.py", "test_impl.py")


def catalog_root() -> Path:
    """Directory holding the starter `catalog/` (a valid pcat root)."""
    return ROOT
