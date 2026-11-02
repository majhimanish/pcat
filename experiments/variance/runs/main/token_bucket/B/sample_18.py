import time

DEFAULT_CAPACITY = 10
DEFAULT_REFILL_RATE = 1.0  # tokens per second


def allow_request(buckets, key, capacity=DEFAULT_CAPACITY,
                  refill_rate=DEFAULT_REFILL_RATE, cost=1, now=None):
    """Token-bucket rate limiter, one bucket per key stored in `buckets` dict.

    Each bucket is a dict: {"tokens": float, "last": float}.
    Returns True if the request is allowed, False if it is rate limited.
    """
    if now is None:
        now = time.monotonic()

    bucket = buckets.get(key)
    if bucket is None:
        # New keys start with a full bucket.
        bucket = {"tokens": float(capacity), "last": now}
        buckets[key] = bucket
    else:
        # Refill based on elapsed time, capped at capacity.
        elapsed = max(0.0, now - bucket["last"])
        bucket["tokens"] = min(capacity, bucket["tokens"] + elapsed * refill_rate)
        bucket["last"] = now

    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True
    return False
