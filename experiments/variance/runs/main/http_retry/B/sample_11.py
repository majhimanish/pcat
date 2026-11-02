import random
import time

import requests


def fetch_with_retry(
    url,
    max_retries=5,
    base_delay=1.0,
    max_delay=30.0,
    timeout=10.0,
    retry_statuses=(429, 500, 502, 503, 504),
    **request_kwargs,
):
    """GET a URL, retrying with exponential backoff and jitter on failure.

    Retries on connection errors, timeouts, and retryable HTTP status codes.
    Non-retryable 4xx responses are raised immediately.
    Returns the successful requests.Response; raises the last error once
    all retries are exhausted.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)

            if response.status_code in retry_statuses:
                retry_after = response.headers.get("Retry-After")
                response.raise_for_status()

            response.raise_for_status()
            return response

        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in retry_statuses:
                raise
            last_exc = exc
            retry_after = exc.response.headers.get("Retry-After")
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            retry_after = None

        if attempt == max_retries:
            break

        delay = min(max_delay, base_delay * (2 ** attempt))
        delay = random.uniform(0, delay)  # full jitter
        if retry_after and retry_after.isdigit():
            delay = max(delay, min(float(retry_after), max_delay))

        time.sleep(delay)

    raise last_exc
