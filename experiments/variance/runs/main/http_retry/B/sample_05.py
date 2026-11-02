import random
import time
import urllib.error
import urllib.request


def get_with_retry(
    url,
    headers=None,
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    timeout=10.0,
    jitter=True,
):
    """
    Perform an HTTP GET request, retrying on network errors and 5xx responses
    with exponential backoff.

    Returns a tuple (status_code, response_headers, body_bytes).
    4xx responses are returned immediately without retrying.
    Raises the last exception (or urllib.error.HTTPError for a final 5xx)
    if all attempts are exhausted.
    """
    attempt = 0
    while True:
        try:
            req = urllib.request.Request(url, headers=headers or {}, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            # Non-5xx HTTP errors (e.g. 4xx) are not retryable.
            if not (500 <= e.code < 600):
                return e.code, dict(e.headers), e.read()
            last_error = e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_error = e

        if attempt >= max_retries:
            raise last_error

        delay = _compute_delay(attempt, base_delay, max_delay, jitter)
        time.sleep(delay)
        attempt += 1


def _compute_delay(attempt, base_delay, max_delay, jitter):
    """Exponential backoff: base_delay * 2**attempt, capped, with optional full jitter."""
    delay = min(max_delay, base_delay * (2 ** attempt))
    if jitter:
        delay = random.uniform(0, delay)
    return delay
