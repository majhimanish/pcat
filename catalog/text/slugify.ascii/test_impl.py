import pytest

from impl import slugify


@pytest.mark.parametrize(
    "text,slug",
    [
        ("Hello World", "hello-world"),
        ("  Hello,   World!  ", "hello-world"),
        ("Already-a-slug", "already-a-slug"),
        ("snake_case_name", "snake-case-name"),
        ("Crème Brûlée", "creme-brulee"),
        ("Ünïcödé Straße", "unicode-strae"),
        ("version 2.0 release", "version-2-0-release"),
        ("---leading and trailing---", "leading-and-trailing"),
        ("MiXeD CaSe 123", "mixed-case-123"),
    ],
)
def test_slugs(text, slug):
    assert slugify(text) == slug


def test_empty_input():
    assert slugify("") == ""


def test_only_symbols_or_non_ascii():
    assert slugify("!!! ??? ***") == ""
    assert slugify("日本語") == ""


def test_custom_separator():
    assert slugify("Hello World Again", separator="_") == "hello_world_again"
    assert slugify("Hello World", separator="") == "helloworld"


def test_result_is_stable_under_reslugify():
    once = slugify("Some Title: Part 2")
    assert slugify(once) == once
