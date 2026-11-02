import os
from typing import Any, Callable, Mapping, Optional


class ConfigError(ValueError):
    """Raised when a configuration value is missing or invalid."""


_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


def parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(f"{name}: invalid boolean {raw!r}")


def parse_int(name: str, raw: str) -> int:
    try:
        return int(raw.strip())
    except ValueError:
        raise ConfigError(f"{name}: invalid integer {raw!r}") from None


def parse_float(name: str, raw: str) -> float:
    try:
        value = float(raw.strip())
    except ValueError:
        raise ConfigError(f"{name}: invalid float {raw!r}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise ConfigError(f"{name}: non-finite float {raw!r}")
    return value


def parse_str(name: str, raw: str) -> str:
    return raw


def parse_list(name: str, raw: str) -> list:
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_setting(
    env: Mapping[str, str],
    name: str,
    parser: Callable[[str, str], Any] = parse_str,
    default: Any = None,
    required: bool = False,
    choices: Optional[set] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> Any:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        if required:
            raise ConfigError(f"{name}: required environment variable is missing")
        return default

    value = parser(name, raw)

    if choices is not None and value not in choices:
        raise ConfigError(
            f"{name}: {value!r} is not one of {sorted(choices, key=str)}"
        )
    if min_value is not None and value < min_value:
        raise ConfigError(f"{name}: {value!r} is below minimum {min_value}")
    if max_value is not None and value > max_value:
        raise ConfigError(f"{name}: {value!r} is above maximum {max_value}")
    return value


def load_config(env: Optional[Mapping[str, str]] = None) -> dict:
    """Load application configuration from os.environ (or a provided mapping).

    Missing values fall back to defaults; values are converted to their
    proper types; invalid values raise ConfigError. All problems are
    collected and reported together.
    """
    if env is None:
        env = os.environ

    # (key, env var name, parser, default, extra kwargs)
    spec = [
        ("host", "APP_HOST", parse_str, "127.0.0.1", {}),
        ("port", "APP_PORT", parse_int, 8000, {"min_value": 1, "max_value": 65535}),
        ("debug", "APP_DEBUG", parse_bool, False, {}),
        ("timeout", "APP_TIMEOUT", parse_float, 30.0, {"min_value": 0}),
        ("workers", "APP_WORKERS", parse_int, 4, {"min_value": 1}),
        (
            "log_level",
            "APP_LOG_LEVEL",
            lambda n, r: r.strip().upper(),
            "INFO",
            {"choices": {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}},
        ),
        ("allowed_hosts", "APP_ALLOWED_HOSTS", parse_list, ["localhost"], {}),
        ("database_url", "APP_DATABASE_URL", parse_str, None, {"required": True}),
    ]

    config = {}
    errors = []
    for key, name, parser, default, kwargs in spec:
        try:
            config[key] = get_setting(env, name, parser, default, **kwargs)
        except ConfigError as exc:
            errors.append(str(exc))

    if errors:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(errors))
    return config
