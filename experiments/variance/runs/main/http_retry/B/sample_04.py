import random
import time
import urllib.error
import urllib.request


def download_with_retry(
    url,
    dest_path=None,
    max_retries=5,
    base_delay=1.0,
    max_delay=60.0,
    backoff_factor=2.0,
    jitter=True,
    timeout=30,
    retry_statuses=(408, 425, 429, 500, 502, 503, 504),
):
    """Download a URL, retrying failures with exponentially increasing delays.

    Delay before retry n (0-based) is min(max_delay, base_delay * backoff_factor**n),
    optionally randomized ("full jitter") to avoid synchronized retries.

    Args:
        url: The URL to download.
        dest_path: If given, the content is written to this file path.
        max_retries: Number of retries after the initial attempt.
        base_delay: Initial delay in seconds.
        max_delay: Upper bound on any single delay.
        backoff_factor: Multiplier applied to the delay after each failure.
        jitter: If True, sleep a random time between 0 and the computed delay.
        timeout: Per-request timeout in seconds.
        retry_statuses: HTTP status codes considered transient and retryable.

    Returns:
        The downloaded bytes (also written to dest_path if provided).

    Raises:
        The last exception encountered if all attempts fail, or immediately
        for non-retryable HTTP errors (e.g. 404).
    """
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "python-download-with-retry/1.0"}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()

            if dest_path is not None:
                with open(dest_path, "wb") as f:
                    f.write(data)
            return data

        except urllib.error.HTTPError as exc:
            if exc.code not in retry_statuses:
                raise
            last_exc = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_exc = exc

        if attempt < max_retries:
            delay = min(max_delay, base_delay * (backoff_factor ** attempt))
            if jitter:
                delay = random.uniform(0, delay)
            time.sleep(delay)

    raise last_exc
