import pytest

from impl import retry_with_exponential_backoff


class Flaky:
    """Fails `failures` times with `error`, then returns `result`."""

    def __init__(self, failures, error=ConnectionError, result="ok"):
        self.failures = failures
        self.error = error
        self.result = result
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error(f"failure {self.calls}")
        return self.result


def test_success_first_try_does_not_sleep():
    sleeps = []
    assert retry_with_exponential_backoff(lambda: 42, sleep=sleeps.append) == 42
    assert sleeps == []


def test_retries_until_success_with_exponential_delays():
    sleeps = []
    func = Flaky(3)
    result = retry_with_exponential_backoff(func, base_delay=1.0, factor=2.0, sleep=sleeps.append)
    assert result == "ok"
    assert func.calls == 4
    assert sleeps == [1.0, 2.0, 4.0]


def test_delay_is_capped():
    sleeps = []
    retry_with_exponential_backoff(
        Flaky(4), max_attempts=5, base_delay=1.0, factor=10.0, max_delay=50.0, sleep=sleeps.append
    )
    assert sleeps == [1.0, 10.0, 50.0, 50.0]


def test_reraises_last_error_when_exhausted():
    sleeps = []
    func = Flaky(10)
    with pytest.raises(ConnectionError, match="failure 3"):
        retry_with_exponential_backoff(func, max_attempts=3, sleep=sleeps.append)
    assert func.calls == 3
    assert len(sleeps) == 2


def test_non_retryable_errors_propagate_immediately():
    sleeps = []
    func = Flaky(1, error=KeyError)
    with pytest.raises(KeyError):
        retry_with_exponential_backoff(func, retry_on=(ConnectionError,), sleep=sleeps.append)
    assert func.calls == 1
    assert sleeps == []


def test_single_attempt_never_sleeps():
    sleeps = []
    with pytest.raises(ConnectionError):
        retry_with_exponential_backoff(Flaky(1), max_attempts=1, sleep=sleeps.append)
    assert sleeps == []


def test_invalid_max_attempts():
    with pytest.raises(ValueError):
        retry_with_exponential_backoff(lambda: 1, max_attempts=0, sleep=lambda s: None)


def test_returns_none_results():
    assert retry_with_exponential_backoff(lambda: None, sleep=lambda s: None) is None
