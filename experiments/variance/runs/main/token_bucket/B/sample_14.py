import time

def allow_request(buckets, client_id, capacity=10, refill_rate=1.0, cost=1, now=None):
    """
    Token-bucket rate limiter. Each client's bucket is stored in `buckets`,
    a dict mapping client_id -> {"tokens": float, "last": float}.

    capacity    : maximum tokens a bucket can hold (burst size)
    refill_rate : tokens added per second
    cost        : tokens consumed by this request
    now         : optional timestamp (seconds); defaults to time.monotonic()

    Returns (allowed: bool, retry_after: float) where retry_after is the
    number of seconds until enough tokens are available (0.0 if allowed).
    """
    if now is None:
        now = time.monotonic()

    bucket = buckets.get(client_id)
    if bucket is None:
        # New clients start with a full bucket.
        bucket = {"tokens": float(capacity), "last": now}
        buckets[client_id] = bucket
    else:
        # Refill based on elapsed time, capped at capacity.
        elapsed = max(0.0, now - bucket["last"])
        bucket["tokens"] = min(capacity, bucket["tokens"] + elapsed * refill_rate)
        bucket["last"] = now

    if cost > capacity:
        return False, float("inf")

    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True, 0.0

    deficit = cost - bucket["tokens"]
    retry_after = deficit / refill_rate if refill_rate > 0 else float("inf")
    return False, retry_after
