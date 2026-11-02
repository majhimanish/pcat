import random
import time

import requests


def get_with_retries(
    url,
    max_retries=5,
    backoff_factor=0.5,
    max_backoff=30.0,
    timeout=10,
    retry_statuses=(429, 500, 502, 503, 504),
    **request_kwargs,
):
    """GET a URL, retrying with exponential backoff and jitter on failure.

    Retries on connection errors, timeouts, and the given HTTP status codes.
    Raises the last exception (or HTTPError) if all attempts fail.
    """
    attempts = max_retries + 1
    last_exc = None

    for attempt in range(attempts):
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)
            if response.status_code not in retry_statuses:
                response.raise_for_status()
                return response
            last_exc = requests.HTTPError(
                f"{response.status_code} error for url: {url}", response=response
            )
            delay = _retry_after_seconds(response)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            delay = None

        if attempt == attempts - 1:
            break

        if delay is None:
            delay = min(max_backoff, backoff_factor * (2 ** attempt))
            delay = random.uniform(0, delay)
        time.sleep(min(delay, max_backoff))

    raise last_exc


def _retry_after_seconds(response):
    """Return the Retry-After header as seconds, or None if absent/invalid."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
