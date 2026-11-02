import os
from typing import Any, Callable, Optional, Sequence

_TRUE = {"1", "true", "yes", "y", "on"}
_FALSE = {"0", "false", "no", "n", "off"}


def parse_bool(value: str) -> bool:
    """Parse a string into a boolean, raising ValueError if unrecognized."""
    v = value.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def parse_list(value: str, sep: str = ",") -> list:
    """Split a string into a list of stripped, non-empty items."""
    return [item.strip() for item in value.split(sep) if item.strip()]


def get_env(
    name: str,
    default: Any = None,
    cast: Callable[[str], Any] = str,
    required: bool = False,
    choices: Optional[Sequence[Any]] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    allow_empty: bool = False,
    env: Optional[dict] = None,
) -> Any:
    """
    Read, parse and validate a single environment variable.

    Args:
        name: Environment variable name.
        default: Value returned when the variable is unset (or empty, unless
            allow_empty is True). Not validated or cast.
        cast: Callable converting the raw string to the desired type
            (e.g. int, float, parse_bool, parse_list).
        required: If True and the variable is missing, raise ValueError.
        choices: Optional collection of permitted values (after casting).
        min_value / max_value: Optional inclusive numeric bounds.
        allow_empty: Treat an empty string as a real value instead of unset.
        env: Mapping to read from (defaults to os.environ); useful for tests.

    Raises:
        ValueError: If the variable is required but missing, cannot be cast,
            or fails validation.
    """
    source = os.environ if env is None else env
    raw = source.get(name)

    if raw is None or (raw.strip() == "" and not allow_empty):
        if required:
            raise ValueError(f"environment variable {name} is required but not set")
        return default

    try:
        value = cast(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"environment variable {name}={raw!r} is invalid: {exc}"
        ) from exc

    if choices is not None and value not in choices:
        raise ValueError(
            f"environment variable {name}={value!r} must be one of {list(choices)}"
        )
    if min_value is not None and value < min_value:
        raise ValueError(
            f"environment variable {name}={value!r} must be >= {min_value}"
        )
    if max_value is not None and value > max_value:
        raise ValueError(
            f"environment variable {name}={value!r} must be <= {max_value}"
        )

    return value


def load_settings(schema: dict, env: Optional[dict] = None) -> dict:
    """
    Load many settings at once, collecting all errors before raising.

    `schema` maps setting names to kwargs for get_env, e.g.:

        schema = {
            "PORT": {"default": 8000, "cast": int, "min_value": 1, "max_value": 65535},
            "DEBUG": {"default": False, "cast": parse_bool},
            "LOG_LEVEL": {"default": "INFO", "choices": ["DEBUG", "INFO", "WARNING", "ERROR"]},
            "ALLOWED_HOSTS": {"default": ["localhost"], "cast": parse_list},
            "DATABASE_URL": {"required": True},
        }
        settings = load_settings(schema)

    Raises:
        ValueError: A single error listing every invalid or missing setting.
    """
    settings = {}
    errors = []
    for name, options in schema.items():
        try:
            settings[name] = get_env(name, env=env, **options)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError("invalid configuration:\n  - " + "\n  - ".join(errors))
    return settings
