"""v5.1 Part C: `requires` vs imports — validation check 12, `import_names`, PC103 mapping."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from conftest import edit_yaml, pattern_dir
from pcat import catalog as cat
from pcat import codeunit, deviation, requirements
from pcat.schema import PatternMeta

HTTP = "http.get_with_retry.requests"


def check12(root) -> list[str]:
    return [p.message for p in cat.validate(root, run_tests=False) if p.check == "12"]


def test_real_catalog_passes_check_12(root):
    assert check12(root) == []


def test_missing_requires_is_reported(root):
    edit_yaml(pattern_dir(root, HTTP), requires=[])
    [msg] = check12(root)
    assert "imports third-party `requests`" in msg


def test_unused_requires_is_reported(root):
    edit_yaml(pattern_dir(root, HTTP), requires=["requests>=2.31,<3", "orjson>=3"])
    [msg] = check12(root)
    assert "'orjson>=3'" in msg and "never imports `orjson`" in msg


def test_import_names_maps_a_distribution_to_its_module(root):
    edit_yaml(pattern_dir(root, HTTP), requires=["requests-fork>=1"])
    assert len(check12(root)) == 2  # requests not covered; requests_fork never imported
    edit_yaml(pattern_dir(root, HTTP), requires=["requests-fork>=1"], import_names={"requests-fork": "requests"})
    assert check12(root) == []
    edit_yaml(pattern_dir(root, HTTP), requires=["requests>=2.31,<3"], import_names={"other": "x"})
    assert check12(root) == ["`import_names` maps 'other', which `requires` does not list"]


def test_built_in_table_and_normalization():
    assert requirements.import_name("PyJWT[crypto]>=2.8") == "jwt"
    assert requirements.import_name("python_dateutil") == "dateutil"
    assert requirements.import_name("email-validator>=2") == "email_validator"
    assert requirements.import_name("pyjwt", {"PyJWT": "jwt2.core"}) == "jwt2"


def test_stdlib_modules_are_exempt():
    source = "from __future__ import annotations\nimport json, os.path\nfrom collections import deque\n"
    assert requirements.check(source, [], None, []) == []
    assert requirements.check("import yaml\n", ["pyyaml>=6"], None, []) == []
    assert requirements.check("from . import x\n", [], None, []) == []  # relative: the package itself


def test_first_party_from_catalog_settings(root):
    edit_yaml(pattern_dir(root, HTTP), requires=[])
    (root / "catalog" / "catalog.yaml").write_text("first_party: [requests]\n")
    assert check12(root) == []
    (root / "catalog" / "catalog.yaml").write_text("first_party: [requests]\nother: 1\n")
    assert check12(root) == ["catalog.yaml: unknown key 'other'"]
    (root / "catalog" / "catalog.yaml").write_text("first_party: requests\n")
    assert any("must be a list" in m for m in check12(root))


def test_import_names_schema_rejects_non_modules():
    base = dict(id="a.b", version=1, title="t", summary="s", category="a", behavior={}, entry_point="f",
                owner="o", status="active")
    assert PatternMeta(**base, import_names={"pyjwt": "jwt"}).import_names == {"pyjwt": "jwt"}
    with pytest.raises(ValidationError):
        PatternMeta(**base, import_names={"pyjwt": "not a module"})


# --------------------------------------------------------------------------- #
# PC103 through the mapping
# --------------------------------------------------------------------------- #

PATTERN = "import fb\n\n\ndef f(x):\n    return fb.load(x)\n"


def pc103(user: str, requires: list[str], import_names: dict | None = None, pattern: str = PATTERN):
    meta = SimpleNamespace(entry_point="f", exports=[], requires=requires, import_names=import_names or {},
                           guards=[])
    a = deviation.analyze(codeunit.build_unit_from_source(pattern, "f"), codeunit.build_unit_from_source(user, "f"),
                          pattern_key="x.y@v1", pattern_function="f", meta=meta)
    return [(d.severity, d.message) for d in a.deviations if d.code == "PC103"]


def test_pc103_uses_import_names():
    swapped = "import other\n\n\ndef f(x):\n    return other.load(x)\n"
    assert pc103(PATTERN, ["foo-bar>=1"], {"foo-bar": "fb"}) == []
    [(severity, msg)] = pc103(swapped, ["foo-bar>=1"], {"foo-bar": "fb"})
    assert severity == "high" and "no longer uses `fb`" in msg and "`other` instead" in msg
    [(severity, _)] = pc103(swapped, ["foo-bar>=1"])  # without the mapping fb is not a required library
    assert severity == "medium"


def test_pc103_ignores_a_required_library_the_pattern_only_uses_in_annotations():
    pattern = "from fastapi import Request\n\n\ndef f(request: Request):\n    return request.url\n"
    user = "def f(request):\n    return request.url\n"
    assert pc103(user, ["fastapi>=0.115"], pattern=pattern) == []


def test_pc103_dropping_a_not_required_package_is_low_and_says_so():
    pattern = "import fb\nimport json\n\n\ndef f(x):\n    return fb.load(json.dumps(x))\n"
    user = "import json\n\n\ndef f(x):\n    return json.dumps(x)\n"
    [(severity, msg)] = pc103(user, [], pattern=pattern)
    assert severity == "low" and "no longer uses `fb` (not in the pattern's `requires`)" in msg
