"""Tests for canonicalization, fingerprints, name maps and rendering."""

from __future__ import annotations

import textwrap

import pytest

from pcat.canonical import (
    analyze,
    canonicalize,
    extract_function,
    extract_name_map,
    fingerprint,
    list_functions,
    render,
)
from pcat.errors import CanonicalizationError, RenderError


def src(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


BASE = src(
    '''
    def find(items, target):
        lo, hi = 0, len(items) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if items[mid] == target:
                return mid
            if items[mid] < target:
                lo = mid + 1
            else:
                hi = mid - 1
        return -1
    '''
)

RENAMED = src(
    '''
    """Module docstring that must vanish."""


    def locate(seq,   needle):
        """Function docstring that must vanish."""
        # a comment
        low, high = 0, len(seq) - 1   # trailing comment
        while low <= high:
            m = (low + high) // 2
            if seq[m] == needle: return m
            if seq[m] < needle:
                low = m + 1
            else:
                high = (
                    m - 1
                )
        return -1
    '''
)


def test_names_comments_docstrings_formatting_do_not_change_fingerprint():
    a = analyze(BASE)
    b = analyze(RENAMED)
    assert a.text == b.text
    assert a.fingerprint == b.fingerprint


@pytest.mark.parametrize(
    "old,new",
    [
        ("len(items)", "abs(items)"),  # builtin
        ("return -1", "return -2"),  # literal
        ("(lo + hi) // 2", "(lo + hi) // 3"),  # literal
    ],
)
def test_builtin_or_literal_change_changes_fingerprint(old, new):
    assert old in BASE
    assert analyze(BASE).fingerprint != analyze(BASE.replace(old, new)).fingerprint


def test_attribute_change_changes_fingerprint():
    a = "def f(xs, x):\n    xs.append(x)\n"
    b = "def f(xs, x):\n    xs.extend(x)\n"
    assert analyze(a).fingerprint != analyze(b).fingerprint


def test_keyword_argument_names_are_not_renamed():
    out = canonicalize("def f(xs):\n    return sorted(xs, reverse=True)\n")
    assert "reverse=True" in out


def test_fingerprint_is_sha256_of_canonical_text():
    result = analyze(BASE)
    assert result.fingerprint == fingerprint(result.text)
    assert len(result.fingerprint) == 64


def test_canonical_text_has_single_trailing_newline():
    out = canonicalize(BASE + "\n\n\n")
    assert out.endswith("\n") and not out.endswith("\n\n")


def test_scoping_restarts_per_function_and_helpers_numbered_in_source_order():
    code = src(
        """
        def alpha(a, b):
            return a + b

        def entry(x):
            return alpha(x, 1) + beta(x)

        def beta(c):
            d = c * 2
            return d
        """
    )
    result = analyze(code, entry_point="entry")
    text = result.text
    # entry point first, helpers in source order
    assert text.index("def f0(") < text.index("def f1(") < text.index("def f2(")
    assert "def f0(v0):" in text
    assert "def f1(v0, v1):" in text  # alpha
    assert "def f2(v0):" in text  # beta
    assert "v1 = v0 * 2" in text
    assert result.name_map == {
        "f0": "entry",
        "v0": "x",
        "f1": "alpha",
        "f1.v0": "a",
        "f1.v1": "b",
        "f2": "beta",
        "f2.v0": "c",
        "f2.v1": "d",
    }


def test_function_order_does_not_matter_when_entry_point_given():
    a = "def h(x):\n    return x\n\ndef e(y):\n    return h(y)\n"
    b = "def e(y):\n    return h(y)\n\ndef h(x):\n    return x\n"
    assert canonicalize(a, "e") == canonicalize(b, "e")


def test_default_entry_point_is_first_function():
    code = "def a():\n    return b()\n\ndef b():\n    return 1\n"
    assert extract_name_map(code)["f0"] == "a"


def test_loop_comprehension_except_and_walrus_names_are_renamed():
    code = src(
        """
        def f(data):
            out = [y for y in data if (z := y)]
            for k in out:
                try:
                    pass
                except ValueError as err:
                    raise err
            return z, k
        """
    )
    text = canonicalize(code)
    for name in ("data", "out", "y", "z", "k", "err"):
        assert f" {name}" not in text and f"({name}" not in text, name
    assert "ValueError" in text


def test_never_renamed_names():
    code = src(
        """
        import math
        from os import path as p

        def f(self, cls, value):
            print(__name__, math.pi, p.join("a"), GLOBAL_THING, len(value))
            return self, cls
        """
    )
    text = canonicalize(code)
    for kept in ("self", "cls", "__name__", "math.pi", "p.join", "GLOBAL_THING", "len(", "print("):
        assert kept in text, kept
    assert "value" not in text


def test_global_declared_names_are_not_renamed():
    code = "def f():\n    global counter\n    counter = 1\n    x = counter\n    return x\n"
    text = canonicalize(code)
    assert "global counter" in text and "counter = 1" in text and "v0 = counter" in text


def test_nonlocal_names_follow_the_enclosing_local():
    code = src(
        """
        def outer():
            count = 0
            def bump():
                nonlocal count
                count += 1
            bump()
            return count
        """
    )
    text = canonicalize(code)
    assert "nonlocal v0" in text and "def v1():" in text


def test_imports_sorted_split_and_deduplicated():
    code = src(
        """
        import sys, os
        from __future__ import annotations
        import os
        from typing import Any, Optional

        def f(x: Any) -> Optional[int]:
            return os.sep, sys.argv
        """
    )
    text = canonicalize(code)
    head = text.split("\n\ndef")[0].splitlines()
    assert head == [
        "from __future__ import annotations",
        "from typing import Any",
        "from typing import Optional",
        "import os",
        "import sys",
    ]


def test_annotations_kept_by_default_and_stripped_on_request():
    code = "def f(x: int, *a: str, k: float = 1.0) -> int:\n    y: int = x\n    z: int\n    return y\n"
    kept = canonicalize(code)
    stripped = canonicalize(code, keep_annotations=False)
    assert "v0: int" in kept and "-> int" in kept
    assert ":" not in stripped.split("\n")[0][:-1]
    assert "v3 = v0" in stripped and "int" not in stripped


def test_stripping_annotations_keeps_bodies_valid():
    code = "def f():\n    if True:\n        x: int\n    return 1\n"
    text = canonicalize(code, keep_annotations=False)
    assert "pass" in text
    canonicalize(text)  # still parses


def test_docstring_only_function_gets_pass():
    assert canonicalize('def f():\n    """only a docstring"""\n') == "def f0():\n    pass\n"


def test_canonicalize_is_idempotent_on_its_output():
    text = canonicalize(RENAMED)
    assert canonicalize(text) == text


@pytest.mark.parametrize(
    "code,message",
    [
        ("def f(:\n", "syntax error"),
        ("X = 1\ndef f():\n    return X\n", "only imports and function definitions"),
        ("class A:\n    pass\n", "only imports and function definitions"),
        ("import os\n", "no top-level function"),
        ("def f():\n    class A:\n        pass\n", "class definitions inside functions"),
        ("def f():\n    return v0\n", "placeholder namespace"),
        ("from m import f1\ndef f():\n    return f1\n", "placeholder namespace"),
        ("def f():\n    pass\ndef f():\n    pass\n", "defined twice"),
    ],
)
def test_rejections(code, message):
    with pytest.raises(CanonicalizationError, match=message):
        canonicalize(code)


def test_unknown_entry_point_rejected():
    with pytest.raises(CanonicalizationError, match="entry point"):
        canonicalize(BASE, entry_point="nope")


def test_list_functions():
    assert list_functions("import os\ndef a():\n    pass\ndef b():\n    pass\n") == ["a", "b"]


def test_render_round_trip_and_custom_names():
    result = analyze(RENAMED)
    rendered = render(result.text, result.name_map)
    assert "def locate(seq, needle):" in rendered
    assert canonicalize(rendered, "locate") == result.text

    custom = render(result.text, {"f0": "find_user", "v0": "users", "f0.v1": "wanted"})
    assert "def find_user(users, wanted):" in custom
    assert "v2" in custom  # unmapped placeholders stay


def test_render_uses_scoped_keys_for_helpers():
    code = "def e(a):\n    return h(a)\n\ndef h(a):\n    b = a\n    return b\n"
    result = analyze(code)
    out = render(result.text, {"f0": "entry", "v0": "first", "f1": "helper", "f1.v0": "x"})
    assert "def entry(first):\n    return helper(first)" in out
    assert "def helper(x):\n    v1 = x\n    return v1" in out


@pytest.mark.parametrize(
    "names,message",
    [
        ({"f9": "x"}, "no such function"),
        ({"v99": "x"}, "unknown placeholder"),
        ({"f0.v99": "x"}, "unknown placeholder"),
        ({"bogus": "x"}, "invalid name-map key"),
        ({"f0": "not valid"}, "not a valid Python identifier"),
        ({"f0": "class"}, "not a valid Python identifier"),
    ],
)
def test_render_rejects_bad_name_maps(names, message):
    text = canonicalize(BASE)
    with pytest.raises(RenderError, match=message):
        render(text, names)


def test_extract_function_with_transitive_helpers_and_used_imports():
    code = src(
        """
        import os
        import sys
        from typing import Any

        CONSTANT = 3

        def unrelated():
            return sys.argv

        def leaf(x):
            return os.path.basename(x)

        def middle(x):
            # keep this comment
            return leaf(x)

        def top(x: Any):
            return middle(x)
        """
    )
    out = extract_function(code, "top")
    assert "import os" in out and "from typing import Any" in out
    assert "import sys" not in out and "unrelated" not in out and "CONSTANT" not in out
    assert "# keep this comment" in out
    assert list_functions(out) == ["leaf", "middle", "top"]


def test_extract_function_unknown_name():
    with pytest.raises(CanonicalizationError, match="no top-level function"):
        extract_function(BASE, "missing")


def test_match_and_async_constructs_are_renamed_in_reading_order():
    code = src(
        """
        async def f(cmd, **opts):
            match cmd:
                case {"go": where, **rest}:
                    return where, rest
                case [first, *others]:
                    return first, others
            async with opts["x"] as ctx:
                async for item in ctx:
                    await item
        """
    )
    result = analyze(code)
    assert "case {'go': v2, **v3}:" in result.text
    assert "case [v4, *v5]:" in result.text
    assert "async for v7 in v6:" in result.text
    assert canonicalize(render(result.text, result.name_map)) == result.text
