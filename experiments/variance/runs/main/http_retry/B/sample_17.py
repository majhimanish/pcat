import random
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import requests

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _parse_retry_after(value):
    """Return seconds to wait from a Retry-After header, or None."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


def _compute_delay(attempt, base_delay, max_delay, jitter):
    delay = min(max_delay, base_delay * (2 ** attempt))
    if jitter:
        delay = random.uniform(0, delay)  # full jitter
    return delay


def http_get_with_retry(
    url,
    params=None,
    headers=None,
    timeout=10,
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    jitter=True,
    retry_statuses=RETRYABLE_STATUS,
    session=None,
):
    """
    Perform an HTTP GET with retries and exponential backoff.

    Retries on connection errors, timeouts, and retryable status codes
    (honoring Retry-After when present). Non-retryable 4xx responses raise
    immediately. After max_retries retries, the last error is raised.

    Returns the successful requests.Response.
    """
    getter = session.get if session is not None else requests.get
    last_exc = None

    for attempt in range(max_retries + 1):
        retry_after = None
        try:
            response = getter(url, params=params, headers=headers, timeout=timeout)
            if response.status_code not in retry_statuses:
                response.raise_for_status()
                return response
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            last_exc = requests.HTTPError(
                f"{response.status_code} error for url: {url}", response=response
            )
            response.close()
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
        # Other exceptions (e.g. non-retryable HTTPError, invalid URL) propagate.

        if attempt == max_retries:
            break

        delay = _compute_delay(attempt, base_delay, max_delay, jitter)
        if retry_after is not None:
            delay = max(delay, min(retry_after, max_delay))
        time.sleep(delay)

    raise last_exc


def http_get_json(url, **kwargs):
    """Convenience wrapper: GET with retries and return parsed JSON."""
    return http_get_with_retry(url, **kwargs).json()
