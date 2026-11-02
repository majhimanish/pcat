import random
import time
import urllib.error
import urllib.request


def download_with_retry(
    url,
    max_retries=5,
    base_delay=1.0,
    max_delay=60.0,
    backoff_factor=2.0,
    jitter=True,
    timeout=30,
    headers=None,
):
    """Download a URL, retrying failures with exponentially increasing delays.

    Returns the response body as bytes. Raises the last error if all attempts fail.
    Client errors (4xx, except 408 and 429) are not retried.
    """
    retryable_statuses = {408, 429, 500, 502, 503, 504}
    request = urllib.request.Request(url, headers=headers or {})
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code not in retryable_statuses:
                raise
            last_error = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_error = e

        if attempt == max_retries:
            break

        delay = min(base_delay * (backoff_factor ** attempt), max_delay)
        if jitter:
            delay = random.uniform(0, delay)
        time.sleep(delay)

    raise last_error


def download_to_file(url, path, **kwargs):
    """Download a URL with retries and save it to the given file path."""
    data = download_with_retry(url, **kwargs)
    with open(path, "wb") as f:
        f.write(data)
    return path
