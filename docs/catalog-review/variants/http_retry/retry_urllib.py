"""GET with retries and capped exponential backoff, standard library only.

Retries connection errors, timeouts, 429 and 5xx; honours numeric Retry-After.
"""

import random
import time
import urllib.error
import urllib.request

RETRY_STATUSES = (429, 500, 502, 503, 504)


def fetch_with_retry(url: str, attempts: int = 4, base_delay: float = 0.5, max_delay: float = 30.0,
                     timeout: float = 10.0, urlopen=urllib.request.urlopen,
                     sleep=time.sleep, rand=random.random) -> bytes:
    """Return the response body of the first successful GET; raise the last error."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("only http(s) URLs are allowed")  # urlopen also reads file:// URLs
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    for attempt in range(attempts):
        last = attempt == attempts - 1
        hint = None
        try:
            with urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUSES or last:
                raise
            value = exc.headers.get("Retry-After") if exc.headers else None
            hint = float(value) if value and value.strip().isdigit() else None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if last:
                raise
        backoff = min(max_delay, base_delay * 2 ** attempt) * rand()
        sleep(min(max_delay, hint) if hint is not None else backoff)
    raise AssertionError("unreachable")
