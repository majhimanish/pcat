import random
import time

import requests


def get_with_retry(
    url,
    max_retries=5,
    base_delay=1.0,
    max_delay=30.0,
    timeout=10,
    retry_statuses=(429, 500, 502, 503, 504),
    **kwargs,
):
    """GET a URL, retrying with exponential backoff and jitter on failure.

    Retries on network errors (connection, timeout) and on the HTTP status
    codes in `retry_statuses`. Other 4xx responses are raised immediately.
    Returns the successful requests.Response, or raises the last error once
    retries are exhausted.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **kwargs)
            if response.status_code in retry_statuses:
                response.raise_for_status()
            response.raise_for_status()
            return response
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in retry_statuses:
                raise
            last_exc = exc

        if attempt == max_retries:
            break

        delay = min(max_delay, base_delay * (2 ** attempt))
        delay = random.uniform(0, delay)  # full jitter
        time.sleep(delay)

    raise last_exc
