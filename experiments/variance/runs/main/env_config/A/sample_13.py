import os
from typing import Any


class SettingsError(ValueError):
    """Raised when one or more settings are invalid."""


def _parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def _parse_list(value: str) -> list:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_settings(env: dict = None, prefix: str = "APP_") -> dict:
    """Load and validate settings from environment variables.

    Reads variables named ``<prefix><KEY>`` (e.g. APP_PORT), applies defaults,
    converts types, and validates values. Raises a single SettingsError
    listing every problem found.
    """
    env = os.environ if env is None else env

    # name: (default, parser, validator, validation message). default=None => required.
    schema = {
        "DEBUG": (False, _parse_bool, None, None),
        "HOST": ("127.0.0.1", str, lambda v: bool(v.strip()), "must not be empty"),
        "PORT": (8000, int, lambda v: 1 <= v <= 65535, "must be between 1 and 65535"),
        "LOG_LEVEL": (
            "INFO",
            lambda v: v.strip().upper(),
            lambda v: v in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
            "must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL",
        ),
        "TIMEOUT": (30.0, float, lambda v: v > 0, "must be greater than 0"),
        "MAX_WORKERS": (4, int, lambda v: v >= 1, "must be at least 1"),
        "ALLOWED_HOSTS": (["localhost"], _parse_list, lambda v: len(v) > 0, "must not be empty"),
        "DATABASE_URL": ("sqlite:///app.db", str, lambda v: "://" in v, "must be a URL like scheme://..."),
        "SECRET_KEY": (None, str, lambda v: len(v) >= 16, "must be at least 16 characters"),
    }

    settings: dict[str, Any] = {}
    errors: list[str] = []

    for key, (default, parser, validator, message) in schema.items():
        var_name = f"{prefix}{key}"
        raw = env.get(var_name)

        if raw is None or raw == "":
            if default is None:
                errors.append(f"{var_name}: required but not set")
                continue
            settings[key.lower()] = default
            continue

        try:
            value = parser(raw)
        except (ValueError, TypeError) as exc:
            errors.append(f"{var_name}: invalid value {raw!r} ({exc})")
            continue

        if validator is not None and not validator(value):
            errors.append(f"{var_name}: invalid value {raw!r}, {message}")
            continue

        settings[key.lower()] = value

    if errors:
        raise SettingsError("Invalid configuration:\n  " + "\n  ".join(errors))

    return settings
