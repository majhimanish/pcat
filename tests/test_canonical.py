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
        ("X = make()\ndef f():\n    return X\n", "not a literal constant"),
        ("X = [1, Y]\ndef f():\n    return X\n", "not a literal constant"),
        ("A, B = 1, 2\ndef f():\n    return A\n", "only imports, function definitions"),
        ("X = 1\nX = 2\ndef f():\n    return X\n", "defined twice"),
        ("class A:\n    pass\n", "only imports, function definitions"),
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


# --------------------------------------------------------------------------- #
# v1.1: keyword arguments at calls to the pattern's own functions
# --------------------------------------------------------------------------- #


def run(text: str, entry: str, *args, **kwargs):
    namespace: dict = {}
    exec(compile(text, "<canonical>", "exec"), namespace)  # noqa: S102 - test only
    return namespace[entry](*args, **kwargs)


KW_HELPER = src(
    """
    def entry(xs, flip=False):
        return order(xs, reverse=flip, key=abs)

    def order(items, key=None, reverse=False):
        return sorted(items, key=key, reverse=reverse)
    """
)


def test_helper_keywords_use_callee_placeholders_and_canonical_text_runs():
    result = analyze(KW_HELPER)
    # callee `order`: items -> v0, key -> v1, reverse -> v2
    assert "return f1(v0, v2=v1, v1=abs)" in result.text
    assert "def f1(v0, v1=None, v2=False):" in result.text
    assert "sorted(v0, key=v1, reverse=v2)" in result.text  # external call untouched
    data = [3, -1, 2, -5]
    for flip in (False, True):
        assert run(result.text, "f0", data, flip) == run(KW_HELPER, "entry", data, flip)


def test_helper_defined_after_caller_and_before_give_same_result():
    before = src(
        """
        def order(items, key=None, reverse=False):
            return sorted(items, key=key, reverse=reverse)

        def entry(xs, flip=False):
            return order(xs, reverse=flip, key=abs)
        """
    )
    assert canonicalize(before, "entry") == canonicalize(KW_HELPER, "entry")
    assert "f1(v0, v2=v1, v1=abs)" in canonicalize(before, "entry")


def test_recursive_entry_point_with_keywords():
    code = src(
        """
        def count_down(n, acc=None):
            if acc is None:
                acc = []
            if n == 0:
                return acc
            acc.append(n)
            return count_down(n - 1, acc=acc)
        """
    )
    text = canonicalize(code)
    assert "return f0(v0 - 1, v1=v1)" in text
    assert run(text, "f0", 3) == [3, 2, 1] == run(code, "count_down", 3)


def test_unmatched_keyword_into_kwargs_is_left_alone():
    code = src(
        """
        def entry(x):
            return build(x, size=2, color="red")

        def build(x, size=1, **extra):
            return x, size, extra
        """
    )
    text = canonicalize(code)
    assert "f1(v0, v1=2, color='red')" in text
    assert run(text, "f0", 9) == (9, 2, {"color": "red"}) == run(code, "entry", 9)


def test_positional_only_name_passed_as_keyword_lands_in_kwargs_unchanged():
    code = "def entry():\n    return build(1, a=2)\n\ndef build(a, /, **kw):\n    return a, kw\n"
    text = canonicalize(code)
    assert "f1(1, a=2)" in text
    assert run(text, "f0") == (1, {"a": 2})


def test_keyword_only_parameters_are_renamed_at_call_sites():
    code = "def entry(x):\n    return helper(x, scale=3)\n\ndef helper(x, *, scale):\n    return x * scale\n"
    text = canonicalize(code)
    assert "f1(v0, v1=3)" in text and "def f1(v0, *, v1):" in text
    assert run(text, "f0", 2) == 6


def test_external_and_shadowed_calls_keep_keyword_names():
    code = src(
        """
        import json
        from functools import reduce

        def entry(obj, items, order):
            a = sorted(items, reverse=True)
            b = obj.method(key=1)
            c = json.dumps(items, indent=2)
            d = reduce(lambda x, y: x + y, items, initial=0)
            e = order(reverse=True)  # parameter shadows the top-level function
            return a, b, c, d, e

        def order(reverse=False):
            return reverse
        """
    )
    text = canonicalize(code, "entry")
    for kept in ("reverse=True)", "key=1", "indent=2", "initial=0", "v2(reverse=True)"):
        assert kept in text, kept


def test_render_maps_keywords_through_callee_names():
    result = analyze(KW_HELPER)
    out = render(result.text, {**result.name_map, "f1.v2": "descending", "f1.v1": "by"})
    assert "return order(xs, descending=flip, by=abs)" in out
    assert "def order(items, by=None, descending=False):" in out
    assert run(out, "entry", [3, -1, 2], True) == [3, 2, -1]
    assert canonicalize(render(result.text, result.name_map), "entry") == result.text


