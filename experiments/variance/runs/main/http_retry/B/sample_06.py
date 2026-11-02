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
    """GET `url`, retrying with exponential backoff and jitter on failure.

    Retries on connection errors, timeouts, and the HTTP statuses listed in
    `retry_statuses`. Other 4xx responses raise immediately since retrying
    won't help. Returns the successful requests.Response, or raises the last
    error once `max_retries` retries have been exhausted.
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)

            if response.status_code in retry_statuses:
                retry_after = response.headers.get("Retry-After")
                response.raise_for_status()

            response.raise_for_status()
            return response

        except (requests.ConnectionError, requests.Timeout) as exc:
            last_error = exc
            retry_after = None

        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in retry_statuses:
                raise
            last_error = exc

        if attempt == max_retries:
            break

        delay = min(max_delay, base_delay * (2 ** attempt))
        delay = random.uniform(0, delay)  # full jitter

        if retry_after is not None:
            try:
                delay = max(delay, min(float(retry_after), max_delay))
            except ValueError:
                pass

        time.sleep(delay)

    raise last_error
