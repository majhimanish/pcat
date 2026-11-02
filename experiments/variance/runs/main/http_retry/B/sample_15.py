import random
import time

import requests


def get_with_retry(
    url,
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    backoff_factor=2.0,
    jitter=True,
    timeout=10,
    **kwargs,
):
    """Perform a GET request, retrying on network errors and 5xx responses.

    Uses exponential backoff: delay = min(max_delay, base_delay * backoff_factor ** attempt),
    optionally with full jitter. Non-5xx responses (including 4xx) are returned
    immediately without retrying.

    Args:
        url: The URL to request.
        max_retries: Maximum number of retries after the initial attempt.
        base_delay: Initial delay in seconds.
        max_delay: Upper bound on the delay between attempts.
        backoff_factor: Multiplier applied to the delay on each retry.
        jitter: If True, sleep a random time in [0, delay] to avoid thundering herd.
        timeout: Per-request timeout in seconds.
        **kwargs: Extra arguments passed to requests.get (headers, params, etc.).

    Returns:
        requests.Response for the first non-5xx response, or the last 5xx
        response if retries are exhausted.

    Raises:
        requests.exceptions.RequestException: If the final attempt fails with a
            network error.
    """
    last_response = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **kwargs)
            if response.status_code < 500:
                return response
            last_response = response
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt == max_retries:
                raise

        if attempt == max_retries:
            break

        delay = min(max_delay, base_delay * (backoff_factor ** attempt))
        if jitter:
            delay = random.uniform(0, delay)
        time.sleep(delay)

    return last_response
