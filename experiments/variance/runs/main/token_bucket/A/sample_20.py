import time


def check_rate_limit(buckets, key, capacity=10, refill_rate=1.0, cost=1, now=None):
    """
    Token bucket rate limiter backed by a plain dict.

    buckets:     dict mapping key -> {"tokens": float, "last": float}
    key:         identifier being rate limited (user id, IP, etc.)
    capacity:    maximum number of tokens the bucket can hold
    refill_rate: tokens added per second
    cost:        tokens required for this request
    now:         optional timestamp (defaults to time.monotonic())

    Returns (allowed, retry_after_seconds). retry_after is 0.0 when allowed.
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

    if cost > capacity:
        return False, float("inf")

    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True, 0.0

    if refill_rate <= 0:
        return False, float("inf")

    retry_after = (cost - bucket["tokens"]) / refill_rate
    return False, retry_after
