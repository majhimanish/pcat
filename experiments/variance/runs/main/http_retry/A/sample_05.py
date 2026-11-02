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
    **kwargs,
):
    """GET a URL, retrying with exponential backoff and jitter on failure.

    Retries on connection errors, timeouts, and the given HTTP status codes.
    Returns the requests.Response on success; raises the last error otherwise.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **kwargs)
            if response.status_code not in retry_statuses:
                response.raise_for_status()
                return response
            last_exc = requests.HTTPError(
                f"{response.status_code} error for {url}", response=response
            )
            retry_after = response.headers.get("Retry-After")
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            retry_after = None

        if attempt == max_retries:
            break

        delay = min(max_backoff, backoff_factor * (2 ** attempt))
        delay += random.uniform(0, delay * 0.1)
        if retry_after and retry_after.isdigit():
            delay = max(delay, min(float(retry_after), max_backoff))
        time.sleep(delay)

    raise last_exc
