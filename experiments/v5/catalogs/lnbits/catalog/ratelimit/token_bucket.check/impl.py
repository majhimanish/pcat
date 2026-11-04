"""Token-bucket rate limiting with per-key state in a plain dict; returns (allowed, retry_after).

Standard library only. State: buckets[key] = {"tokens": float, "last": float}.
"""

import time
from collections.abc import MutableMapping


def check_rate_limit(
    buckets: MutableMapping[str, dict[str, float]], key: str, capacity: float = 10.0,
    refill_rate: float = 1.0, cost: float = 1.0, now: float | None = None,
) -> tuple[bool, float]:
    """Refill `key`'s bucket, then take `cost` tokens if available.

    Returns (True, 0.0) when allowed, else (False, seconds until it would be),
    suitable for an HTTP Retry-After header. New keys start full; `now`
    defaults to time.monotonic(). Not thread-safe; one process only.
    """
    if capacity <= 0 or refill_rate <= 0 or cost <= 0:
        raise ValueError("capacity, refill_rate and cost must be positive")
    if cost > capacity:
        raise ValueError("cost can never be satisfied: it exceeds capacity")
    now = time.monotonic() if now is None else now
    bucket = buckets.get(key)
    if bucket is None:
        bucket = buckets[key] = {"tokens": float(capacity), "last": now}
    elapsed = max(0.0, now - bucket["last"])  # a clock that goes backwards adds nothing
    bucket["tokens"] = min(float(capacity), bucket["tokens"] + elapsed * refill_rate)
    bucket["last"] = now
    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True, 0.0
    return False, (cost - bucket["tokens"]) / refill_rate
