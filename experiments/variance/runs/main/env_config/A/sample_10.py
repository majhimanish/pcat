import os
from typing import Any, Callable, Dict, Optional


class ConfigError(ValueError):
    """Raised when one or more settings fail validation."""


def _parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def load_settings(env: Optional[Dict[str, str]] = None, prefix: str = "APP_") -> Dict[str, Any]:
    """Load and validate settings from environment variables.

    Each setting is read from ``<prefix><NAME>``. Missing or empty variables
    fall back to defaults. All validation errors are collected and raised
    together as a single ConfigError.

    Args:
        env: Mapping to read from (defaults to os.environ).
        prefix: Prefix applied to every variable name.

    Returns:
        A dict of validated settings.
    """
    env = os.environ if env is None else env

    def in_range(lo: float, hi: float) -> Callable[[Any], bool]:
        return lambda x: lo <= x <= hi

    def one_of(*choices: str) -> Callable[[Any], bool]:
        return lambda x: x in choices

    # name: (default, converter, validator, description of constraint)
    schema = {
        "DEBUG": (False, _parse_bool, None, "a boolean"),
        "HOST": ("127.0.0.1", str, lambda x: bool(x.strip()), "a non-empty string"),
        "PORT": (8000, int, in_range(1, 65535), "an integer between 1 and 65535"),
        "WORKERS": (4, int, in_range(1, 256), "an integer between 1 and 256"),
        "TIMEOUT": (30.0, float, lambda x: x > 0, "a positive number"),
        "LOG_LEVEL": (
            "INFO",
            lambda s: s.strip().upper(),
            one_of("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
            "one of DEBUG, INFO, WARNING, ERROR, CRITICAL",
        ),
        "ENVIRONMENT": (
            "development",
            lambda s: s.strip().lower(),
            one_of("development", "staging", "production"),
            "one of development, staging, production",
        ),
    }

    settings: Dict[str, Any] = {}
    errors = []

    for name, (default, convert, validate, constraint) in schema.items():
        key = f"{prefix}{name}"
        raw = env.get(key)

        if raw is None or raw.strip() == "":
            settings[name.lower()] = default
            continue

        try:
            value = convert(raw)
        except (ValueError, TypeError):
            errors.append(f"{key}={raw!r} is invalid: expected {constraint}")
            continue

        if validate is not None and not validate(value):
            errors.append(f"{key}={raw!r} is invalid: expected {constraint}")
            continue

        settings[name.lower()] = value

    if errors:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return settings
