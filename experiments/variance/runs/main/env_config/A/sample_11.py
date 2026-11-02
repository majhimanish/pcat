import os
from typing import Any


class ConfigError(ValueError):
    """Raised when environment configuration is invalid."""


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}

_VALID_ENVIRONMENTS = {"development", "staging", "production", "test"}
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(f"{name} must be a boolean (true/false), got {raw!r}")


def _parse_int(name: str, raw: str, minimum: int | None = None,
               maximum: int | None = None) -> int:
    try:
        value = int(raw.strip())
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name} must be <= {maximum}, got {value}")
    return value


def _parse_float(name: str, raw: str, minimum: float | None = None) -> float:
    try:
        value = float(raw.strip())
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise ConfigError(f"{name} must be a finite number, got {raw!r}")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    return value


def _parse_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_settings(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Load and validate application settings from environment variables.

    Variables (defaults in parentheses):
        APP_ENV          one of development/staging/production/test (development)
        DEBUG            boolean (false; forced false-checked in production)
        HOST             string (127.0.0.1)
        PORT             integer 1-65535 (8000)
        LOG_LEVEL        DEBUG/INFO/WARNING/ERROR/CRITICAL (INFO)
        WORKERS          integer >= 1 (4)
        REQUEST_TIMEOUT  float seconds > 0 (30.0)
        ALLOWED_HOSTS    comma-separated list (localhost)
        DATABASE_URL     string, required in production (sqlite:///app.db otherwise)
        SECRET_KEY       string, required in production, min 16 chars

    Args:
        env: Mapping to read from; defaults to os.environ (useful for tests).

    Returns:
        A dict of validated settings.

    Raises:
        ConfigError: listing every problem found, not just the first.
    """
    source = os.environ if env is None else env
    errors: list[str] = []
    settings: dict[str, Any] = {}

    def get(name: str, default: str | None = None) -> str | None:
        raw = source.get(name)
        if raw is None or raw.strip() == "":
            return default
        return raw

    def collect(name: str, parser, default: Any, *args, **kwargs) -> None:
        raw = get(name)
        if raw is None:
            settings[name.lower()] = default
            return
        try:
            settings[name.lower()] = parser(name, raw, *args, **kwargs)
        except ConfigError as exc:
            errors.append(str(exc))

    # Environment name
    app_env = (get("APP_ENV", "development") or "").strip().lower()
    if app_env not in _VALID_ENVIRONMENTS:
        errors.append(
            f"APP_ENV must be one of {sorted(_VALID_ENVIRONMENTS)}, got {app_env!r}"
        )
    settings["app_env"] = app_env
    is_prod = app_env == "production"

    collect("DEBUG", _parse_bool, False)
    collect("PORT", _parse_int, 8000, minimum=1, maximum=65535)
    collect("WORKERS", _parse_int, 4, minimum=1)
    collect("REQUEST_TIMEOUT", _parse_float, 30.0, minimum=0.001)

    settings["host"] = (get("HOST", "127.0.0.1") or "").strip()

    log_level = (get("LOG_LEVEL", "INFO") or "").strip().upper()
    if log_level not in _VALID_LOG_LEVELS:
        errors.append(
            f"LOG_LEVEL must be one of {sorted(_VALID_LOG_LEVELS)}, got {log_level!r}"
        )
    settings["log_level"] = log_level

    allowed_hosts = _parse_list(get("ALLOWED_HOSTS", "localhost") or "")
    if not allowed_hosts:
        errors.append("ALLOWED_HOSTS must contain at least one host")
    settings["allowed_hosts"] = allowed_hosts

    # Secrets / required-in-production values
    database_url = get("DATABASE_URL")
    if database_url is None:
        if is_prod:
            errors.append("DATABASE_URL is required when APP_ENV=production")
        database_url = "sqlite:///app.db"
    settings["database_url"] = database_url.strip()

    secret_key = get("SECRET_KEY")
    if secret_key is None:
        if is_prod:
            errors.append("SECRET_KEY is required when APP_ENV=production")
        secret_key = "dev-insecure-key-change-me"
    elif len(secret_key) < 16:
        errors.append("SECRET_KEY must be at least 16 characters")
    settings["secret_key"] = secret_key

    # Cross-field rules
    if is_prod and settings.get("debug") is True:
        errors.append("DEBUG must not be enabled when APP_ENV=production")

    if errors:
        raise ConfigError(
            "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return settings
