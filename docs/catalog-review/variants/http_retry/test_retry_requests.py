import pytest

requests = pytest.importorskip("requests")
from retry_requests import get_with_retry, retry_after_seconds  # noqa: E402


def response(status, retry_after=None):
    r = requests.Response()
    r.status_code = status
    r.url = "https://example.test/x"
    if retry_after is not None:
        r.headers["Retry-After"] = retry_after
    return r


def fake_session(*outcomes):
    calls = []

    def get(url, timeout):
        calls.append((url, timeout))
        item = outcomes[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    return type("FakeSession", (), {"get": staticmethod(get)})(), calls


def run(*outcomes, **kw):
    session, calls = fake_session(*outcomes)
    sleeps = []
    kw.setdefault("rand", lambda: 1.0)
    result = get_with_retry("https://example.test/x", session=session, sleep=sleeps.append, **kw)
    return result, calls, sleeps


def test_first_try_success_no_sleep():
    result, calls, sleeps = run(response(200))
    assert result.status_code == 200 and len(calls) == 1 and sleeps == []
    assert calls[0][1] == 10.0  # a timeout is always passed


def test_retries_errors_and_5xx_with_exponential_backoff():
    result, calls, sleeps = run(requests.ConnectionError(), requests.Timeout(), response(503), response(200))
    assert result.status_code == 200 and len(calls) == 4 and sleeps == [0.5, 1.0, 2.0]


def test_full_jitter_and_cap():
    _, _, sleeps = run(response(500), response(500), response(200), base_delay=20.0, rand=lambda: 0.5)
    assert sleeps == [10.0, 15.0]  # 20*0.5, then min(30, 40)*0.5


def test_retry_after_is_honoured_and_capped():
    _, _, sleeps = run(response(429, "3"), response(429, "9999"), response(200))
    assert sleeps == [3.0, 30.0]
    assert retry_after_seconds("Wed, 21 Oct 2015 07:28:00 GMT") is None


def test_client_errors_are_not_retried():
    with pytest.raises(requests.HTTPError):
        run(response(404))


def test_gives_up_after_attempts():
    with pytest.raises(requests.HTTPError):
        run(response(503), response(503), attempts=2)
    with pytest.raises(requests.ConnectionError):
        run(requests.ConnectionError(), requests.ConnectionError(), attempts=2)


def test_attempts_validated():
    with pytest.raises(ValueError):
        get_with_retry("https://example.test", attempts=0)
