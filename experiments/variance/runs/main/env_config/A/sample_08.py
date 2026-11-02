import os
from typing import Any, Callable, Dict, Optional


class ConfigError(ValueError):
    """Raised when one or more environment settings are invalid."""


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def _parse_int(value: str) -> int:
    return int(value.strip())


def _parse_float(value: str) -> float:
    return float(value.strip())


def _parse_str(value: str) -> str:
    return value.strip()


def _parse_list(value: str) -> list:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_settings(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Load and validate application settings from environment variables.

    Each setting is defined by: (env var name, parser, default, validator).
    A default of None marks the setting as required.
    Raises ConfigError listing every problem found, not just the first.
    """
    env = os.environ if env is None else env

    def in_range(low: float, high: float) -> Callable[[Any], bool]:
        return lambda v: low <= v <= high

    def one_of(*choices: str) -> Callable[[Any], bool]:
        return lambda v: v in choices

    def non_empty(v: Any) -> bool:
        return bool(v)

    # key: (env var, parser, default, validator, validation error message)
    schema = {
        "app_name": ("APP_NAME", _parse_str, "my-app", non_empty,
                     "must not be empty"),
        "environment": ("APP_ENV", _parse_str, "development",
                        one_of("development", "staging", "production"),
                        "must be one of: development, staging, production"),
        "debug": ("DEBUG", _parse_bool, False, None, ""),
        "host": ("HOST", _parse_str, "127.0.0.1", non_empty,
                 "must not be empty"),
        "port": ("PORT", _parse_int, 8000, in_range(1, 65535),
                 "must be between 1 and 65535"),
        "log_level": ("LOG_LEVEL", _parse_str, "INFO",
                      one_of("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
                      "must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"),
        "request_timeout": ("REQUEST_TIMEOUT", _parse_float, 30.0,
                            lambda v: v > 0, "must be greater than 0"),
        "max_workers": ("MAX_WORKERS", _parse_int, 4, in_range(1, 256),
                        "must be between 1 and 256"),
        "allowed_hosts": ("ALLOWED_HOSTS", _parse_list, ["localhost"], None, ""),
        "database_url": ("DATABASE_URL", _parse_str, None, non_empty,
                         "must not be empty"),
    }

    settings: Dict[str, Any] = {}
    errors = []

    for key, (var, parser, default, validator, message) in schema.items():
        raw = env.get(var)

        if raw is None or raw.strip() == "":
            if default is None:
                errors.append(f"{var}: required but not set")
                continue
            settings[key] = default
            continue

        try:
            value = parser(raw)
        except (ValueError, TypeError) as exc:
            errors.append(f"{var}: invalid value {raw!r} ({exc})")
            continue

        if validator is not None and not validator(value):
            errors.append(f"{var}: invalid value {raw!r} ({message})")
            continue

        settings[key] = value

    # Cross-field validation
    if (
        settings.get("environment") == "production"
        and settings.get("debug") is True
    ):
        errors.append("DEBUG: must not be enabled when APP_ENV=production")

    if errors:
        raise ConfigError(
            "Invalid configuration:\n  - " + "\n  - ".join(errors)
        )

    return settings
