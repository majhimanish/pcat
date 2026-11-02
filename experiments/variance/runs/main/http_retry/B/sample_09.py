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
    headers=None,
):
    """Download a URL, retrying failures with exponentially increasing delays.

    Args:
        url: The URL to download.
        dest_path: If given, the content is written to this file path and the
            path is returned. Otherwise the raw bytes are returned.
        max_retries: Number of retries after the initial attempt.
        base_delay: Delay (seconds) before the first retry.
        max_delay: Upper bound on the delay between retries.
        backoff_factor: Multiplier applied to the delay after each failure.
        jitter: If True, randomize each delay (between 50% and 100% of the
            computed value) to avoid synchronized retries.
        timeout: Per-request timeout in seconds.
        retry_statuses: HTTP status codes considered transient and retryable.
        headers: Optional dict of request headers.

    Returns:
        The downloaded bytes, or dest_path if one was provided.

    Raises:
        The last exception encountered if all attempts fail, or immediately
        for non-retryable errors (e.g. HTTP 404).
    """
    request = urllib.request.Request(url, headers=headers or {})
    attempt = 0

    while True:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()

            if dest_path is not None:
                with open(dest_path, "wb") as f:
                    f.write(data)
                return dest_path
            return data

        except urllib.error.HTTPError as exc:
            if exc.code not in retry_statuses:
                raise
            error = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            error = exc

        if attempt >= max_retries:
            raise error

        delay = min(max_delay, base_delay * (backoff_factor ** attempt))
        if jitter:
            delay *= random.uniform(0.5, 1.0)

        print(
            f"Attempt {attempt + 1} failed ({error}); "
            f"retrying in {delay:.2f}s..."
        )
        time.sleep(delay)
        attempt += 1
