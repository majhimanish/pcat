"""Shape canonicalization (literal values blanked)."""

from __future__ import annotations

import textwrap

import pytest

from pcat import canonical
from pcat.shape import SHAPE_VERSION, shape_canonicalize, shape_fingerprint


def src(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


A = src(
    '''
    def total_price(items):
        """Doc."""
        total = 0
        for item in items:  # comment
            if item.price > 100:
                total += item.price * 2
        return total
    '''
)
B = src(
    """
    def other(rows):
        acc = 0
        for r in rows:
            if r.price > 50:
                acc += r.price * 3.5
        return acc
    """
)


def test_names_comments_and_literals_give_same_shape_but_different_exact():
    assert shape_fingerprint(A) == shape_fingerprint(B)
    assert canonical.analyze(A).fingerprint != canonical.analyze(B).fingerprint
    assert "if v2.price > 0:" in shape_canonicalize(A)


@pytest.mark.parametrize("old,new", [("False", "True"), ("False", "None"), ("None", "...")])
def test_true_false_none_ellipsis_are_kept(old, new):
    code = f"def f(x):\n    if x is {old}:\n        return [x, x, x]\n    return {old}\n"
    assert shape_fingerprint(code) != shape_fingerprint(code.replace(old, new))


def test_strings_bytes_and_numbers_blanked():
    code = "def f(x):\n    return (x + 1, x * 2.5, 3j, 'abc', b'xyz', -7)\n"
    assert shape_canonicalize(code) == "def f0(v0):\n    return (v0 + 0, v0 * 0, 0, '', b'', -0)\n"


def test_fstring_structure_kept_literal_parts_blanked():
    code = 'def f(name, n):\n    return f"Hello {name!r:>10} you have {n:.2f} items"\n'
    other = 'def g(a, b):\n    return f"Bye {a!r:<3}! {b:d}"\n'
    assert shape_canonicalize(code) == "def f0(v0, v1):\n    return f'{v0!r:}{v1:}'\n"
    assert shape_fingerprint(code) == shape_fingerprint(other)
    assert shape_fingerprint(code) != shape_fingerprint('def f(a, b):\n    return f"{a} {b}"\n')


def test_constants_keep_names_values_blanked():
    code = "LIMIT = 10\nNAMES = ('a', 'b')\n\ndef f(x):\n    return x[:LIMIT], NAMES\n"
    text = shape_canonicalize(code)
    assert text.startswith("c0 = 0\nc1 = ('', '')\n")
    assert "return (v0[:c0], c1)" in text


def test_shape_version():
    assert SHAPE_VERSION == 1
