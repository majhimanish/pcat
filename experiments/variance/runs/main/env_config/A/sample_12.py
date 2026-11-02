import os
from typing import Any, Callable


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}


def parse_bool(value: str) -> bool:
    """Parse a string into a boolean, raising ValueError if unrecognized."""
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def parse_list(value: str) -> list[str]:
    """Parse a comma-separated string into a list of non-empty, stripped items."""
    return [item.strip() for item in value.split(",") if item.strip()]


def load_settings(env: dict[str, str] | None = None) -> dict[str, Any]:
    """
    Load and validate application settings from environment variables.

    Each setting is defined by: (type parser, default, required, validator).
    Missing or empty variables fall back to the default. Required settings
    without a value raise an error. All problems are collected and reported
    together in a single ValueError.

    Args:
        env: Optional mapping to read from instead of os.environ (useful for tests).

    Returns:
        A dict of validated, correctly typed settings.

    Raises:
        ValueError: If any setting is missing (when required) or invalid.
    """
    env = os.environ if env is None else env

    def in_range(low: int, high: int) -> Callable[[Any], bool]:
        return lambda v: low <= v <= high

    def one_of(*choices: str) -> Callable[[Any], bool]:
        return lambda v: v in choices

    # name: (parser, default, required, validator, validation_message)
    schema: dict[str, tuple[Callable[[str], Any], Any, bool, Callable[[Any], bool] | None, str]] = {
        "APP_ENV": (str, "development", False,
                    one_of("development", "staging", "production"),
                    "must be one of: development, staging, production"),
        "APP_HOST": (str, "127.0.0.1", False, lambda v: bool(v), "must not be empty"),
        "APP_PORT": (int, 8000, False, in_range(1, 65535), "must be between 1 and 65535"),
        "DEBUG": (parse_bool, False, False, None, ""),
        "LOG_LEVEL": (lambda s: s.strip().upper(), "INFO", False,
                      one_of("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
                      "must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"),
        "WORKERS": (int, 4, False, in_range(1, 128), "must be between 1 and 128"),
        "REQUEST_TIMEOUT": (float, 30.0, False, lambda v: v > 0, "must be greater than 0"),
        "ALLOWED_HOSTS": (parse_list, ["localhost"], False, None, ""),
        "DATABASE_URL": (str, None, True,
                         lambda v: "://" in v,
                         "must be a valid URL such as postgresql://user:pass@host/db"),
    }

    settings: dict[str, Any] = {}
    errors: list[str] = []

    for name, (parser, default, required, validator, message) in schema.items():
        raw = env.get(name)

        if raw is None or raw.strip() == "":
            if required:
                errors.append(f"{name}: required but not set")
            else:
                settings[name] = default
            continue

        try:
            value = parser(raw.strip())
        except (ValueError, TypeError) as exc:
            errors.append(f"{name}: invalid value {raw!r} ({exc})")
            continue

        if validator is not None and not validator(value):
            errors.append(f"{name}: invalid value {raw!r}, {message}")
            continue

        settings[name] = value

    if errors:
        raise ValueError("Invalid configuration:\n  " + "\n  ".join(errors))

    return settings
