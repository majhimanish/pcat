"""Token-bucket rate limiting with per-key state in a plain dict; returns a bool.

Standard library only. State: buckets[key] = {"tokens": float, "last": float}.
"""

import time
from collections.abc import MutableMapping


def allow_request(buckets: MutableMapping[str, dict[str, float]], key: str, capacity: float = 10.0,
                  refill_rate: float = 1.0, cost: float = 1.0, now: float | None = None) -> bool:
    """Refill `key`'s bucket for the elapsed time, then take `cost` tokens if available.

    New keys start full. `refill_rate` is tokens per second; `now` defaults to
    time.monotonic() (inject it in tests). Not thread-safe; one process only.
    """
    if capacity <= 0 or refill_rate <= 0 or cost <= 0:
        raise ValueError("capacity, refill_rate and cost must be positive")
    now = time.monotonic() if now is None else now
    bucket = buckets.get(key)
    if bucket is None:
        bucket = buckets[key] = {"tokens": float(capacity), "last": now}
    elapsed = max(0.0, now - bucket["last"])  # a clock that goes backwards adds nothing
    bucket["tokens"] = min(float(capacity), bucket["tokens"] + elapsed * refill_rate)
    bucket["last"] = now
    if bucket["tokens"] >= cost:
        bucket["tokens"] -= cost
        return True
    return False
