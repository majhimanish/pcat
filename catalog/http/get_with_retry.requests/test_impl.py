import pytest

requests = pytest.importorskip("requests")
from impl import get_with_retry, retry_after_seconds  # noqa: E402

URL = "https://example.test/resource"


def response(status, retry_after=None, body=b""):
    r = requests.Response()
    r.status_code, r.url, r._content = status, URL, body
    if retry_after is not None:
        r.headers["Retry-After"] = retry_after
    return r


class FakeSession:
    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        item = self.outcomes[len(self.calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item


def run(*outcomes, **kw):
    session, sleeps = FakeSession(*outcomes), []
    kw.setdefault("rand", lambda: 1.0)
    result = get_with_retry(URL, session=session, sleep=sleeps.append, **kw)
    return result, session.calls, sleeps


# Normal cases ---------------------------------------------------------------
def test_success_first_try():
    result, calls, sleeps = run(response(200, body=b"ok"))
    assert result.content == b"ok" and calls == [(URL, 10.0)] and sleeps == []


def test_recovers_from_errors_and_5xx_with_backoff():
    result, calls, sleeps = run(requests.ConnectionError(), requests.Timeout(), response(502), response(200))
    assert result.status_code == 200 and len(calls) == 4 and sleeps == [0.5, 1.0, 2.0]


def test_custom_timeout_attempts_and_delays():
    _, calls, sleeps = run(response(503), response(503), response(503), response(503), response(200),
                           attempts=5, base_delay=2.0, max_delay=10.0, timeout=3.0)
    assert {t for _, t in calls} == {3.0} and sleeps == [2.0, 4.0, 8.0, 10.0]


# Jitter, Retry-After ------------------------------------------------------------
def test_full_jitter_scales_the_backoff():
    _, _, sleeps = run(response(500), response(500), response(200), rand=lambda: 0.25)
    assert sleeps == [0.125, 0.25]
    _, _, zero = run(response(500), response(200), rand=lambda: 0.0)
    assert zero == [0.0]


def test_retry_after_seconds_used_and_capped():
    _, _, sleeps = run(response(429, "7"), response(503, "86400"), response(200))
    assert sleeps == [7.0, 30.0]


def test_retry_after_http_date_or_garbage_falls_back_to_backoff():
    _, _, sleeps = run(response(503, "Wed, 21 Oct 2015 07:28:00 GMT"), response(503, "soon"), response(200))
    assert sleeps == [0.5, 1.0]
    assert retry_after_seconds(" 12 ") == 12.0 and retry_after_seconds(None) is None
    assert retry_after_seconds("-5") is None and retry_after_seconds("1.5") is None


# Failure cases ------------------------------------------------------------------------
@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422])
def test_client_errors_are_raised_immediately(status):
    session = FakeSession(response(status))
    with pytest.raises(requests.HTTPError):
        get_with_retry(URL, session=session, sleep=lambda s: pytest.fail("no sleep"))
    assert len(session.calls) == 1


def test_exhausted_retries_raise_the_last_error():
    with pytest.raises(requests.HTTPError) as info:
        run(response(503), response(503), response(429), attempts=3)
    assert info.value.response.status_code == 429
    with pytest.raises(requests.Timeout):
        run(requests.ConnectionError(), requests.Timeout(), attempts=2)


def test_single_attempt_never_sleeps():
    with pytest.raises(requests.HTTPError):
        run(response(500), attempts=1)


def test_attempts_validated():
    with pytest.raises(ValueError, match="attempts"):
        get_with_retry(URL, session=FakeSession(), attempts=0)


def test_other_request_exceptions_are_not_retried():
    with pytest.raises(requests.exceptions.InvalidURL):
        run(requests.exceptions.InvalidURL("bad"), response(200))
