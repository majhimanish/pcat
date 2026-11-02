import time
import random

import requests


def fetch_with_retry(url, max_retries=3, base_delay=1.0, backoff_factor=2.0, timeout=10):
    """Make a GET request to `url`, retrying on errors with exponential backoff.

    Retries on network errors and on HTTP 5xx / 429 responses. Other 4xx
    responses are treated as permanent failures and raised immediately.
    Returns the successful requests.Response.
    """
    attempt = 0
    while True:
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            response.raise_for_status()
            return response
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            retryable = status == 429 or (status is not None and status >= 500)
            if not retryable or attempt >= max_retries:
                raise
        except (requests.ConnectionError, requests.Timeout):
            if attempt >= max_retries:
                raise

        delay = base_delay * (backoff_factor ** attempt)
        delay += random.uniform(0, delay * 0.1)  # small jitter
        time.sleep(delay)
        attempt += 1
