import pytest

from bucket_bool import allow_request


def test_burst_then_refill():
    buckets = {}
    assert [allow_request(buckets, "ip", capacity=3, now=0.0) for _ in range(4)] == [True, True, True, False]
    assert allow_request(buckets, "ip", capacity=3, refill_rate=2.0, now=0.5)  # +1 token
    assert not allow_request(buckets, "ip", capacity=3, refill_rate=2.0, now=0.5)


def test_refill_capped_at_capacity_and_keys_independent():
    buckets = {}
    allow_request(buckets, "a", capacity=2, now=0.0)
    allow_request(buckets, "a", capacity=2, now=1000.0)
    assert buckets["a"]["tokens"] == 1.0  # refilled to 2 (not 1001), then took 1
    assert allow_request(buckets, "b", capacity=2, now=0.0)


def test_cost_and_backwards_clock():
    buckets = {}
    assert allow_request(buckets, "k", capacity=5, cost=5, now=10.0)
    assert not allow_request(buckets, "k", capacity=5, now=9.0)  # clock went back: no refill
    assert buckets["k"]["tokens"] == 0.0


def test_default_clock_is_monotonic(monkeypatch):
    monkeypatch.setattr("bucket_bool.time.monotonic", lambda: 42.0)
    buckets = {}
    allow_request(buckets, "k")
    assert buckets["k"]["last"] == 42.0


@pytest.mark.parametrize("kw", [{"capacity": 0}, {"refill_rate": 0}, {"cost": 0}, {"cost": -1}])
def test_rejects_non_positive_settings(kw):
    with pytest.raises(ValueError):
        allow_request({}, "k", now=0.0, **kw)