# --------------------------------------------------------------------------- #
# v1.1: module-level literal constants
# --------------------------------------------------------------------------- #

CONSTS = src(
    """
    import re

    SEPARATOR = "-"

    def _clean(word):
        return re.sub(PATTERN_TEXT, "", word)

    PATTERN_TEXT: str = r"[^a-z]"
    LIMITS = (1, 10)

    def join_words(words, limit=LIMITS[1]):
        return SEPARATOR.join(_clean(w) for w in words[:limit])
    """
)


def test_constants_renamed_in_source_order_and_placed_before_functions():
    # `limit=LIMITS[1]` is evaluated at def time; constants come before all
    # functions so the canonical (and rendered) text stays runnable.
    result = analyze(CONSTS, "join_words")
    assert result.text == src(
        """
        import re
        c0 = '-'
        c1: str = '[^a-z]'
        c2 = (1, 10)

        def f0(v0, v1=c2[1]):
            return c0.join((f1(v2) for v2 in v0[:v1]))

        def f1(v0):
            return re.sub(c1, '', v0)
        """
    )
    assert {k: v for k, v in result.name_map.items() if k.startswith("c")} == {
        "c0": "SEPARATOR",
        "c1": "PATTERN_TEXT",
        "c2": "LIMITS",
    }
    assert run(result.text, "f0", ["ab1", "c!d"]) == run(CONSTS, "join_words", ["ab1", "c!d"])


def test_constants_round_trip_and_are_idempotent():
    result = analyze(CONSTS, "join_words")
    rendered = render(result.text, result.name_map)
    assert "SEPARATOR = '-'" in rendered and "PATTERN_TEXT: str" in rendered
    assert canonicalize(rendered, "join_words") == result.text
    assert canonicalize(result.text, "f0") == result.text
    custom = render(result.text, {"c0": "SEP"})
    assert "SEP = '-'" in custom and "SEP.join" in custom


def test_constant_annotations_stripped_on_request():
    text = canonicalize("LIMIT: int = 3\ndef f():\n    return LIMIT\n", keep_annotations=False)
    assert text == "c0 = 3\n\ndef f0():\n    return c0\n"


def test_global_declaration_and_local_shadowing_of_constants():
    code = src(
        """
        COUNT = 0

        def bump():
            global COUNT
            COUNT += 1
            return COUNT

        def shadow():
            COUNT = 5
            return COUNT
        """
    )
    text = canonicalize(code, "bump")
    assert "global c0" in text and "c0 += 1" in text
    assert "def f1():\n    v0 = 5\n    return v0" in text


@pytest.mark.parametrize(
    "literal",
    ["1", "-2.5", "'s'", "b'x'", "True", "None", "(1, 'a')", "[1, [2]]", "{'k': (1,)}", "{1, 2}"],
)
def test_accepted_literals(literal):
    assert canonicalize(f"X = {literal}\ndef f():\n    return X\n").startswith("c0 = ")


def test_free_name_c0_collides_with_placeholders():
    with pytest.raises(CanonicalizationError, match="placeholder namespace"):
        canonicalize("def f():\n    return c0\n")


def test_extract_copies_used_constants_transitively():
    code = src(
        """
        UNUSED = 5
        GREETING = "hello"  # trailing comment
        PUNCT = ".,!?"

        def _clean(word):
            return word.strip(PUNCT)

        def greet(name):
            return f"{GREETING}, {_clean(name)}"
        """
    )
    out = extract_function(code, "greet")
    assert "GREETING = \"hello\"" in out and 'PUNCT = ".,!?"' in out
    assert "UNUSED" not in out
    assert out.index("GREETING") < out.index("PUNCT") < out.index("def _clean")
    assert run(out, "greet", "bob!") == "hello, bob"


@pytest.mark.parametrize(
    "definition,name",
    [
        ("PATTERN = re.compile('x')", "PATTERN"),
        ("class Helper:\n    pass", "Helper"),
        ("for LOOPVAR in range(3):\n    pass", "LOOPVAR"),
        ("TOTAL = 1\nTOTAL += 1", "TOTAL"),
    ],
)
def test_extract_fails_clearly_on_non_literal_module_names(definition, name):
    code = f"import re\n{definition}\n\ndef f():\n    return {name}\n"
    with pytest.raises(CanonicalizationError, match=f"module-level name '{name}'"):
        extract_function(code, "f")


def test_extract_ignores_locals_that_shadow_module_names():
    code = src(
        """
        def helper():
            return 1

        CONFIG = object()

        def f(helper, CONFIG):
            return helper(CONFIG)
        """
    )
    assert list_functions(extract_function(code, "f")) == ["f"]
