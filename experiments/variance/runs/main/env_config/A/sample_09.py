import os
from typing import Any


class SettingsError(ValueError):
    """Raised when one or more environment settings are invalid."""


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}


def _parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(f"expected a boolean (true/false), got {raw!r}")


def _parse_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_settings(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Load and validate application settings from environment variables.

    Reads from `env` (defaults to os.environ), applies defaults for missing
    or empty values, converts types, and validates ranges/choices. All
    problems are collected and raised together as a SettingsError.

    Recognized variables:
        APP_ENV          str   one of: development, staging, production
                               (default: development)
        APP_HOST         str   non-empty hostname/IP (default: 127.0.0.1)
        APP_PORT         int   1-65535 (default: 8000)
        APP_DEBUG        bool  (default: False; must be False in production)
        APP_TIMEOUT      float seconds, > 0 (default: 30.0)
        APP_WORKERS      int   >= 1 (default: 4)
        APP_LOG_LEVEL    str   DEBUG/INFO/WARNING/ERROR/CRITICAL (default: INFO)
        APP_ALLOWED_HOSTS list comma-separated (default: ["localhost"])
        APP_SECRET_KEY   str   required in production, min 16 chars
                               (default: None outside production)
    """
    source = os.environ if env is None else env
    errors: list[str] = []
    settings: dict[str, Any] = {}

    def get(name: str) -> str | None:
        raw = source.get(name)
        if raw is None or raw.strip() == "":
            return None
        return raw.strip()

    def read(name: str, default: Any, parser, validator=None, message: str = ""):
        raw = get(name)
        if raw is None:
            return default
        try:
            value = parser(raw)
        except (ValueError, TypeError) as exc:
            errors.append(f"{name}: {exc}")
            return default
        if validator is not None and not validator(value):
            errors.append(f"{name}: {message} (got {value!r})")
            return default
        return value

    settings["env"] = read(
        "APP_ENV", "development", str.lower,
        lambda v: v in {"development", "staging", "production"},
        "must be one of development, staging, production",
    )
    settings["host"] = read("APP_HOST", "127.0.0.1", str)
    settings["port"] = read(
        "APP_PORT", 8000, int,
        lambda v: 1 <= v <= 65535, "must be between 1 and 65535",
    )
    settings["debug"] = read("APP_DEBUG", False, _parse_bool)
    settings["timeout"] = read(
        "APP_TIMEOUT", 30.0, float,
        lambda v: v > 0 and v != float("inf"), "must be a positive, finite number",
    )
    settings["workers"] = read(
        "APP_WORKERS", 4, int, lambda v: v >= 1, "must be >= 1",
    )
    settings["log_level"] = read(
        "APP_LOG_LEVEL", "INFO", str.upper,
        lambda v: v in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
        "must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    settings["allowed_hosts"] = read(
        "APP_ALLOWED_HOSTS", ["localhost"], _parse_list,
        lambda v: len(v) > 0, "must contain at least one host",
    )
    settings["secret_key"] = read(
        "APP_SECRET_KEY", None, str,
        lambda v: len(v) >= 16, "must be at least 16 characters",
    )

    # Cross-field validation
    if settings["env"] == "production":
        if settings["debug"]:
            errors.append("APP_DEBUG: must be false in production")
        if get("APP_SECRET_KEY") is None:
            errors.append("APP_SECRET_KEY: required in production")

    if errors:
        raise SettingsError(
            "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return settings
