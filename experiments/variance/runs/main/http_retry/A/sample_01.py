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

    Retries on network errors (connection errors, timeouts) and on
    responses whose status code is in `retry_statuses`. Other 4xx errors
    are raised immediately. Returns the successful requests.Response.
    Raises the last exception if all attempts fail.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)

            if response.status_code in retry_statuses:
                retry_after = response.headers.get("Retry-After")
                last_exc = requests.HTTPError(
                    f"{response.status_code} error for {url}", response=response
                )
                if attempt == max_retries:
                    raise last_exc
                delay = None
                if retry_after and retry_after.isdigit():
                    delay = min(float(retry_after), max_backoff)
            else:
                response.raise_for_status()
                return response

        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt == max_retries:
                raise
            delay = None

        if delay is None:
            delay = min(backoff_factor * (2 ** attempt), max_backoff)
            delay *= random.uniform(0.5, 1.5)

        time.sleep(delay)

    raise last_exc
