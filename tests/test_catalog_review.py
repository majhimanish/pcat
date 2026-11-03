"""Consistency of the v2.2 catalog review (docs/catalog-review/).

Variant tests themselves live next to the variants; this only checks that the
review is complete and that every variant could become a catalog pattern.
"""

from __future__ import annotations

import re

import pytest
import yaml

from conftest import REPO_ROOT
from pcat import canonical
from pcat.schema import ID_PATTERN

REVIEW = REPO_ROOT / "docs" / "catalog-review"
VARIANTS = REVIEW / "variants"
TASKS = list(yaml.safe_load((REPO_ROOT / "experiments" / "variance" / "tasks.yaml").read_text())["tasks"])


def variant_files():
    return sorted(p for p in VARIANTS.glob("*/*.py") if not p.name.startswith("test_"))


def test_every_task_has_two_to_four_options():
    for task in TASKS:
        names = [p.stem for p in (VARIANTS / task).glob("*.py") if not p.name.startswith("test_")]
        options = len(names) + (task == "fastapi_create_user")  # + the "defer" option
        assert 2 <= options <= 4, task


@pytest.mark.parametrize("path", variant_files(), ids=lambda p: p.stem)
def test_variant_is_catalog_ready_and_tested(path):
    canonical.analyze(path.read_text(encoding="utf-8"))  # only functions, literal constants, imports
    assert (path.parent / f"test_{path.name}").is_file()
    assert "﻿" not in path.read_text(encoding="utf-8")


def test_variant_module_names_are_unique():
    names = [p.stem for p in variant_files()]
    assert len(names) == len(set(names))  # they share one pytest session


def test_choices_cover_all_tasks_with_valid_values():
    data = yaml.safe_load((REVIEW / "choices.yaml").read_text())
    assert data["status"] in ("draft", "final")
    assert list(data["choices"]) == TASKS
    for task, choice in data["choices"].items():
        options = {p.stem for p in (VARIANTS / task).glob("*.py") if not p.name.startswith("test_")}
        assert choice["variant"] in options | {"defer"}, task
        assert re.fullmatch(ID_PATTERN, choice["pattern_id"]), task
        assert isinstance(choice["notes"], str)


def test_comparison_mentions_every_variant_and_recommendation():
    doc = (REVIEW / "v2.2-comparison.md").read_text()
    for path in variant_files():
        assert f"### `{path.stem}`" in doc
    choices = yaml.safe_load((REVIEW / "choices.yaml").read_text())["choices"]
    for task, choice in choices.items():
        assert f"## {task} " in doc and f"### Recommendation: `{choice['variant']}`" in doc
