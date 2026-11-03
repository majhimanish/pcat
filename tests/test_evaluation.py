"""v3 evaluation scoring on small fixtures (no claude -p calls)."""

from __future__ import annotations

from conftest import REPO_ROOT
from pcat import evaluation

POS = "auth.jwt.create_access_token"


def item(expected, ranked, task="jwt_create", request="r"):
    return {"expected": expected, "ranked": ranked, "task": task if expected else None, "request": request}


def test_retrieval_metrics_threshold_top1_top3_and_false_matches():
    items = [
        item(POS, [(POS, 12.0), ("x", 3.0)]),                  # top-1 hit
        item(POS, [("x", 11.0), (POS, 10.0)]),                 # top-3 only
        item(POS, [(POS, 5.0)]),                               # right but below threshold
        item(None, [("x", 9.5)], request="neg-match"),         # false match
        item(None, [("x", 2.0)]),                              # correct rejection
        item(None, []),
    ]
    m = evaluation.retrieval_metrics(items, threshold=9.0)
    assert (m["positives"], m["negatives"]) == (3, 3)
    assert m["top1"] == round(1 / 3, 4) and m["top3"] == round(2 / 3, 4)
    assert m["top1_ignoring_threshold"] == round(2 / 3, 4)
    assert m["false_match_rate"] == round(1 / 3, 4) and m["false_matches"][0]["request"] == "neg-match"
    assert m["per_task"]["jwt_create"]["top1"] == 1 and len(m["per_task"]["jwt_create"]["misses"]) == 2


def test_calibration_picks_the_middle_of_the_best_gap():
    items = [item(POS, [(POS, 12.0)]), item(POS, [(POS, 14.0)]),
             item(None, [("x", 4.0)]), item(None, [("x", 6.0)])]
    threshold, table = evaluation.calibrate_threshold(items)
    assert threshold == 9.0 and max(r["accuracy"] for r in table) == 1.0


def test_calibration_with_overlap_is_deterministic():
    items = [item(POS, [(POS, 8.0)]), item(None, [("x", 10.0)]), item(POS, [(POS, 12.0)])]
    assert evaluation.calibrate_threshold(items) == evaluation.calibrate_threshold(list(reversed(items)))


def test_clean_request():
    assert evaluation.clean_request('Request: "Write a JWT helper."\n\nMore text') == "Write a JWT helper."
    assert evaluation.clean_request("  `hash   passwords`  ") == "hash passwords"


def test_dev_set_shape():
    items = evaluation.dev_set(REPO_ROOT)
    assert sum(1 for i in items if i["expected"]) == 35 and sum(1 for i in items if not i["expected"]) == 10
    assert evaluation.cataloged_tasks(REPO_ROOT)["password_hash"] == "auth.password.pbkdf2"


def test_library_agreement_and_pattern_match():
    assert evaluation.library_agreement("import jwt\nfrom datetime import datetime\n", ["pyjwt>=2.8,<3"])
    assert not evaluation.library_agreement("from jose import jwt\n", ["pyjwt>=2.8,<3"])
    assert evaluation.library_agreement("import hashlib\n", [])
    assert not evaluation.library_agreement("import requests\n", [])
    check = {"functions": [
        {"pattern": "auth.password.pbkdf2", "pattern_function": "hash_password", "status": "covered"},
        {"pattern": "auth.password.pbkdf2", "pattern_function": "verify_password", "status": "near"},
    ]}
    both = evaluation.pattern_match(check, "auth.password.pbkdf2", ["hash_password", "verify_password"])
    assert both == {"shape": True, "exact": False,
                    "found": {"hash_password": "covered", "verify_password": "near"}}
    assert not evaluation.pattern_match(check, "auth.password.pbkdf2",
                                        ["hash_password", "needs_rehash"])["shape"]
