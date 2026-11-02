import os
from typing import Any, Callable, Mapping, Optional


class ConfigError(ValueError):
    """Raised when a configuration value is missing or invalid."""


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}

_MISSING = object()


def parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(
        f"Invalid boolean for {name}: {raw!r} "
        f"(expected one of {sorted(_TRUE_VALUES | _FALSE_VALUES)})"
    )


def parse_int(name: str, raw: str) -> int:
    try:
        return int(raw.strip())
    except ValueError:
        raise ConfigError(f"Invalid integer for {name}: {raw!r}") from None


def parse_float(name: str, raw: str) -> float:
    try:
        return float(raw.strip())
    except ValueError:
        raise ConfigError(f"Invalid float for {name}: {raw!r}") from None


def parse_str(name: str, raw: str) -> str:
    return raw


def parse_list(name: str, raw: str) -> list:
    return [item.strip() for item in raw.split(",") if item.strip()]


_PARSERS: dict = {
    bool: parse_bool,
    int: parse_int,
    float: parse_float,
    str: parse_str,
    list: parse_list,
}


def get_env(
    name: str,
    type_: Any = str,
    default: Any = _MISSING,
    required: bool = False,
    validator: Optional[Callable[[Any], bool]] = None,
    choices: Optional[list] = None,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Any:
    """Read one setting from os.environ (or `environ`), convert and validate it.

    - Missing/empty variable -> `default` (error if `required` or no default
      given and required=True).
    - Unconvertible or out-of-range value -> ConfigError.
    """
    env = os.environ if environ is None else environ
    raw = env.get(name)

    if raw is None or raw.strip() == "":
        if required:
            raise ConfigError(f"Missing required environment variable: {name}")
        return None if default is _MISSING else default

    parser = type_ if callable(type_) and type_ not in _PARSERS else None
    if type_ in _PARSERS:
        value = _PARSERS[type_](name, raw)
    elif parser is not None:
        try:
            value = parser(raw)
        except Exception as exc:
            raise ConfigError(f"Invalid value for {name}: {raw!r} ({exc})") from None
    else:
        raise ConfigError(f"Unsupported type for {name}: {type_!r}")

    if choices is not None and value not in choices:
        raise ConfigError(f"Invalid value for {name}: {value!r} (choices: {choices})")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name} must be <= {maximum}, got {value}")
    if validator is not None and not validator(value):
        raise ConfigError(f"Validation failed for {name}: {value!r}")

    return value


# Schema: name -> keyword arguments for get_env
DEFAULT_SCHEMA: dict = {
    "APP_HOST": {"type_": str, "default": "127.0.0.1"},
    "APP_PORT": {"type_": int, "default": 8000, "minimum": 1, "maximum": 65535},
    "APP_DEBUG": {"type_": bool, "default": False},
    "APP_TIMEOUT": {"type_": float, "default": 30.0, "minimum": 0},
    "APP_LOG_LEVEL": {
        "type_": str,
        "default": "INFO",
        "choices": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    },
    "APP_ALLOWED_HOSTS": {"type_": list, "default": []},
    "APP_SECRET_KEY": {"type_": str, "required": True},
}


def load_config(
    schema: Optional[Mapping[str, Mapping[str, Any]]] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> dict:
    """Load all settings described by `schema` from the environment.

    Collects every problem and raises a single ConfigError listing them all.
    """
    schema = DEFAULT_SCHEMA if schema is None else schema
    config: dict = {}
    errors: list = []

    for name, spec in schema.items():
        try:
            config[name] = get_env(name, environ=environ, **spec)
        except ConfigError as exc:
            errors.append(str(exc))

    if errors:
        raise ConfigError(
            "Invalid configuration:\n  - " + "\n  - ".join(errors)
        )
    return config
