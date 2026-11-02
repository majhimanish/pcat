import os
from typing import Any, Callable, Mapping, Optional


class ConfigError(ValueError):
    """Raised when a configuration value is missing or invalid."""


_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}


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
        return float(raw.strip())
    except ValueError:
        raise ConfigError(f"{name}: invalid float {raw!r}") from None


def parse_list(name: str, raw: str) -> list:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_str(name: str, raw: str) -> str:
    return raw


_PARSERS = {
    str: parse_str,
    int: parse_int,
    float: parse_float,
    bool: parse_bool,
    list: parse_list,
}

_MISSING = object()


def get_env(
    name: str,
    type_: Any = str,
    default: Any = _MISSING,
    *,
    required: bool = False,
    choices: Optional[list] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Any:
    """Read one variable, converting it to `type_`.

    - Missing/empty variable: returns `default` (or raises ConfigError if
      `required` is True or no default was given and required is set).
    - Invalid value: raises ConfigError.
    """
    env = os.environ if environ is None else environ
    raw = env.get(name)

    if raw is None or raw.strip() == "":
        if required:
            raise ConfigError(f"{name}: required environment variable is not set")
        return None if default is _MISSING else default

    parser: Callable[[str, str], Any]
    if callable(type_) and type_ not in _PARSERS:
        def parser(n: str, r: str) -> Any:
            try:
                return type_(r)
            except Exception as exc:
                raise ConfigError(f"{n}: invalid value {r!r} ({exc})") from None
    else:
        parser = _PARSERS.get(type_)
        if parser is None:
            raise ConfigError(f"{name}: unsupported type {type_!r}")

    value = parser(name, raw)

    if choices is not None and value not in choices:
        raise ConfigError(f"{name}: {value!r} not in allowed choices {choices}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if min_value is not None and value < min_value:
            raise ConfigError(f"{name}: {value} is below minimum {min_value}")
        if max_value is not None and value > max_value:
            raise ConfigError(f"{name}: {value} is above maximum {max_value}")
    return value


def load_config(
    schema: Mapping[str, Mapping[str, Any]],
    environ: Optional[Mapping[str, str]] = None,
) -> dict:
    """Load a config dict from the environment according to `schema`.

    schema maps config keys to specs, e.g.:
        {
            "port": {"env": "APP_PORT", "type": int, "default": 8080,
                     "min_value": 1, "max_value": 65535},
            "debug": {"type": bool, "default": False},
            "db_url": {"type": str, "required": True},
        }
    `env` defaults to the upper-cased key. All errors are collected and
    raised together in a single ConfigError.
    """
    config = {}
    errors = []
    for key, spec in schema.items():
        spec = dict(spec)
        env_name = spec.pop("env", key.upper())
        type_ = spec.pop("type", str)
        try:
            config[key] = get_env(env_name, type_, environ=environ, **spec)
        except ConfigError as exc:
            errors.append(str(exc))
    if errors:
        raise ConfigError("Invalid configuration: " + "; ".join(errors))
    return config


def load_app_config(environ: Optional[Mapping[str, str]] = None) -> dict:
    """Example application configuration."""
    schema = {
        "host": {"type": str, "default": "127.0.0.1"},
        "port": {"type": int, "default": 8000, "min_value": 1, "max_value": 65535},
        "debug": {"type": bool, "default": False},
        "timeout": {"type": float, "default": 30.0, "min_value": 0},
        "allowed_hosts": {"type": list, "default": []},
        "log_level": {
            "type": str,
            "default": "INFO",
            "choices": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        },
    }
    return load_config(schema, environ=environ)
