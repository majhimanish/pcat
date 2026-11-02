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

    Retries on network errors (connection/timeout) and on the HTTP status
    codes in `retry_statuses`. Honors a numeric Retry-After header if present.
    Returns the requests.Response on success; raises the last exception
    (or requests.HTTPError for a final bad status) when retries are exhausted.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        delay = min(max_backoff, backoff_factor * (2 ** attempt))
        delay = random.uniform(0, delay)  # full jitter

        try:
            response = requests.get(url, timeout=timeout, **kwargs)

            if response.status_code in retry_statuses:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = min(max_backoff, float(retry_after))
                last_exc = requests.HTTPError(
                    f"{response.status_code} error for {url}", response=response
                )
            else:
                response.raise_for_status()
                return response

        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc

        if attempt < max_retries:
            time.sleep(delay)

    raise last_exc
