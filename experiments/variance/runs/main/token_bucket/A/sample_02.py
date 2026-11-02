import time


def check_rate_limit(buckets, key, capacity=10, refill_rate=1.0, cost=1, now=None):
    """Token bucket rate limiter backed by a dict.

    buckets:     dict mapping key -> {"tokens": float, "last": float}
    key:         identifier being limited (e.g. user id or IP)
    capacity:    maximum number of tokens the bucket can hold
    refill_rate: tokens added per second
    cost:        tokens required for this request
    now:         optional timestamp (seconds); defaults to time.monotonic()

    Returns True if the request is allowed, False if it is rate limited.
    """
    if now is None:
        now = time.monotonic()

    bucket = buckets.get(key)
    if bucket is None:
        bucket = {"tokens": float(capacity), "last": now}
        buckets[key] = bucket
    else:
        elapsed = max(0.0, now - bucket["last"])
        bucket["tokens"] = min(float(capacity), bucket["tokens"] + elapsed * refill_rate)
        bucket["last"] = now

    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True
    return False
