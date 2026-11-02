import random
import time

import requests


def get_with_retries(
    url,
    max_retries=5,
    base_delay=1.0,
    max_delay=30.0,
    backoff_factor=2.0,
    timeout=10,
    retry_statuses=(429, 500, 502, 503, 504),
    **request_kwargs,
):
    """GET a URL, retrying with exponential backoff and jitter on failure.

    Retries on connection errors, timeouts, and the given HTTP status codes.
    Returns the successful requests.Response; raises the last error if all
    attempts fail.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)
            if response.status_code not in retry_statuses:
                response.raise_for_status()
                return response
            last_exc = requests.HTTPError(
                f"HTTP {response.status_code} for {url}", response=response
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc

        if attempt == max_retries:
            break

        delay = min(max_delay, base_delay * (backoff_factor ** attempt))

        # Honor Retry-After header if the server provided one
        resp = getattr(last_exc, "response", None)
        if resp is not None:
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = min(max_delay, max(delay, float(retry_after)))

        time.sleep(delay * random.uniform(0.5, 1.0))

    raise last_exc
