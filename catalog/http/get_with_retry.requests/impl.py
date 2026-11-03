"""GET with retries, capped exponential backoff, full jitter and Retry-After.

Requires: requests>=2.31,<3. Retries connection errors, timeouts, 429 and 5xx.
"""

import random
import time

import requests

RETRY_STATUSES = (429, 500, 502, 503, 504)


def retry_after_seconds(value: str | None) -> float | None:
    """Seconds from a numeric Retry-After header (HTTP-date form is ignored)."""
    return float(value) if value and value.strip().isdigit() else None


def get_with_retry(url: str, session: requests.Session | None = None, attempts: int = 4,
                   base_delay: float = 0.5, max_delay: float = 30.0, timeout: float = 10.0,
                   sleep=time.sleep, rand=random.random) -> requests.Response:
    """Return the first successful response; raise the last error otherwise."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    session = session or requests.Session()
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            response = session.get(url, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout):
            if last:
                raise
            hint = None
        else:
            if response.status_code not in RETRY_STATUSES or last:
                response.raise_for_status()
                return response
            hint = retry_after_seconds(response.headers.get("Retry-After"))
        backoff = min(max_delay, base_delay * 2 ** attempt) * rand()
        sleep(min(max_delay, hint) if hint is not None else backoff)
    raise AssertionError("unreachable")
