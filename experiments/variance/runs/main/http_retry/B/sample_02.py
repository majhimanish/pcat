import random
import time

import requests

RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


def _parse_retry_after(value):
    """Parse a Retry-After header (seconds) into a float, or None if invalid."""
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def _compute_delay(attempt, base_delay, max_delay, jitter, retry_after=None):
    """Return exponential backoff delay, honoring Retry-After when provided."""
    delay = min(max_delay, base_delay * (2 ** attempt))
    if retry_after is not None:
        delay = min(max_delay, max(delay, retry_after))
    if jitter:
        delay = random.uniform(delay / 2, delay)
    return delay


def http_get_with_retry(
    url,
    params=None,
    headers=None,
    timeout=10.0,
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    jitter=True,
    retry_statuses=RETRYABLE_STATUS_CODES,
    session=None,
):
    """
    Perform an HTTP GET request, retrying with exponential backoff.

    Retries on connection errors, timeouts, and retryable HTTP status codes
    (honoring the Retry-After header when present). Non-retryable error
    statuses raise immediately via raise_for_status().

    Args:
        url: URL to request.
        params: Optional query parameters.
        headers: Optional request headers.
        timeout: Per-request timeout in seconds.
        max_retries: Number of retries after the initial attempt.
        base_delay: Initial backoff delay in seconds.
        max_delay: Upper bound on any single backoff delay.
        jitter: If True, randomize delay to avoid thundering herd.
        retry_statuses: Iterable of status codes that trigger a retry.
        session: Optional requests.Session to reuse connections.

    Returns:
        requests.Response with a successful (non-error) status.

    Raises:
        requests.RequestException: If all attempts fail or a non-retryable
            error occurs.
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

        if attempt == max_retries:
            break
        time.sleep(_compute_delay(attempt, base_delay, max_delay, jitter, retry_after))

    raise last_exc
