import time


def check_rate_limit(buckets, key, capacity=10, refill_rate=1.0, cost=1, now=None):
    """Token bucket rate limiter.

    buckets: dict mapping key -> {"tokens": float, "last": float}
    capacity: max tokens the bucket can hold
    refill_rate: tokens added per second
    cost: tokens consumed per request
    now: optional timestamp (defaults to time.monotonic())

    Returns (allowed, retry_after_seconds).
    """
    if now is None:
        now = time.monotonic()

    bucket = buckets.get(key)
    if bucket is None:
        bucket = {"tokens": float(capacity), "last": now}
        buckets[key] = bucket

    # Refill based on elapsed time, capped at capacity
    elapsed = max(0.0, now - bucket["last"])
    bucket["tokens"] = min(capacity, bucket["tokens"] + elapsed * refill_rate)
    bucket["last"] = now

    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True, 0.0

    if refill_rate <= 0 or cost > capacity:
        return False, float("inf")

    retry_after = (cost - bucket["tokens"]) / refill_rate
    return False, retry_after
