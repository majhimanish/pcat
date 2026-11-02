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
    codes in `retry_statuses`. Other 4xx responses are raised immediately.
    Returns the successful requests.Response; raises the last error if all
    attempts fail.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)
            if response.status_code in retry_statuses:
                raise requests.HTTPError(
                    f"Retryable status {response.status_code} for {url}",
                    response=response,
                )
            response.raise_for_status()
            return response
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
        except requests.HTTPError as exc:
            resp = exc.response
            if resp is None or resp.status_code not in retry_statuses:
                raise
            last_exc = exc

        if attempt == max_retries:
            break

        delay = min(max_backoff, backoff_factor * (2 ** attempt))
        delay *= random.uniform(0.5, 1.5)

        # Honor Retry-After if the server sent a numeric value.
        resp = getattr(last_exc, "response", None)
        if resp is not None:
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = max(delay, min(float(retry_after), max_backoff))

        time.sleep(delay)

    raise last_exc
