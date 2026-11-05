"""Shared helpers for the research tests (mirrors tests/conftest.py)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

collect_ignore = ["fixtures_variance"]

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / "fixtures_variance"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copytree(REPO_ROOT / "catalog", tmp_path / "catalog",
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return tmp_path


def pattern_dir(root: Path, pattern_id: str, version: int = 1) -> Path:
    category, rest = pattern_id.split(".", 1)
    return root / "catalog" / category / (rest if version == 1 else f"{rest}@v{version}")


def edit_yaml(folder: Path, **changes) -> None:
    path = folder / "pattern.yaml"
    data = yaml.safe_load(path.read_text())
    data.update(changes)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
