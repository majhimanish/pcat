import time


def make_bucket(capacity, refill_rate, now=None):
    """Create a token bucket state dict.

    capacity: maximum number of tokens the bucket can hold.
    refill_rate: tokens added per second.
    """
    if capacity <= 0:
        raise ValueError("capacity must be positive")
    if refill_rate < 0:
        raise ValueError("refill_rate must be non-negative")
    if now is None:
        now = time.monotonic()
    return {
        "capacity": float(capacity),
        "refill_rate": float(refill_rate),
        "tokens": float(capacity),
        "last_refill": now,
    }


def allow_request(bucket, now=None):
    """Refill the bucket based on elapsed time, then consume one token if available.

    Returns True if a token was consumed, False otherwise.
    """
    if now is None:
        now = time.monotonic()

    elapsed = max(0.0, now - bucket["last_refill"])
    bucket["tokens"] = min(
        bucket["capacity"],
        bucket["tokens"] + elapsed * bucket["refill_rate"],
    )
    bucket["last_refill"] = now

    if bucket["tokens"] >= 1.0:
        bucket["tokens"] -= 1.0
        return True
    return False
