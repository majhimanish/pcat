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

    Retries on network errors/timeouts and on retryable HTTP status codes.
    Non-retryable 4xx responses are raised immediately. Honors the
    Retry-After header when present. Returns the successful Response, or
    raises the last exception after max_retries retries are exhausted.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        retry_after = None
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)
            if response.status_code not in retry_statuses:
                response.raise_for_status()
                return response
            retry_after = response.headers.get("Retry-After")
            response.raise_for_status()
            return response
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code not in retry_statuses:
                raise
            last_exc = exc

        if attempt == max_retries:
            break

        delay = min(max_delay, base_delay * (2 ** attempt))
        delay = random.uniform(0, delay)  # full jitter
        if retry_after is not None:
            try:
                delay = max(delay, min(max_delay, float(retry_after)))
            except ValueError:
                pass
        time.sleep(delay)

    raise last_exc
