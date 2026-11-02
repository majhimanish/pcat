import random
import time
import urllib.error
import urllib.request


def _is_retryable_status(status):
    """Return True for server-side (5xx) HTTP status codes."""
    return 500 <= status <= 599


def _compute_delay(attempt, base_delay, max_delay, jitter):
    """Compute exponential backoff delay for a given zero-based attempt."""
    delay = min(max_delay, base_delay * (2 ** attempt))
    if jitter:
        delay = random.uniform(0, delay)
    return delay


def get_with_retry(
    url,
    headers=None,
    timeout=10.0,
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    jitter=True,
    sleep=time.sleep,
):
    """
    Perform an HTTP GET request, retrying on network errors and 5xx responses
    using exponential backoff.

    Args:
        url: The URL to request.
        headers: Optional dict of request headers.
        timeout: Per-request timeout in seconds.
        max_retries: Number of retries after the initial attempt.
        base_delay: Initial backoff delay in seconds.
        max_delay: Upper bound on any single backoff delay.
        jitter: If True, apply full jitter to each delay.
        sleep: Sleep function (injectable for testing).

    Returns:
        A tuple (status_code, headers_dict, body_bytes) for the first
        non-5xx response (including 4xx, which are not retried).

    Raises:
        urllib.error.URLError / OSError: if all attempts fail due to network
            errors.
        urllib.error.HTTPError: if all attempts end with a 5xx response.
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")

    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            # HTTPError is a subclass of URLError; check it first.
            if not _is_retryable_status(exc.code):
                # 4xx and other non-5xx errors: return without retrying.
                body = exc.read()
                return exc.code, dict(exc.headers), body
            last_error = exc
        except (urllib.error.URLError, OSError):
            # Network-level failures: DNS, connection refused, timeouts, resets.
            # (socket.timeout and ConnectionError are OSError subclasses.)
            last_error = _current_exception()

        if attempt < max_retries:
            sleep(_compute_delay(attempt, base_delay, max_delay, jitter))

    raise last_error


def _current_exception():
    """Return the exception currently being handled."""
    import sys
    return sys.exc_info()[1]
