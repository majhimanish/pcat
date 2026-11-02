import time
import random

import requests


def fetch_with_retry(url, max_retries=3, base_delay=1.0, timeout=10):
    """GET a URL, retrying on errors with exponential backoff and jitter.

    Retries on network errors, timeouts, 5xx, and 429 responses.
    Other 4xx responses are not retried. Returns the successful
    requests.Response, or raises the last error once retries are exhausted.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            response.raise_for_status()
            return response
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None and status < 500 and status != 429:
                raise
            last_error = e
        except (requests.ConnectionError, requests.Timeout) as e:
            last_error = e

        if attempt < max_retries:
            delay = base_delay * (2 ** attempt)
            delay += random.uniform(0, delay * 0.1)
            time.sleep(delay)

    raise last_error
