import random
import time

import requests


def get_with_retries(
    url,
    max_retries=5,
    base_delay=1.0,
    max_delay=30.0,
    timeout=10,
    retry_statuses=(429, 500, 502, 503, 504),
    **request_kwargs,
):
    """GET a URL, retrying with exponential backoff and jitter on failure.

    Retries on network errors (connection errors, timeouts) and on the HTTP
    status codes listed in `retry_statuses`. Other 4xx responses are raised
    immediately. Raises the last error if all attempts are exhausted.
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, **request_kwargs)

            if response.status_code in retry_statuses:
                response.raise_for_status()

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

        delay = min(max_delay, base_delay * (2 ** attempt))
        delay *= random.uniform(0.5, 1.0)  # jitter

        # Honor Retry-After header if the server provided one (seconds form)
        resp = getattr(last_exc, "response", None)
        if resp is not None:
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = max(delay, min(float(retry_after), max_delay))

        time.sleep(delay)

    raise last_exc
