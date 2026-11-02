import time


def make_bucket(capacity, refill_rate, now=None):
    """Create a bucket state dict.

    capacity: maximum number of tokens the bucket can hold.
    refill_rate: tokens added per second.
    """
    if now is None:
        now = time.monotonic()
    return {
        "capacity": float(capacity),
        "refill_rate": float(refill_rate),
        "tokens": float(capacity),
        "last_refill": now,
    }


def allow_request(bucket, now=None):
    """Refill based on elapsed time, then consume one token if available.

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
