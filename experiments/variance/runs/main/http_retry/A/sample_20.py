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
    **request_kwargs,
):
    """GET a URL, retrying with exponential backoff and jitter on failure.

    Retries on connection errors, timeouts, and retryable HTTP status codes.
    Returns the successful requests.Response, or raises the last error once
    retries are exhausted.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)

            if response.status_code in retry_statuses:
                response.raise_for_status()

            # Non-retryable 4xx errors raise immediately and are not retried.
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

        delay = min(max_backoff, backoff_factor * (2 ** attempt))
        delay += random.uniform(0, delay * 0.1)
        time.sleep(delay)

    raise last_exc
