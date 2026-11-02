import os
from typing import Any, Callable, Iterable, Optional

_TRUE = {"1", "true", "yes", "y", "on"}
_FALSE = {"0", "false", "no", "n", "off"}
_MISSING = object()


def _parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"expected a boolean (true/false, 1/0, yes/no, on/off), got {raw!r}")


def _parse_list(raw: str) -> list:
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_env(
    name: str,
    default: Any = _MISSING,
    cast: Any = str,
    *,
    choices: Optional[Iterable[Any]] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    validator: Optional[Callable[[Any], bool]] = None,
    environ: Optional[dict] = None,
) -> Any:
    """Read, parse and validate one environment variable.

    Args:
        name: Variable name.
        default: Value used when the variable is unset or empty. If omitted,
            the variable is required and a ValueError is raised when missing.
            The default is returned as-is (not cast), but is still validated.
        cast: One of str, int, float, bool, list, or any callable taking a str.
        choices: Allowed values (after casting).
        min_value / max_value: Inclusive numeric bounds (after casting).
        validator: Extra predicate; must return True for a valid value.
        environ: Mapping to read from (defaults to os.environ); handy for tests.

    Raises:
        ValueError: If the variable is missing and required, cannot be parsed,
            or fails validation. The message always names the variable.
    """
    env = os.environ if environ is None else environ
    raw = env.get(name)

    if raw is None or raw.strip() == "":
        if default is _MISSING:
            raise ValueError(f"{name}: required environment variable is not set")
        value = default
    else:
        try:
            if cast is bool:
                value = _parse_bool(raw)
            elif cast is list:
                value = _parse_list(raw)
            elif cast is str:
                value = raw
            else:
                value = cast(raw.strip())
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{name}: invalid value {raw!r}: {exc}") from exc

    if choices is not None and value not in set(choices):
        raise ValueError(f"{name}: {value!r} is not one of {sorted(choices, key=str)}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{name}: {value!r} is below minimum {min_value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{name}: {value!r} is above maximum {max_value}")
    if validator is not None and not validator(value):
        raise ValueError(f"{name}: {value!r} failed custom validation")

    return value


def load_settings(environ: Optional[dict] = None) -> dict:
    """Example: build an application settings dict with sensible defaults."""
    return {
        "debug": get_env("APP_DEBUG", False, bool, environ=environ),
        "host": get_env("APP_HOST", "127.0.0.1", str, environ=environ),
        "port": get_env("APP_PORT", 8000, int, min_value=1, max_value=65535, environ=environ),
        "log_level": get_env(
            "APP_LOG_LEVEL", "INFO", lambda s: s.upper(),
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], environ=environ,
        ),
        "workers": get_env("APP_WORKERS", 4, int, min_value=1, max_value=64, environ=environ),
        "timeout": get_env("APP_TIMEOUT", 30.0, float, min_value=0, environ=environ),
        "allowed_hosts": get_env("APP_ALLOWED_HOSTS", ["localhost"], list, environ=environ),
        "database_url": get_env("DATABASE_URL", environ=environ),  # required
    }
