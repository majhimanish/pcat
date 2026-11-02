import random
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def _parse_retry_after(value):
    """Return seconds to wait from a Retry-After header, or None."""
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        target = parsedate_to_datetime(value)
        return max(0.0, target.timestamp() - time.time())
    except (TypeError, ValueError):
        return None


def _compute_delay(attempt, base_delay, max_delay, jitter, retry_after=None):
    """Exponential backoff with optional jitter; honors Retry-After if given."""
    delay = min(max_delay, base_delay * (2 ** attempt))
    if jitter:
        delay = random.uniform(delay / 2, delay)
    if retry_after is not None:
        delay = max(delay, min(retry_after, max_delay))
    return delay


def http_get(
    url,
    headers=None,
    timeout=10.0,
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    jitter=True,
    retry_statuses=RETRYABLE_STATUS,
):
    """
    Perform an HTTP GET, retrying on transient failures with exponential backoff.

    Retries on network errors, timeouts, and status codes in `retry_statuses`.
    Honors the Retry-After header. Non-retryable HTTP errors are raised immediately.

    Returns a tuple: (status_code, response_headers, body_bytes).
    Raises the last exception if all attempts fail.
    """
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    last_exc = None

    for attempt in range(max_retries + 1):
        retry_after = None
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in retry_statuses:
                raise
            last_exc = exc
            retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
            exc.close()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_exc = exc

        if attempt == max_retries:
            break
        time.sleep(_compute_delay(attempt, base_delay, max_delay, jitter, retry_after))

    raise last_exc


def http_get_text(url, encoding="utf-8", **kwargs):
    """Convenience wrapper around http_get that returns the decoded body."""
    _, _, body = http_get(url, **kwargs)
    return body.decode(encoding, errors="replace")
