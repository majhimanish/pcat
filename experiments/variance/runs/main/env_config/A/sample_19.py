import os
from typing import Any, Callable, Optional


class ConfigError(ValueError):
    """Raised when one or more environment settings are invalid."""


def _parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def _parse_log_level(value: str) -> str:
    level = value.strip().upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError(f"unknown log level {value!r}")
    return level


def _parse_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError(f"port {port} out of range 1-65535")
    return port


def _parse_positive_int(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise ValueError(f"{n} must be positive")
    return n


def _parse_positive_float(value: str) -> float:
    x = float(value)
    if x <= 0:
        raise ValueError(f"{x} must be positive")
    return x


def _parse_str_list(value: str) -> list:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_nonempty_str(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be empty")
    return value


# name -> (parser, default, required)
_SCHEMA = {
    "APP_NAME": (_parse_nonempty_str, "myapp", False),
    "APP_ENV": (_parse_nonempty_str, "development", False),
    "DEBUG": (_parse_bool, False, False),
    "HOST": (_parse_nonempty_str, "127.0.0.1", False),
    "PORT": (_parse_port, 8000, False),
    "LOG_LEVEL": (_parse_log_level, "INFO", False),
    "WORKERS": (_parse_positive_int, 4, False),
    "TIMEOUT_SECONDS": (_parse_positive_float, 30.0, False),
    "ALLOWED_HOSTS": (_parse_str_list, ["localhost"], False),
    "DATABASE_URL": (_parse_nonempty_str, "sqlite:///app.db", False),
    "SECRET_KEY": (_parse_nonempty_str, None, False),
}


def load_settings(
    env: Optional[dict] = None,
    prefix: str = "",
    require_secret_in_production: bool = True,
) -> dict:
    """Load and validate settings from environment variables.

    Unset or empty variables fall back to defaults. All problems are
    collected and reported together in a single ConfigError.

    Args:
        env: Mapping to read from (defaults to os.environ).
        prefix: Optional prefix for variable names, e.g. "MYAPP_".
        require_secret_in_production: Require SECRET_KEY when APP_ENV is
            "production".

    Returns:
        A dict of validated settings keyed by lowercase name.
    """
    source = os.environ if env is None else env
    settings: dict = {}
    errors: list = []

    for name, (parser, default, required) in _SCHEMA.items():
        raw = source.get(prefix + name)
        if raw is None or raw.strip() == "":
            if required:
                errors.append(f"{prefix}{name} is required but not set")
                continue
            value: Any = list(default) if isinstance(default, list) else default
        else:
            try:
                value = parser(raw)
            except ValueError as exc:
                errors.append(f"{prefix}{name}: {exc}")
                continue
        settings[name.lower()] = value

    if (
        require_secret_in_production
        and settings.get("app_env", "").lower() == "production"
        and not settings.get("secret_key")
    ):
        errors.append(f"{prefix}SECRET_KEY is required when APP_ENV is 'production'")

    if errors:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return settings
