import random
import time

import requests


def fetch_with_retry(url, max_retries=3, base_delay=1.0, backoff_factor=2.0, timeout=10):
    """GET a URL, retrying on errors with exponentially increasing delays.

    Retries on network errors, timeouts, 5xx responses, and 429. Other 4xx
    responses are not retried. Raises the last error if all attempts fail.
    """
    retryable_statuses = {429, 500, 502, 503, 504}
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code in retryable_statuses:
                response.raise_for_status()
            response.raise_for_status()
            return response
        except (requests.ConnectionError, requests.Timeout) as e:
            last_error = e
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status not in retryable_statuses:
                raise
            last_error = e

        if attempt < max_retries:
            delay = base_delay * (backoff_factor ** attempt)
            delay += random.uniform(0, delay * 0.1)  # small jitter
            time.sleep(delay)

    raise last_error
