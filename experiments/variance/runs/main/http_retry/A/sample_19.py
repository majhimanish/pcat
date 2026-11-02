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

    Retries on network errors (connection, timeout) and on the HTTP status
    codes listed in `retry_statuses`. Other 4xx responses are returned/raised
    immediately since retrying will not help.

    Returns the successful requests.Response; raises the last exception if
    all attempts fail.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)
            if response.status_code in retry_statuses:
                response.raise_for_status()
            response.raise_for_status()
            return response
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in retry_statuses:
                raise
            last_exc = exc
            retry_after = exc.response.headers.get("Retry-After")
            delay = None
            if retry_after and retry_after.isdigit():
                delay = float(retry_after)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            delay = None

        if attempt == max_retries:
            break

        if delay is None:
            delay = min(max_backoff, backoff_factor * (2 ** attempt))
            delay += random.uniform(0, delay * 0.1)
        time.sleep(min(delay, max_backoff))

    raise last_exc
