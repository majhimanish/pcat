"""Retry a callable with capped exponential backoff and an injectable sleep."""

import time
from collections.abc import Callable
from typing import Any


def retry_with_exponential_backoff(
    func: Callable[[], Any],
    *,
    max_attempts: int = 5,
    base_delay: float = 0.1,
    factor: float = 2.0,
    max_delay: float = 10.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], Any] = time.sleep,
) -> Any:
    """Return func() once it succeeds.

    Attempt n (0-based) that fails with an exception in `retry_on` is followed by
    sleep(min(max_delay, base_delay * factor ** n)). After `max_attempts` failed
    attempts the last exception is re-raised. Other exceptions propagate at once.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    attempt = 0
    while True:
        try:
            return func()
        except retry_on:
            attempt += 1
            if attempt >= max_attempts:
                raise
            sleep(min(max_delay, base_delay * factor ** (attempt - 1)))
