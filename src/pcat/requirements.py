"""`requires` vs imports (v5.1 Part C). Standard library + PyYAML only.

A pattern's `requires` lists pip distributions; code imports modules. The two
names differ for some distributions (`pyjwt` is imported as `jwt`). This module
maps one to the other (a built-in table, overridable per pattern with
`import_names`) and finds the third-party modules a source file imports, for
validation check 12 and for PC103.

Modules of the organization's own application (`lnbits`, `CTFd`, ...) are not
third-party: a catalog lists them as `first_party` in `catalog/catalog.yaml`.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Mapping
from pathlib import Path

import yaml

# distribution (lowercase, as pip normalizes it) -> top-level import name
KNOWN_IMPORT_NAMES: dict[str, str] = {
    "attrs": "attr",
    "beautifulsoup4": "bs4",
    "dnspython": "dns",
    "google-cloud-storage": "google",
    "opencv-python": "cv2",
    "pillow": "PIL",
    "protobuf": "google",
    "psycopg2-binary": "psycopg2",
    "psycopg-binary": "psycopg",
    "pycryptodome": "Crypto",
    "pyjwt": "jwt",
    "pymupdf": "fitz",
    "pyopenssl": "OpenSSL",
    "python-dateutil": "dateutil",
    "python-dotenv": "dotenv",
    "python-multipart": "multipart",
    "pyyaml": "yaml",
    "scikit-learn": "sklearn",
}
SETTINGS_FILE = "catalog.yaml"  # catalog-wide settings, inside catalog/
SETTINGS_KEYS = {"first_party"}


def distribution(requirement: str) -> str:
    """`PyJWT[crypto]>=2.8` -> `pyjwt` (pip's normalization: lowercase, `_`/`.` -> `-`)."""
    name = re.match(r"[A-Za-z0-9._-]+", requirement).group(0)
    return re.sub(r"[-_.]+", "-", name).lower()


def import_name(dist: str, overrides: Mapping[str, str] | None = None) -> str:
    """Top-level module a distribution is imported as."""
    dist = distribution(dist)
    norm = {distribution(k): v for k, v in (overrides or {}).items()}
    if dist in norm:
        return norm[dist].split(".")[0]
    return KNOWN_IMPORT_NAMES.get(dist, dist.replace("-", "_"))


def required_roots(requires: list[str], overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    """import root -> requirement, for every `requires` entry."""
    return {import_name(r, overrides): r for r in requires}


def imported_roots(source: str) -> dict[str, int]:
    """Top-level module -> first line, for every absolute import in `source` (anywhere)."""
    out: dict[str, int] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.setdefault(alias.name.split(".")[0], node.lineno)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            out.setdefault(node.module.split(".")[0], node.lineno)
    return dict(sorted(out.items(), key=lambda x: (x[1], x[0])))


def is_stdlib(root: str) -> bool:
    return root in sys.stdlib_module_names or root == "__future__"


def load_settings(root: Path) -> tuple[dict, list[str]]:
    """`catalog/catalog.yaml` (optional): ({"first_party": [...]}, errors)."""
    path = Path(root) / "catalog" / SETTINGS_FILE
    if not path.is_file():
        return {"first_party": []}, []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {"first_party": []}, [f"{SETTINGS_FILE} is not valid YAML: {exc}"]
    if not isinstance(data, dict):
        return {"first_party": []}, [f"{SETTINGS_FILE} must be a mapping"]
    errors = [f"{SETTINGS_FILE}: unknown key {k!r}" for k in sorted(set(data) - SETTINGS_KEYS)]
    first = data.get("first_party", [])
    if not isinstance(first, list) or not all(isinstance(x, str) and x.isidentifier() for x in first):
        errors.append(f"{SETTINGS_FILE}: first_party must be a list of top-level module names")
        first = []
    return {"first_party": sorted(first)}, errors


def check(source: str, requires: list[str], overrides: Mapping[str, str] | None,
          first_party: list[str]) -> list[str]:
    """Problems for validation check 12 (empty = consistent)."""
    problems = []
    imported = imported_roots(source)
    required = required_roots(requires, overrides)
    third = {r: ln for r, ln in imported.items() if not is_stdlib(r) and r not in first_party}
    for root, line in third.items():
        if root not in required:
            problems.append(f"imports third-party `{root}` (line {line}) but `requires` does not list it; "
                            f"add its distribution (and `import_names` if it is not imported as its "
                            f"name), or list `{root}` as first_party in catalog/{SETTINGS_FILE}")
    for root, req in sorted(required.items()):
        if root not in imported:
            problems.append(f"`requires` lists {req!r} (imported as `{root}`) but the impl never imports "
                            f"`{root}`" + ("; fix `import_names` if its import name differs"
                                           if root == distribution(req).replace("-", "_") else ""))
    for dist in sorted(overrides or {}):
        if distribution(dist) not in {distribution(r) for r in requires}:
            problems.append(f"`import_names` maps {dist!r}, which `requires` does not list")
    return problems
