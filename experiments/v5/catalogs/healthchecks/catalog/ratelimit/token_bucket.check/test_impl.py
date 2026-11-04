import pytest

import impl
from impl import check_rate_limit


# Normal cases ---------------------------------------------------------------
def test_burst_up_to_capacity_then_retry_after():
    buckets = {}
    results = [check_rate_limit(buckets, "ip", capacity=3, refill_rate=1.0, now=0.0) for _ in range(4)]
    assert results == [(True, 0.0)] * 3 + [(False, 1.0)]


def test_refill_over_time_and_accurate_wait():
    buckets = {}
    for _ in range(2):
        check_rate_limit(buckets, "k", capacity=2, refill_rate=0.5, now=0.0)
    assert check_rate_limit(buckets, "k", capacity=2, refill_rate=0.5, now=0.0) == (False, 2.0)
    assert check_rate_limit(buckets, "k", capacity=2, refill_rate=0.5, now=1.0) == (False, 1.0)
    assert check_rate_limit(buckets, "k", capacity=2, refill_rate=0.5, now=2.0) == (True, 0.0)


def test_waiting_retry_after_is_enough():
    buckets = {}
    check_rate_limit(buckets, "k", capacity=10, cost=10, now=0.0)
    allowed, wait = check_rate_limit(buckets, "k", capacity=10, refill_rate=4.0, cost=6, now=0.0)
    assert not allowed and wait == 1.5
    assert check_rate_limit(buckets, "k", capacity=10, refill_rate=4.0, cost=6, now=wait)[0]


def test_keys_are_independent_and_state_shape():
    buckets = {}
    check_rate_limit(buckets, "a", capacity=1, now=5.0)
    assert check_rate_limit(buckets, "a", capacity=1, now=5.0)[0] is False
    assert check_rate_limit(buckets, "b", capacity=1, now=5.0) == (True, 0.0)
    assert buckets == {"a": {"tokens": 0.0, "last": 5.0}, "b": {"tokens": 0.0, "last": 5.0}}


# Edge cases -----------------------------------------------------------------------
def test_refill_capped_at_capacity_after_long_idle():
    buckets = {}
    check_rate_limit(buckets, "k", capacity=3, now=0.0)
    check_rate_limit(buckets, "k", capacity=3, now=1_000_000.0)
    assert buckets["k"]["tokens"] == 2.0


def test_clock_going_backwards_adds_no_tokens():
    buckets = {}
    check_rate_limit(buckets, "k", capacity=1, now=100.0)
    assert check_rate_limit(buckets, "k", capacity=1, now=50.0) == (False, 1.0)


def test_fractional_costs_and_rates():
    buckets = {}
    assert check_rate_limit(buckets, "k", capacity=1.0, refill_rate=0.25, cost=0.5, now=0.0) == (True, 0.0)
    assert check_rate_limit(buckets, "k", capacity=1.0, refill_rate=0.25, cost=0.75, now=0.0) == (False, 1.0)


def test_default_clock_is_monotonic(monkeypatch):
    monkeypatch.setattr(impl.time, "monotonic", lambda: 123.0)
    buckets = {}
    check_rate_limit(buckets, "k")
    assert buckets["k"]["last"] == 123.0


# Failure cases ------------------------------------------------------------------------
@pytest.mark.parametrize("kw,message", [
    ({"capacity": 0}, "positive"), ({"capacity": -1}, "positive"), ({"refill_rate": 0}, "positive"),
    ({"cost": 0}, "positive"), ({"cost": -2}, "positive"), ({"cost": 10.5}, "exceeds capacity")])
def test_rejects_bad_settings(kw, message):
    with pytest.raises(ValueError, match=message):
        check_rate_limit({}, "k", now=0.0, **kw)


def test_rejected_settings_do_not_create_state():
    buckets = {}
    with pytest.raises(ValueError):
        check_rate_limit(buckets, "k", cost=99, now=0.0)
    assert buckets == {}
