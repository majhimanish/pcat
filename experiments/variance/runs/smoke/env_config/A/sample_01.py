import os
from typing import Any, Callable, Dict, Optional


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def _parse_list(value: str) -> list:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_settings(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Load and validate application settings from environment variables.

    Each setting is defined by a name, a type parser, a default value
    (or None if required), and an optional validator. All problems are
    collected and reported together in a single ValueError.

    Args:
        env: Optional mapping to read from instead of os.environ
             (useful for testing).

    Returns:
        A dict mapping setting names to validated, typed values.

    Raises:
        ValueError: If any required setting is missing or any value
                    fails parsing or validation.
    """
    source = os.environ if env is None else env

    # name: (parser, default, required, validator, validator_message)
    schema: Dict[str, tuple] = {
        "APP_ENV": (
            str, "development", False,
            lambda v: v in {"development", "staging", "production"},
            "must be one of: development, staging, production",
        ),
        "HOST": (str, "127.0.0.1", False, lambda v: bool(v), "must not be empty"),
        "PORT": (
            int, 8000, False,
            lambda v: 1 <= v <= 65535,
            "must be between 1 and 65535",
        ),
        "DEBUG": (_parse_bool, False, False, None, None),
        "LOG_LEVEL": (
            lambda v: v.strip().upper(), "INFO", False,
            lambda v: v in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
            "must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        ),
        "WORKERS": (
            int, 4, False,
            lambda v: v >= 1,
            "must be at least 1",
        ),
        "REQUEST_TIMEOUT": (
            float, 30.0, False,
            lambda v: v > 0,
            "must be greater than 0",
        ),
        "ALLOWED_HOSTS": (_parse_list, ["localhost"], False, None, None),
        "DATABASE_URL": (
            str, None, True,
            lambda v: "://" in v,
            "must be a valid URL such as postgres://user:pass@host/db",
        ),
        "SECRET_KEY": (
            str, None, True,
            lambda v: len(v) >= 16,
            "must be at least 16 characters",
        ),
    }

    settings: Dict[str, Any] = {}
    errors = []

    for name, (parser, default, required, validator, message) in schema.items():
        raw = source.get(name)

        if raw is None or raw.strip() == "":
            if required:
                errors.append(f"{name}: required but not set")
            else:
                settings[name] = default
            continue

        try:
            value = parser(raw)
        except (ValueError, TypeError) as exc:
            errors.append(f"{name}: invalid value {raw!r} ({exc})")
            continue

        if validator is not None and not validator(value):
            errors.append(f"{name}: invalid value {raw!r}, {message}")
            continue

        settings[name] = value

    # Cross-field validation
    if not errors:
        if settings["APP_ENV"] == "production" and settings["DEBUG"]:
            errors.append("DEBUG: must not be enabled when APP_ENV=production")

    if errors:
        raise ValueError(
            "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return settings
