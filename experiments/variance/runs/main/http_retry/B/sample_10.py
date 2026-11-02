import random
import time

import requests


def get_with_retry(
    url,
    max_retries=5,
    backoff_factor=0.5,
    max_backoff=30.0,
    jitter=True,
    timeout=10,
    retry_statuses=None,
    **kwargs,
):
    """
    Perform an HTTP GET request, retrying on network errors and 5xx responses
    using exponential backoff.

    Args:
        url: The URL to request.
        max_retries: Maximum number of retries after the initial attempt.
        backoff_factor: Base delay in seconds; the delay before retry n
            (0-indexed) is backoff_factor * 2**n.
        max_backoff: Upper bound on any single delay, in seconds.
        jitter: If True, apply "full jitter" (random delay in [0, computed delay]).
        timeout: Per-request timeout in seconds.
        retry_statuses: Optional iterable of status codes to retry on.
            Defaults to all 5xx codes (500-599).
        **kwargs: Extra arguments passed to requests.get (headers, params, ...).

    Returns:
        requests.Response: The final response. A 5xx response is returned as-is
        if retries are exhausted; 4xx and other non-5xx responses are returned
        immediately without retrying.

    Raises:
        requests.exceptions.RequestException: If all attempts fail due to
        network errors (the last error is re-raised).
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")

    def should_retry_status(status):
        if retry_statuses is not None:
            return status in retry_statuses
        return 500 <= status < 600

    def compute_delay(attempt):
        delay = min(max_backoff, backoff_factor * (2 ** attempt))
        return random.uniform(0, delay) if jitter else delay

    for attempt in range(max_retries + 1):
        is_last_attempt = attempt == max_retries
        try:
            response = requests.get(url, timeout=timeout, **kwargs)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError):
            if is_last_attempt:
                raise
        else:
            if not should_retry_status(response.status_code) or is_last_attempt:
                return response
            response.close()

        time.sleep(compute_delay(attempt))
