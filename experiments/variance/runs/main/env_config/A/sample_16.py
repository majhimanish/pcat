import os
from typing import Any, Callable, Dict, Optional


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def _parse_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError(f"port must be between 1 and 65535, got {port}")
    return port


def _parse_positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError(f"must be a positive integer, got {number}")
    return number


def _parse_log_level(value: str) -> str:
    level = value.strip().upper()
    allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if level not in allowed:
        raise ValueError(f"must be one of {sorted(allowed)}, got {value!r}")
    return level


def _parse_str(value: str) -> str:
    return value.strip()


def _parse_non_empty_str(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be empty")
    return value


# name -> (env var, parser, default, required)
_SETTINGS_SPEC: Dict[str, tuple] = {
    "app_name": ("APP_NAME", _parse_non_empty_str, "my-app", False),
    "host": ("APP_HOST", _parse_non_empty_str, "127.0.0.1", False),
    "port": ("APP_PORT", _parse_port, 8000, False),
    "debug": ("APP_DEBUG", _parse_bool, False, False),
    "log_level": ("APP_LOG_LEVEL", _parse_log_level, "INFO", False),
    "workers": ("APP_WORKERS", _parse_positive_int, 4, False),
    "database_url": ("DATABASE_URL", _parse_non_empty_str, None, True),
}


def load_settings(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Load settings from environment variables, applying defaults and validation.

    Args:
        env: Optional mapping to read from instead of os.environ (useful for tests).

    Returns:
        A dict of validated settings.

    Raises:
        ValueError: If any setting is missing (when required) or invalid. All
            problems are collected and reported together.
    """
    source = os.environ if env is None else env
    settings: Dict[str, Any] = {}
    errors = []

    for name, (env_var, parser, default, required) in _SETTINGS_SPEC.items():
        raw = source.get(env_var)

        if raw is None or raw.strip() == "":
            if required:
                errors.append(f"{env_var}: required but not set")
            else:
                settings[name] = default
            continue

        try:
            settings[name] = parser(raw)
        except ValueError as exc:
            errors.append(f"{env_var}: {exc}")

    if errors:
        raise ValueError("Invalid configuration:\n  " + "\n  ".join(errors))

    return settings
