import random
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

RETRY_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


def parse_retry_after(value, max_delay=60.0):
    """Parse a Retry-After header (seconds or HTTP date) into a delay in seconds."""
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, min(float(value), max_delay))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, min(delta, max_delay))
    except (TypeError, ValueError):
        return None


def compute_backoff(attempt, base_delay=0.5, max_delay=30.0, jitter=True):
    """Exponential backoff: base_delay * 2**attempt, capped, with full jitter."""
    delay = min(max_delay, base_delay * (2 ** attempt))
    return random.uniform(0, delay) if jitter else delay


def http_get_with_retry(
    url,
    headers=None,
    timeout=10.0,
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    jitter=True,
    retry_statuses=RETRY_STATUS_CODES,
    sleep=time.sleep,
):
    """
    Perform an HTTP GET with retries and exponential backoff.

    Retries on network errors, timeouts, and retryable HTTP status codes.
    Honors the Retry-After header when present.

    Returns a tuple: (status_code, headers_dict, body_bytes).
    Raises the last exception if all retries fail, or urllib.error.HTTPError
    immediately for non-retryable HTTP errors (e.g. 404).
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
            retry_after = parse_retry_after(exc.headers.get("Retry-After"), max_delay)
            exc.close()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_exc = exc

        if attempt >= max_retries:
            break

        delay = retry_after if retry_after is not None else compute_backoff(
            attempt, base_delay, max_delay, jitter
        )
        sleep(delay)

    raise last_exc


def get_text(url, encoding="utf-8", **kwargs):
    """Convenience wrapper returning the response body decoded as text."""
    _, _, body = http_get_with_retry(url, **kwargs)
    return body.decode(encoding, errors="replace")


def get_json(url, **kwargs):
    """Convenience wrapper returning the response body parsed as JSON."""
    import json

    _, _, body = http_get_with_retry(url, **kwargs)
    return json.loads(body.decode("utf-8"))
