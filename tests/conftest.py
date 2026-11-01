"""Shared fixtures: a disposable copy of the real seed catalog."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_IDS = [
    "collections.group_by.dict_of_lists",
    "retry.with_exponential_backoff",
    "search.binary_search.iterative",
    "search.binary_search.recursive",
    "sort.merge_sort.recursive",
    "text.slugify.ascii",
]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A temporary repository root holding a copy of the seed catalog."""
    shutil.copytree(
        REPO_ROOT / "catalog",
        tmp_path / "catalog",
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
    )
    return tmp_path


def pattern_dir(root: Path, pattern_id: str, version: int = 1) -> Path:
    category, rest = pattern_id.split(".", 1)
    return root / "catalog" / category / (rest if version == 1 else f"{rest}@v{version}")


def edit_yaml(folder: Path, **changes) -> None:
    path = folder / "pattern.yaml"
    data = yaml.safe_load(path.read_text())
    data.update(changes)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
