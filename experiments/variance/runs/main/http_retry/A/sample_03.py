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

    Retries on connection errors, timeouts, and the given HTTP statuses.
    Returns the successful requests.Response, or raises the last error
    once all retries are exhausted.
    """
    attempt = 0
    while True:
        try:
            response = requests.get(url, timeout=timeout, **kwargs)
            if response.status_code not in retry_statuses:
                response.raise_for_status()
                return response
            error = requests.HTTPError(
                f"{response.status_code} error for {url}", response=response
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            error = exc

        if attempt >= max_retries:
            raise error

        delay = min(max_backoff, backoff_factor * (2 ** attempt))
        retry_after = None
        resp = getattr(error, "response", None)
        if resp is not None:
            retry_after = resp.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            delay = max(delay, min(float(retry_after), max_backoff))
        time.sleep(delay * random.uniform(0.5, 1.0))
        attempt += 1
