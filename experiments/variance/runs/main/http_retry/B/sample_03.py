import time
import random
import requests


def fetch_with_retry(url, max_retries=3, base_delay=1.0, backoff_factor=2.0, timeout=10):
    """GET `url`, retrying on errors with exponentially increasing delays (plus jitter).

    Retries on network errors, timeouts, 5xx and 429 responses.
    Other 4xx responses are not retried. Raises the last error if all attempts fail.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and status < 500 and status != 429:
                raise  # client error: retrying won't help
            last_exc = exc
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exc:
            last_exc = exc

        if attempt < max_retries:
            delay = base_delay * (backoff_factor ** attempt)
            time.sleep(delay + random.uniform(0, delay * 0.1))

    raise last_exc
