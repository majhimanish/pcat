"""v5 per-app catalogs (experiments/v5/catalogs/<app>) validate like catalog/ (v5 Part C)."""

from __future__ import annotations

import pytest

from conftest import REPO_ROOT
from pcat import catalog as cat

APPS = ("ctfd", "healthchecks", "lnbits")
GENERIC = ("auth.jwt.create_access_token", "auth.password.pbkdf2", "config.env.load_settings",
           "db.pagination.select_page", "http.get_with_retry.requests", "importers.users_csv.parse",
           "ratelimit.token_bucket.check")


@pytest.mark.parametrize("app", APPS)
def test_v5_catalog_validates_with_tests(app):
    root = REPO_ROOT / "experiments" / "v5" / "catalogs" / app
    assert cat.validate(root, run_tests=True) == []


@pytest.mark.parametrize("app", APPS)
def test_v5_catalog_has_house_and_generic_patterns(app):
    root = REPO_ROOT / "experiments" / "v5" / "catalogs" / app
    patterns = {p.meta.id: p for p in cat.load_catalog(root)}
    assert set(GENERIC) <= set(patterns)
    house = [i for i in patterns if i not in GENERIC]
    assert 8 <= len(house) <= 12
    real = {p.meta.id: p for p in cat.load_catalog(REPO_ROOT)}
    for gid in GENERIC:  # copied unchanged
        assert (patterns[gid].impl_path.read_bytes() == real[gid].impl_path.read_bytes())
        assert patterns[gid].meta == real[gid].meta
    assert (root / "REVIEW.md").is_file()
