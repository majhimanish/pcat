import time


def allow_request(buckets, key, capacity=10, refill_rate=1.0, cost=1, now=None):
    """Token bucket rate limiter.

    buckets:     plain dict mapping key -> {"tokens": float, "last": float}
    key:         identifier for the client/resource being limited
    capacity:    maximum number of tokens the bucket can hold
    refill_rate: tokens added per second
    cost:        tokens consumed by this request
    now:         optional timestamp (seconds); defaults to time.monotonic()

    Returns True if the request is allowed, False otherwise.
    """
    if now is None:
        now = time.monotonic()

    bucket = buckets.get(key)
    if bucket is None:
        bucket = {"tokens": float(capacity), "last": now}
        buckets[key] = bucket

    # Refill based on elapsed time, capped at capacity.
    elapsed = max(0.0, now - bucket["last"])
    bucket["tokens"] = min(float(capacity), bucket["tokens"] + elapsed * refill_rate)
    bucket["last"] = now

    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True
    return False
