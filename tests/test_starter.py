"""Packaging (v6 Part B): the starter catalog and the wheel's contents."""

from __future__ import annotations

import subprocess
import sys
import zipfile

import pytest

from conftest import REPO_ROOT
from pcat import __version__
from pcat import catalog as cat
from pcat import starter

RESEARCH = ("variance", "evaluation", "linteval", "v5", "rescore", "v52", "derivation")


def test_starter_matches_the_reviewed_catalog():
    """scripts/sync_starter_catalog.py keeps these copies identical to catalog/."""
    root = starter.catalog_root()
    found = sorted(p.meta.id for p in cat.load_catalog(root) if p.meta)
    assert found == sorted(starter.PATTERN_IDS)
    for pid in starter.PATTERN_IDS:
        mine, theirs = cat.get_one(root, pid).folder, cat.get_one(REPO_ROOT, pid).folder
        for name in starter.FILES:
            assert (mine / name).read_bytes() == (theirs / name).read_bytes(), (pid, name)
    assert cat.validate(root, run_tests=False) == []


def test_version():
    from typer.testing import CliRunner

    from pcat.cli import app

    r = CliRunner().invoke(app, ["--version"])
    assert r.exit_code == 0 and r.output.strip() == f"pcat {__version__}" == "pcat 0.1.0"


def test_wheel_has_product_code_and_the_starter_only(tmp_path):
    pytest.importorskip("setuptools")
    proc = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q",
                           "-w", str(tmp_path), str(REPO_ROOT)], capture_output=True, text=True)
    if proc.returncode != 0:
        pytest.skip(f"cannot build a wheel here: {proc.stderr[-300:]}")
    [wheel] = tmp_path.glob("pcat-0.1.0-*.whl")
    names = zipfile.ZipFile(wheel).namelist()
    assert not [n for n in names if n.startswith(("pcatlab", "experiments", "scripts", "tests"))]
    assert not [n for n in names if n in {f"pcat/{m}.py" for m in RESEARCH}]
    for pid in starter.PATTERN_IDS:
        category, rest = pid.split(".", 1)
        for name in starter.FILES:
            assert f"pcat/starter/catalog/{category}/{rest}/{name}" in names
    assert "pcat/starter/catalog/index.json" in names
