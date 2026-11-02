import random
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import requests

RETRY_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


def parse_retry_after(value):
    """Parse a Retry-After header (seconds or HTTP date) into seconds, or None."""
    if not value:
        return None
    value = value.strip()
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


def compute_backoff(attempt, base_delay=0.5, max_delay=30.0, jitter=True):
    """Exponential backoff delay for a zero-based attempt number, with full jitter."""
    delay = min(max_delay, base_delay * (2 ** attempt))
    return random.uniform(0, delay) if jitter else delay


def http_get_with_retry(
    url,
    params=None,
    headers=None,
    timeout=10.0,
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    jitter=True,
    retry_statuses=RETRY_STATUS_CODES,
    session=None,
    **kwargs,
):
    """
    Perform an HTTP GET, retrying on connection errors, timeouts, and
    retryable status codes using exponential backoff.

    Honors the Retry-After header when present. Returns the final
    requests.Response on success or a non-retryable status. Raises the last
    requests exception if retries are exhausted on network errors; if retries
    are exhausted on a retryable status, the last response is returned so the
    caller can inspect it (use response.raise_for_status() to raise).
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")

    getter = session.get if session is not None else requests.get
    last_exc = None

    for attempt in range(max_retries + 1):
        retry_after = None
        try:
            response = getter(
                url, params=params, headers=headers, timeout=timeout, **kwargs
            )
            if response.status_code not in retry_statuses:
                return response
            if attempt == max_retries:
                return response
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            response.close()
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt == max_retries:
                raise

        delay = compute_backoff(attempt, base_delay, max_delay, jitter)
        if retry_after is not None:
            delay = min(max(delay, retry_after), max_delay)
        time.sleep(delay)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("http_get_with_retry exhausted retries unexpectedly")
