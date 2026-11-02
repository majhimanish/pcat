import os
from typing import Any, Callable, Mapping, Optional

_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}

_MISSING = object()


class ConfigError(ValueError):
    """Raised when a configuration value is missing or invalid."""


def parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(f"{name}: invalid boolean {raw!r} (expected one of "
                      f"{sorted(_TRUE_VALUES | _FALSE_VALUES)})")


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


def parse_list(name: str, raw: str, sep: str = ",") -> list:
    return [item.strip() for item in raw.split(sep) if item.strip()]


def parse_str(name: str, raw: str) -> str:
    return raw


_PARSERS = {
    str: parse_str,
    int: parse_int,
    float: parse_float,
    bool: parse_bool,
    list: parse_list,
}


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
    """Read one variable from the environment, converting and validating it.

    - Missing or empty variable -> `default` (if given); otherwise ConfigError
      when `required` is True or no default was supplied.
    - Invalid value -> ConfigError.
    """
    env = os.environ if environ is None else environ
    raw = env.get(name)

    if raw is None or raw.strip() == "":
        if default is not _MISSING and not required:
            return default
        raise ConfigError(f"{name}: required environment variable is not set")

    parser: Callable = type_ if (callable(type_) and type_ not in _PARSERS) else None
    if type_ in _PARSERS:
        value = _PARSERS[type_](name, raw)
    elif parser is not None:
        try:
            value = parser(raw)
        except Exception as exc:
            raise ConfigError(f"{name}: cannot convert {raw!r}: {exc}") from None
    else:
        raise ConfigError(f"{name}: unsupported type {type_!r}")

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

    schema maps config key -> spec dict with keys:
        env (str, defaults to key.upper()), type, default, required,
        choices, min_value, max_value.

    All errors are collected and raised together in one ConfigError.
    """
    config = {}
    errors = []
    for key, spec in schema.items():
        kwargs = {
            "type_": spec.get("type", str),
            "required": spec.get("required", False),
            "choices": spec.get("choices"),
            "min_value": spec.get("min_value"),
            "max_value": spec.get("max_value"),
            "environ": environ,
        }
        if "default" in spec:
            kwargs["default"] = spec["default"]
        try:
            config[key] = get_env(spec.get("env", key.upper()), **kwargs)
        except ConfigError as exc:
            errors.append(str(exc))
    if errors:
        raise ConfigError("; ".join(errors))
    return config


def load_app_config(environ: Optional[Mapping[str, str]] = None) -> dict:
    """Example: load the application's configuration from os.environ."""
    schema = {
        "debug": {"type": bool, "default": False},
        "port": {"type": int, "default": 8000, "min_value": 1, "max_value": 65535},
        "timeout": {"type": float, "default": 30.0, "min_value": 0},
        "log_level": {
            "type": str,
            "default": "INFO",
            "choices": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        },
        "allowed_hosts": {"type": list, "default": ["localhost"]},
        "database_url": {"type": str, "required": True},
    }
    return load_config(schema, environ)
