import pytest

from bucket_retry_after import check_rate_limit


def test_allowed_then_retry_after():
    buckets = {}
    assert check_rate_limit(buckets, "ip", capacity=2, refill_rate=0.5, now=0.0) == (True, 0.0)
    assert check_rate_limit(buckets, "ip", capacity=2, refill_rate=0.5, now=0.0) == (True, 0.0)
    assert check_rate_limit(buckets, "ip", capacity=2, refill_rate=0.5, now=0.0) == (False, 2.0)
    assert check_rate_limit(buckets, "ip", capacity=2, refill_rate=0.5, now=1.0) == (False, 1.0)
    assert check_rate_limit(buckets, "ip", capacity=2, refill_rate=0.5, now=2.0) == (True, 0.0)


def test_retry_after_is_accurate_for_larger_cost():
    buckets = {}
    check_rate_limit(buckets, "k", capacity=10, cost=10, now=0.0)
    allowed, wait = check_rate_limit(buckets, "k", capacity=10, refill_rate=2.0, cost=4, now=0.0)
    assert not allowed and wait == 2.0
    assert check_rate_limit(buckets, "k", capacity=10, refill_rate=2.0, cost=4, now=wait)[0]


def test_refill_capped_and_backwards_clock():
    buckets = {}
    check_rate_limit(buckets, "k", capacity=3, now=0.0)
    check_rate_limit(buckets, "k", capacity=3, now=500.0)
    assert buckets["k"]["tokens"] == 2.0
    check_rate_limit(buckets, "k", capacity=3, now=100.0)
    assert buckets["k"]["tokens"] == 1.0


@pytest.mark.parametrize("kw,msg", [({"capacity": 0}, "positive"), ({"refill_rate": -1}, "positive"),
                                     ({"cost": 0}, "positive"), ({"cost": 11}, "exceeds capacity")])
def test_rejects_bad_settings(kw, msg):
    with pytest.raises(ValueError, match=msg):
        check_rate_limit({}, "k", now=0.0, **kw)
