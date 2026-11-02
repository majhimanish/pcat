import os
from typing import Any


class SettingsError(ValueError):
    """Raised when one or more environment settings are invalid."""


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def load_settings(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Load and validate application settings from environment variables.

    Reads from `env` if given, otherwise from os.environ. Missing or empty
    variables fall back to defaults. All validation errors are collected and
    raised together as a single SettingsError.

    Variables:
        APP_ENV        str   one of: development, staging, production (default: development)
        APP_HOST       str   non-empty hostname/IP                    (default: 127.0.0.1)
        APP_PORT       int   1-65535                                  (default: 8000)
        APP_DEBUG      bool  1/0, true/false, yes/no, on/off          (default: false)
        APP_TIMEOUT    float seconds, > 0                             (default: 30.0)
        APP_WORKERS    int   >= 1                                     (default: 4)
        APP_LOG_LEVEL  str   DEBUG, INFO, WARNING, ERROR, CRITICAL    (default: INFO)
        DATABASE_URL   str   required when APP_ENV=production         (default: sqlite:///app.db)
        SECRET_KEY     str   required when APP_ENV=production, min 16 chars (default: None)
    """
    source = os.environ if env is None else env
    errors: list[str] = []

    def get(name: str, default: Any, cast=str, check=None, message: str = "") -> Any:
        raw = source.get(name)
        if raw is None or raw.strip() == "":
            return default
        try:
            value = cast(raw.strip())
        except (TypeError, ValueError) as exc:
            errors.append(f"{name}: invalid value {raw!r} ({exc})")
            return default
        if check is not None and not check(value):
            errors.append(f"{name}: invalid value {raw!r} ({message})")
            return default
        return value

    app_env = get(
        "APP_ENV", "development", str.lower,
        lambda v: v in {"development", "staging", "production"},
        "must be one of development, staging, production",
    )
    settings: dict[str, Any] = {
        "app_env": app_env,
        "host": get("APP_HOST", "127.0.0.1"),
        "port": get("APP_PORT", 8000, int, lambda v: 1 <= v <= 65535, "must be 1-65535"),
        "debug": get("APP_DEBUG", False, _parse_bool),
        "timeout": get("APP_TIMEOUT", 30.0, float, lambda v: 0 < v < float("inf"), "must be a positive finite number"),
        "workers": get("APP_WORKERS", 4, int, lambda v: v >= 1, "must be >= 1"),
        "log_level": get(
            "APP_LOG_LEVEL", "INFO", str.upper,
            lambda v: v in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
            "must be DEBUG, INFO, WARNING, ERROR or CRITICAL",
        ),
        "database_url": get("DATABASE_URL", None),
        "secret_key": get("SECRET_KEY", None),
    }

    if app_env == "production":
        if settings["database_url"] is None:
            errors.append("DATABASE_URL: required when APP_ENV=production")
        if settings["secret_key"] is None:
            errors.append("SECRET_KEY: required when APP_ENV=production")
        if settings["debug"]:
            errors.append("APP_DEBUG: must not be enabled when APP_ENV=production")
    if settings["secret_key"] is not None and len(settings["secret_key"]) < 16:
        errors.append("SECRET_KEY: must be at least 16 characters")
    if settings["database_url"] is None:
        settings["database_url"] = "sqlite:///app.db"

    if errors:
        raise SettingsError("Invalid settings:\n  - " + "\n  - ".join(errors))

    return settings
