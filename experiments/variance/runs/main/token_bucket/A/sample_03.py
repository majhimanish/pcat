import time


def check_rate_limit(buckets, key, capacity=10, refill_rate=1.0, cost=1, now=None):
    """Token bucket rate limiter backed by a dict.

    buckets: dict mapping key -> {"tokens": float, "last": float}
    key: identifier being rate limited (e.g. user id or IP)
    capacity: maximum tokens the bucket can hold (burst size)
    refill_rate: tokens added per second
    cost: tokens consumed by this request
    now: optional timestamp (seconds) for testing; defaults to time.monotonic()

    Returns (allowed, retry_after) where retry_after is the number of seconds
    to wait before the request could succeed (0.0 if allowed).
    """
    if now is None:
        now = time.monotonic()

    if cost > capacity:
        return False, float("inf")

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
        return True, 0.0

    if refill_rate <= 0:
        return False, float("inf")

    retry_after = (cost - bucket["tokens"]) / refill_rate
    return False, retry_after
