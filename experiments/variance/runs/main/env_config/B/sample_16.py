import os
from typing import Any, Mapping, Optional

_VALID_ENVS = {"development", "staging", "production", "test"}
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {raw!r}")


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


def load_config(env: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    """Load application configuration from environment variables.

    Applies defaults for optional settings and validates all values.
    Raises ValueError listing every problem found.

    Environment variables:
        APP_ENV          one of development/staging/production/test (default: development)
        APP_HOST         bind host (default: 127.0.0.1)
        APP_PORT         port, 1-65535 (default: 8000)
        APP_DEBUG        boolean (default: false; must be false in production)
        APP_LOG_LEVEL    DEBUG/INFO/WARNING/ERROR/CRITICAL (default: INFO)
        APP_WORKERS      integer >= 1 (default: 1)
        APP_TIMEOUT      request timeout in seconds, >= 1 (default: 30)
        DATABASE_URL     required
        SECRET_KEY       required; >= 16 characters
    """
    source = os.environ if env is None else env
    errors: list[str] = []
    config: dict[str, Any] = {}

    def get(name: str, default: Optional[str] = None) -> Optional[str]:
        raw = source.get(name)
        if raw is None or raw.strip() == "":
            return default
        return raw

    def collect(name: str, parser, default: Optional[str], *args, **kwargs):
        raw = get(name, default)
        if raw is None:
            errors.append(f"{name} is required but not set")
            return None
        try:
            return parser(name, raw, *args, **kwargs)
        except ValueError as exc:
            errors.append(str(exc))
            return None

    # Environment name
    app_env = (get("APP_ENV", "development") or "").strip().lower()
    if app_env not in _VALID_ENVS:
        errors.append(
            f"APP_ENV must be one of {sorted(_VALID_ENVS)}, got {app_env!r}"
        )
    config["env"] = app_env

    # Host
    config["host"] = (get("APP_HOST", "127.0.0.1") or "").strip()

    # Numeric / boolean settings
    config["port"] = collect("APP_PORT", _parse_int, "8000", minimum=1, maximum=65535)
    config["debug"] = collect("APP_DEBUG", _parse_bool, "false")
    config["workers"] = collect("APP_WORKERS", _parse_int, "1", minimum=1)
    config["timeout"] = collect("APP_TIMEOUT", _parse_int, "30", minimum=1)

    # Log level
    log_level = (get("APP_LOG_LEVEL", "INFO") or "").strip().upper()
    if log_level not in _VALID_LOG_LEVELS:
        errors.append(
            f"APP_LOG_LEVEL must be one of {sorted(_VALID_LOG_LEVELS)}, got {log_level!r}"
        )
    config["log_level"] = log_level

    # Required settings
    database_url = get("DATABASE_URL")
    if database_url is None:
        errors.append("DATABASE_URL is required but not set")
    config["database_url"] = database_url.strip() if database_url else None

    secret_key = get("SECRET_KEY")
    if secret_key is None:
        errors.append("SECRET_KEY is required but not set")
    elif len(secret_key) < 16:
        errors.append("SECRET_KEY must be at least 16 characters long")
    config["secret_key"] = secret_key

    # Cross-field validation
    if app_env == "production" and config["debug"] is True:
        errors.append("APP_DEBUG must be false when APP_ENV is production")

    if errors:
        raise ValueError(
            "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return config
