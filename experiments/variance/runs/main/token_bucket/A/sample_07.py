import time


def check_rate_limit(buckets, key, capacity=10, refill_rate=1.0, cost=1, now=None):
    """
    Token bucket rate limiter backed by a plain dict.

    buckets:     dict mapping key -> {"tokens": float, "last": float}
    key:         identifier being limited (e.g. user ID or IP)
    capacity:    maximum tokens the bucket can hold (burst size)
    refill_rate: tokens added per second
    cost:        tokens required for this request
    now:         optional timestamp (seconds); defaults to time.monotonic()

    Returns True if the request is allowed, False if rate limited.
    """
    if now is None:
        now = time.monotonic()

    bucket = buckets.get(key)
    if bucket is None:
        bucket = {"tokens": float(capacity), "last": now}
        buckets[key] = bucket

    # Refill based on elapsed time, capped at capacity.
    elapsed = max(0.0, now - bucket["last"])
    bucket["tokens"] = min(capacity, bucket["tokens"] + elapsed * refill_rate)
    bucket["last"] = now

    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True
    return False
