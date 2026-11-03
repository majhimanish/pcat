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


def _parse_choice(name: str, raw: str, choices: tuple, case: str = "lower") -> str:
    value = raw.strip()
    value = value.upper() if case == "upper" else value.lower()
    if value not in choices:
        raise ValueError(f"{name} must be one of {', '.join(choices)}, got {raw!r}")
    return value


def load_settings(env: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    """Load application settings from environment variables.

    Applies defaults for optional settings, converts values to their proper
    types, and validates them. All problems are collected and reported together
    in a single ValueError.

    Environment variables:
        APP_ENV          one of development/staging/production/test (default: development)
        APP_DEBUG        boolean (default: false)
        APP_HOST         string (default: 127.0.0.1)
        APP_PORT         integer 1-65535 (default: 8000)
        APP_LOG_LEVEL    DEBUG/INFO/WARNING/ERROR/CRITICAL (default: INFO)
        DATABASE_URL     string (default: sqlite:///app.db)
    """
    source = os.environ if env is None else env
    errors: list[str] = []
    settings: dict[str, Any] = {}

    def get(name: str) -> Optional[str]:
        raw = source.get(name)
        if raw is None or raw.strip() == "":
            return None
        return raw

    def load(name: str, default: Any, parser) -> None:
        key = name.lower()
        raw = get(name)
        if raw is None:
            settings[key] = default
            return
        try:
            settings[key] = parser(name, raw)
        except ValueError as exc:
            errors.append(str(exc))

    load("APP_ENV", "development", lambda n, r: _parse_choice(n, r, _ENVIRONMENTS))
    load("APP_DEBUG", False, _parse_bool)
    load("APP_HOST", "127.0.0.1", lambda n, r: r.strip())
    load("APP_PORT", 8000, lambda n, r: _parse_int(n, r, 1, 65535))
    load(
        "APP_LOG_LEVEL",
        "INFO",
        lambda n, r: _parse_choice(n, r, _LOG_LEVELS, case="upper"),
    )
    load("DATABASE_URL", "sqlite:///app.db", lambda n, r: r.strip())

    if settings.get("app_env") == "production" and settings.get("app_debug"):
        errors.append("APP_DEBUG must not be enabled when APP_ENV is production")

    if errors:
        raise ValueError(
            "Invalid settings:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return settings
