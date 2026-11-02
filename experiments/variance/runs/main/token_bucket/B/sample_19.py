import time

def allow_request(buckets, client_id, capacity=10, refill_rate=1.0, cost=1, now=None):
    """
    Token-bucket rate limiter.

    buckets:     dict mapping client_id -> {"tokens": float, "last": float}
    client_id:   identifier for the client making the request
    capacity:    maximum tokens a bucket can hold (burst size)
    refill_rate: tokens added per second
    cost:        tokens consumed by this request
    now:         optional timestamp (seconds); defaults to time.monotonic()

    Returns True if the request is allowed, False if it is rate limited.
    """
    if now is None:
        now = time.monotonic()

    bucket = buckets.get(client_id)
    if bucket is None:
        # New clients start with a full bucket.
        bucket = {"tokens": float(capacity), "last": now}
        buckets[client_id] = bucket
    else:
        elapsed = max(0.0, now - bucket["last"])
        bucket["tokens"] = min(float(capacity), bucket["tokens"] + elapsed * refill_rate)
        bucket["last"] = now

    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True
    return False
