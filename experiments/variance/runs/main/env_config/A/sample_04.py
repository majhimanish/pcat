import os
from typing import Any, Callable, Optional


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}


def parse_bool(value: str) -> bool:
    """Convert a string to a boolean, raising ValueError if unrecognized."""
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def parse_list(value: str) -> list:
    """Convert a comma-separated string to a list of non-empty stripped items."""
    return [item.strip() for item in value.split(",") if item.strip()]


def load_setting(
    env: dict,
    name: str,
    default: Any = None,
    cast: Callable[[str], Any] = str,
    required: bool = False,
    validator: Optional[Callable[[Any], bool]] = None,
    choices: Optional[list] = None,
) -> Any:
    """Load a single setting from env, applying cast, default, and validation."""
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        if required:
            raise ValueError(f"missing required environment variable: {name}")
        return default

    try:
        value = cast(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid value for {name}: {raw!r} ({exc})") from exc

    if choices is not None and value not in choices:
        raise ValueError(f"{name} must be one of {choices}, got {value!r}")
    if validator is not None and not validator(value):
        raise ValueError(f"invalid value for {name}: {value!r}")
    return value


def load_settings(env: Optional[dict] = None) -> dict:
    """Load and validate application settings from environment variables.

    Reads from os.environ unless an explicit mapping is provided. Collects
    all validation errors and raises a single ValueError listing them.
    """
    env = os.environ if env is None else env

    specs = {
        "APP_ENV": dict(default="development", choices=["development", "staging", "production"]),
        "DEBUG": dict(default=False, cast=parse_bool),
        "HOST": dict(default="127.0.0.1"),
        "PORT": dict(default=8000, cast=int, validator=lambda p: 1 <= p <= 65535),
        "WORKERS": dict(default=1, cast=int, validator=lambda w: w >= 1),
        "TIMEOUT_SECONDS": dict(default=30.0, cast=float, validator=lambda t: t > 0),
        "LOG_LEVEL": dict(
            default="INFO",
            cast=lambda s: s.strip().upper(),
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        ),
        "ALLOWED_HOSTS": dict(default=["localhost"], cast=parse_list),
        "DATABASE_URL": dict(
            default="sqlite:///app.db",
            validator=lambda u: "://" in u,
        ),
        "SECRET_KEY": dict(
            required=True,
            validator=lambda k: len(k) >= 16,
        ),
    }

    settings = {}
    errors = []
    for name, spec in specs.items():
        try:
            settings[name] = load_setting(env, name, **spec)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        raise ValueError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    if settings["APP_ENV"] == "production" and settings["DEBUG"]:
        raise ValueError("Invalid configuration: DEBUG must be disabled in production")

    return settings
