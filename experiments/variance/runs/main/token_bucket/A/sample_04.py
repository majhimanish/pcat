import time


def check_rate_limit(buckets, key, capacity=10, refill_rate=1.0, cost=1, now=None):
    """
    Token bucket rate limiter backed by a plain dict.

    buckets:     dict mapping key -> {"tokens": float, "last": float}
    key:         identifier being limited (user id, IP, API key, ...)
    capacity:    maximum number of tokens the bucket can hold (burst size)
    refill_rate: tokens added per second
    cost:        tokens required for this request
    now:         optional timestamp (seconds); defaults to time.monotonic()

    Returns (allowed, retry_after):
        allowed:     True if the request may proceed (tokens were consumed)
        retry_after: seconds until enough tokens are available (0.0 if allowed)
    """
    if now is None:
        now = time.monotonic()

    if cost > capacity:
        return False, float("inf")

    bucket = buckets.get(key)
    if bucket is None:
        bucket = {"tokens": float(capacity), "last": now}
        buckets[key] = bucket

    # Refill based on elapsed time, clamped to capacity.
    elapsed = max(0.0, now - bucket["last"])
    bucket["tokens"] = min(capacity, bucket["tokens"] + elapsed * refill_rate)
    bucket["last"] = now

    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True, 0.0

    if refill_rate <= 0:
        return False, float("inf")

    deficit = cost - bucket["tokens"]
    return False, deficit / refill_rate
