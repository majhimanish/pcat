"""Tests for validators.regex_match."""
import pytest

from impl import is_valid_username


@pytest.mark.parametrize("name", ["ab", "alice", "a.b_c", "x" * 20])
def test_valid(name):
    assert is_valid_username(name)


@pytest.mark.parametrize("name", ["a", "x" * 21, ".alice", "alice_", "a..b", "a_.b", "al ice", "alice!", ""])
def test_invalid(name):
    assert not is_valid_username(name)
