"""Approval demo (v4.1): code from http.get_with_retry.requests, written the way an agent did.

The retries were narrowed to timeouts (connection errors are no longer retried) and the agent
proposed an approval for that deviation. The pull request stays red until an approver
confirms the proposal; see examples/approval-demo/README.md.
"""

import random
import requests
import time
RETRY_STATUSES = (429, 500, 502, 503, 504)

# pcat-allow: PC100 #6db40061 -- the request says to retry only on timeouts and 5xx responses, so connection errors fail fast
# pcat: http.get_with_retry.requests@v1
def fetch_status(url: str, session: requests.Session | None=None, attempts: int=4, base_delay: float=0.5, max_delay: float=30.0, timeout: float=10.0, sleep=time.sleep, rand=random.random) -> requests.Response:
    if attempts < 1:
        raise ValueError('attempts must be >= 1')
    session = session or requests.Session()
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            response = session.get(url, timeout=timeout)
        except requests.Timeout:
            if last:
                raise
            hint = None
        else:
            if response.status_code not in RETRY_STATUSES or last:
                response.raise_for_status()
                return response
            hint = retry_after_seconds(response.headers.get('Retry-After'))
        backoff = min(max_delay, base_delay * 2 ** attempt) * rand()
        sleep(min(max_delay, hint) if hint is not None else backoff)
    raise AssertionError('unreachable')

def retry_after_seconds(value: str | None) -> float | None:
    return float(value) if value and value.strip().isdigit() else None
