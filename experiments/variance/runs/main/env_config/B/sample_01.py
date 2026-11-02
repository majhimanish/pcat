import os
from typing import Any, Mapping, Optional

_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_ENVIRONMENTS = ("development", "staging", "production", "test")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(
        f"{name} must be a boolean (true/false, 1/0, yes/no, on/off), got {raw!r}"
    )


def _parse_int(
    name: str,
    raw: str,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}, got {value}")
    return value


def _parse_float(name: str, raw: str, minimum: Optional[float] = None) -> float:
    try:
        value = float(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be a finite number, got {raw!r}")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _parse_choice(name: str, raw: str, choices: tuple, case: str = "lower") -> str:
    value = raw.strip()
    value = value.upper() if case == "upper" else value.lower()
    if value not in choices:
        raise ValueError(f"{name} must be one of {', '.join(choices)}, got {raw!r}")
    return value


def load_config(env: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    """Load app configuration from environment variables.

    Applies defaults for optional settings, converts values to their proper
    types, and validates them. All problems are collected and reported together
    in a single ValueError.

    Environment variables:
        APP_ENV          one of development/staging/production/test (default: development)
        APP_DEBUG        boolean (default: false)
        APP_HOST         string (default: 127.0.0.1)
        APP_PORT         integer 1-65535 (default: 8000)
        APP_LOG_LEVEL    DEBUG/INFO/WARNING/ERROR/CRITICAL (default: INFO)
        APP_TIMEOUT      float seconds > 0 (default: 30.0)
        APP_MAX_WORKERS  integer >= 1 (default: 4)
        DATABASE_URL     string (required)
        SECRET_KEY       string, min 16 chars (required)
    """
    source = os.environ if env is None else env
    errors: list[str] = []
    config: dict[str, Any] = {}

    def get(name: str) -> Optional[str]:
        raw = source.get(name)
        if raw is None or raw.strip() == "":
            return None
        return raw

    def load(name: str, default: Any, parser) -> None:
        key = name.lower()
        raw = get(name)
        if raw is None:
            config[key] = default
            return
        try:
            config[key] = parser(name, raw)
        except ValueError as exc:
            errors.append(str(exc))

    def require(name: str, validator=None) -> None:
        key = name.lower()
        raw = get(name)
        if raw is None:
            errors.append(f"{name} is required but not set")
            return
        value = raw.strip()
        if validator is not None:
            try:
                validator(name, value)
            except ValueError as exc:
                errors.append(str(exc))
                return
        config[key] = value

    def validate_secret(name: str, value: str) -> None:
        if len(value) < 16:
            raise ValueError(f"{name} must be at least 16 characters long")

    load("APP_ENV", "development", lambda n, r: _parse_choice(n, r, _ENVIRONMENTS))
    load("APP_DEBUG", False, _parse_bool)
    load("APP_HOST", "127.0.0.1", lambda n, r: r.strip())
    load("APP_PORT", 8000, lambda n, r: _parse_int(n, r, 1, 65535))
    load(
        "APP_LOG_LEVEL",
        "INFO",
        lambda n, r: _parse_choice(n, r, _LOG_LEVELS, case="upper"),
    )
    load("APP_TIMEOUT", 30.0, lambda n, r: _parse_float(n, r, minimum=0.0))
    load("APP_MAX_WORKERS", 4, lambda n, r: _parse_int(n, r, minimum=1))

    require("DATABASE_URL")
    require("SECRET_KEY", validate_secret)

    if "app_timeout" in config and config["app_timeout"] <= 0:
        errors.append(f"APP_TIMEOUT must be greater than 0, got {config['app_timeout']}")

    if config.get("app_env") == "production" and config.get("app_debug"):
        errors.append("APP_DEBUG must not be enabled when APP_ENV is production")

    if errors:
        raise ValueError(
            "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return config
