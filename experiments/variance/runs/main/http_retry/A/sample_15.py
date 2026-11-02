import random
import time

import requests


def get_with_retries(
    url,
    max_retries=5,
    base_delay=1.0,
    max_delay=30.0,
    backoff_factor=2.0,
    timeout=10,
    retry_statuses=(429, 500, 502, 503, 504),
    **request_kwargs,
):
    """GET a URL, retrying with exponential backoff and jitter on failure.

    Retries on connection errors, timeouts, and the given HTTP status codes.
    Other 4xx responses are raised immediately without retrying.
    Returns the successful requests.Response, or raises the last error.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        retry_after = None
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)
            if response.status_code not in retry_statuses:
                response.raise_for_status()
                return response

            last_exc = requests.HTTPError(
                f"{response.status_code} error for url: {url}", response=response
            )
            header = response.headers.get("Retry-After")
            if header and header.isdigit():
                retry_after = float(header)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc

        if attempt == max_retries:
            break

        delay = min(max_delay, base_delay * (backoff_factor ** attempt))
        delay = random.uniform(0, delay)  # full jitter
        if retry_after is not None:
            delay = max(delay, min(retry_after, max_delay))
        time.sleep(delay)

    raise last_exc
