import time


def allow_request(state, key, capacity, refill_rate, cost=1, now=None):
    """
    Token bucket rate limit check.

    state:       dict holding bucket state, keyed by `key`
    key:         identifier for the client/resource being limited
    capacity:    maximum number of tokens the bucket can hold
    refill_rate: tokens added per second
    cost:        tokens consumed by this request
    now:         optional timestamp (seconds); defaults to time.monotonic()

    Returns True if the request is allowed, False otherwise.
    """
    if now is None:
        now = time.monotonic()

    bucket = state.get(key)
    if bucket is None:
        # New clients start with a full bucket
        bucket = {"tokens": float(capacity), "last_refill": now}
        state[key] = bucket

    # Refill based on elapsed time
    elapsed = max(0.0, now - bucket["last_refill"])
    bucket["tokens"] = min(float(capacity), bucket["tokens"] + elapsed * refill_rate)
    bucket["last_refill"] = now

    # Consume tokens if available
    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True
    return False
