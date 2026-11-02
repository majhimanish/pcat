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
        dest_path: If given, write the content to this file path and return it.
                   Otherwise return the content as bytes.
        max_retries: Number of retries after the initial attempt.
        base_delay: Initial delay in seconds.
        max_delay: Upper bound for any single delay.
        backoff_factor: Multiplier applied to the delay after each failure.
        jitter: If True, sleep a random time between 0 and the computed delay.
        timeout: Per-request timeout in seconds.
        retry_statuses: HTTP status codes considered transient and retryable.

    Returns:
        bytes if dest_path is None, otherwise dest_path.

    Raises:
        urllib.error.HTTPError: For non-retryable HTTP errors, or when retries are exhausted.
        Exception: The last error encountered once retries are exhausted.
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                data = response.read()

            if dest_path is None:
                return data

            with open(dest_path, "wb") as f:
                f.write(data)
            return dest_path

        except urllib.error.HTTPError as e:
            if e.code not in retry_statuses:
                raise
            last_error = e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_error = e

        if attempt == max_retries:
            break

        delay = min(max_delay, base_delay * (backoff_factor ** attempt))
        if jitter:
            delay = random.uniform(0, delay)
        time.sleep(delay)

    raise last_error
