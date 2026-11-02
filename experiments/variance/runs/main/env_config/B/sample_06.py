import os
from typing import Any, Mapping, Optional


class ConfigError(ValueError):
    """Raised when one or more configuration values are invalid."""


_VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_VALID_ENVIRONMENTS = ("development", "staging", "production", "test")
_TRUE_VALUES = ("1", "true", "yes", "on")
_FALSE_VALUES = ("0", "false", "no", "off")


def _parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(
        f"{name} must be a boolean (one of {_TRUE_VALUES + _FALSE_VALUES}), got {raw!r}"
    )


def _parse_int(name: str, raw: str, minimum: Optional[int], maximum: Optional[int]) -> int:
    try:
        value = int(raw.strip())
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name} must be <= {maximum}, got {value}")
    return value


def _parse_float(name: str, raw: str, minimum: Optional[float]) -> float:
    try:
        value = float(raw.strip())
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise ConfigError(f"{name} must be a finite number, got {raw!r}")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    return value


def load_config(env: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    """Load configuration from environment variables.

    Applies defaults for optional settings, converts values to their proper
    types, and validates them. All problems are collected and reported together
    in a single ConfigError.

    Environment variables:
        APP_ENV          One of development/staging/production/test (default: development)
        APP_DEBUG        Boolean (default: false; must be false in production)
        APP_HOST         Host to bind to (default: 127.0.0.1)
        APP_PORT         Integer 1-65535 (default: 8000)
        APP_LOG_LEVEL    DEBUG/INFO/WARNING/ERROR/CRITICAL (default: INFO)
        APP_WORKERS      Integer >= 1 (default: 1)
        APP_TIMEOUT      Float seconds > 0 (default: 30.0)
        DATABASE_URL     Required, non-empty
        SECRET_KEY       Required, at least 16 characters
    """
    source = os.environ if env is None else env
    errors: list[str] = []
    config: dict[str, Any] = {}

    def get(name: str) -> Optional[str]:
        raw = source.get(name)
        if raw is None or raw.strip() == "":
            return None
        return raw

    def collect(name: str, default: Any, parser) -> None:
        raw = get(name)
        if raw is None:
            config[name] = default
            return
        try:
            config[name] = parser(raw)
        except ConfigError as exc:
            errors.append(str(exc))

    # Optional settings with defaults
    raw_env = get("APP_ENV")
    app_env = (raw_env or "development").strip().lower()
    if app_env not in _VALID_ENVIRONMENTS:
        errors.append(f"APP_ENV must be one of {_VALID_ENVIRONMENTS}, got {raw_env!r}")
    config["APP_ENV"] = app_env

    collect("APP_DEBUG", False, lambda r: _parse_bool("APP_DEBUG", r))
    collect("APP_HOST", "127.0.0.1", lambda r: r.strip())
    collect("APP_PORT", 8000, lambda r: _parse_int("APP_PORT", r, 1, 65535))
    collect("APP_WORKERS", 1, lambda r: _parse_int("APP_WORKERS", r, 1, None))

    raw_timeout = get("APP_TIMEOUT")
    if raw_timeout is None:
        config["APP_TIMEOUT"] = 30.0
    else:
        try:
            timeout = _parse_float("APP_TIMEOUT", raw_timeout, 0.0)
            if timeout <= 0:
                raise ConfigError(f"APP_TIMEOUT must be > 0, got {timeout}")
            config["APP_TIMEOUT"] = timeout
        except ConfigError as exc:
            errors.append(str(exc))

    raw_level = get("APP_LOG_LEVEL")
    log_level = (raw_level or "INFO").strip().upper()
    if log_level not in _VALID_LOG_LEVELS:
        errors.append(f"APP_LOG_LEVEL must be one of {_VALID_LOG_LEVELS}, got {raw_level!r}")
    config["APP_LOG_LEVEL"] = log_level

    # Required settings
    database_url = get("DATABASE_URL")
    if database_url is None:
        errors.append("DATABASE_URL is required but not set")
    else:
        config["DATABASE_URL"] = database_url.strip()

    secret_key = get("SECRET_KEY")
    if secret_key is None:
        errors.append("SECRET_KEY is required but not set")
    elif len(secret_key) < 16:
        errors.append("SECRET_KEY must be at least 16 characters long")
    else:
        config["SECRET_KEY"] = secret_key

    # Cross-field validation
    if app_env == "production" and config.get("APP_DEBUG") is True:
        errors.append("APP_DEBUG must not be enabled when APP_ENV is 'production'")

    if errors:
        details = "\n  - ".join(errors)
        raise ConfigError(f"Invalid configuration:\n  - {details}")

    return config
