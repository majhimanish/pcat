import os
from typing import Any, Callable, Dict, Optional


class ConfigError(ValueError):
    """Raised when one or more settings are missing or invalid."""


def _parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def _parse_int_in_range(low: int, high: int) -> Callable[[str], int]:
    def parse(value: str) -> int:
        n = int(value.strip())
        if not low <= n <= high:
            raise ValueError(f"{n} is outside the allowed range {low}-{high}")
        return n
    return parse


def _parse_choice(choices: tuple) -> Callable[[str], str]:
    def parse(value: str) -> str:
        v = value.strip().upper()
        if v not in choices:
            raise ValueError(f"{value!r} is not one of {', '.join(choices)}")
        return v
    return parse


def _parse_nonempty(value: str) -> str:
    v = value.strip()
    if not v:
        raise ValueError("value must not be empty")
    return v


def load_settings(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Load and validate application settings from environment variables.

    Each setting has a parser (which also validates), a default, and a
    flag indicating whether it is required. All problems are collected and
    reported together in a single ConfigError.

    Args:
        env: Optional mapping to read from instead of os.environ (useful in tests).

    Returns:
        A dict of validated, correctly typed settings.

    Raises:
        ConfigError: If any required setting is missing or any value is invalid.
    """
    source = os.environ if env is None else env

    # name: (parser, default, required)
    spec = {
        "APP_NAME": (_parse_nonempty, "myapp", False),
        "APP_HOST": (_parse_nonempty, "127.0.0.1", False),
        "APP_PORT": (_parse_int_in_range(1, 65535), 8000, False),
        "APP_DEBUG": (_parse_bool, False, False),
        "APP_LOG_LEVEL": (
            _parse_choice(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")),
            "INFO",
            False,
        ),
        "APP_WORKERS": (_parse_int_in_range(1, 256), 4, False),
        "APP_TIMEOUT_SECONDS": (float, 30.0, False),
        "DATABASE_URL": (_parse_nonempty, None, True),
    }

    settings: Dict[str, Any] = {}
    errors = []

    for name, (parser, default, required) in spec.items():
        raw = source.get(name)

        if raw is None or raw.strip() == "":
            if required:
                errors.append(f"{name}: required but not set")
            else:
                settings[name] = default
            continue

        try:
            settings[name] = parser(raw)
        except (ValueError, TypeError) as exc:
            errors.append(f"{name}: {exc}")

    # Cross-field validation
    timeout = settings.get("APP_TIMEOUT_SECONDS")
    if isinstance(timeout, float) and timeout <= 0:
        errors.append("APP_TIMEOUT_SECONDS: must be greater than 0")

    if errors:
        raise ConfigError("Invalid configuration:\n  " + "\n  ".join(errors))

    return settings
