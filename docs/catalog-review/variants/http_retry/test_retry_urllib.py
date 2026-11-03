import io
import urllib.error
from email.message import Message

import pytest

from retry_urllib import fetch_with_retry

URL = "https://example.test/x"


def http_error(code, retry_after=None):
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(URL, code, "err", headers, io.BytesIO(b""))


def fake_urlopen(*outcomes):
    calls = []

    def urlopen(request, timeout):
        calls.append((request.full_url, request.get_method(), timeout))
        item = outcomes[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return io.BytesIO(item)

    return urlopen, calls


def run(*outcomes, **kw):
    urlopen, calls = fake_urlopen(*outcomes)
    sleeps = []
    kw.setdefault("rand", lambda: 1.0)
    return fetch_with_retry(URL, urlopen=urlopen, sleep=sleeps.append, **kw), calls, sleeps


def test_success_returns_body():
    body, calls, sleeps = run(b"hello")
    assert body == b"hello" and calls == [(URL, "GET", 10.0)] and sleeps == []


def test_retries_with_backoff():
    body, calls, sleeps = run(urllib.error.URLError("down"), TimeoutError(), http_error(502), b"ok")
    assert body == b"ok" and len(calls) == 4 and sleeps == [0.5, 1.0, 2.0]


def test_retry_after_honoured_and_capped():
    _, _, sleeps = run(http_error(429, "2"), http_error(503, "600"), b"ok")
    assert sleeps == [2.0, 30.0]


def test_client_error_not_retried_and_last_error_raised():
    with pytest.raises(urllib.error.HTTPError) as info:
        run(http_error(404))
    assert info.value.code == 404
    with pytest.raises(urllib.error.HTTPError):
        run(http_error(500), http_error(500), attempts=2)
    with pytest.raises(urllib.error.URLError):
        run(urllib.error.URLError("a"), urllib.error.URLError("b"), attempts=2)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.test/x", "/relative"])
def test_non_http_urls_rejected(url):
    with pytest.raises(ValueError, match="http"):
        fetch_with_retry(url, urlopen=lambda *a, **k: pytest.fail("must not open"))


def test_attempts_validated():
    with pytest.raises(ValueError):
        fetch_with_retry(URL, attempts=0)
