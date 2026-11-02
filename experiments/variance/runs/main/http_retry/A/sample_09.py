import random
import time

import requests


def get_with_retries(
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
    codes listed in `retry_statuses`. Other 4xx errors are raised immediately.
    Returns the successful requests.Response; raises the last error once
    retries are exhausted.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        retry_after = None
        try:
            response = requests.get(url, timeout=timeout, **kwargs)
            if response.status_code not in retry_statuses:
                response.raise_for_status()
                return response
            retry_after = response.headers.get("Retry-After")
            last_exc = requests.HTTPError(
                f"{response.status_code} error for url: {url}", response=response
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc

        if attempt == max_retries:
            break

        delay = min(max_delay, base_delay * (2 ** attempt))
        delay = random.uniform(0, delay)
        if retry_after is not None and str(retry_after).isdigit():
            delay = max(delay, min(max_delay, float(retry_after)))
        time.sleep(delay)

    raise last_exc
