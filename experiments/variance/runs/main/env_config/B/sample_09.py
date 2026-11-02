import os
from typing import Any, Callable, Iterable, Mapping, Optional

_TRUE = {"1", "true", "yes", "y", "on", "t"}
_FALSE = {"0", "false", "no", "n", "off", "f", ""}


def parse_bool(value: str) -> bool:
    """Parse a string into a bool, raising ValueError if unrecognized."""
    v = value.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def parse_list(value: str, sep: str = ",") -> list:
    """Split a delimited string into a list of stripped, non-empty items."""
    return [item.strip() for item in value.split(sep) if item.strip()]


def get_env(
    name: str,
    default: Any = None,
    cast: Callable[[str], Any] = str,
    *,
    required: bool = False,
    choices: Optional[Iterable[Any]] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    validator: Optional[Callable[[Any], bool]] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Any:
    """
    Read, parse, and validate a single environment variable.

    Args:
        name:       Variable name.
        default:    Value returned when the variable is unset or empty.
                    The default is returned as-is (not cast or validated).
        cast:       Callable converting the raw string (e.g. int, float,
                    parse_bool, parse_list). Defaults to str.
        required:   If True, a missing/empty variable raises ValueError
                    (the default is ignored).
        choices:    Allowed values after casting.
        min_value:  Minimum allowed value (inclusive) for comparable types.
        max_value:  Maximum allowed value (inclusive) for comparable types.
        validator:  Extra predicate; must return True for the value to be valid.
        env:        Mapping to read from (defaults to os.environ).

    Raises:
        ValueError: If the variable is required but missing, cannot be cast,
                    or fails any validation rule.
    """
    source = os.environ if env is None else env
    raw = source.get(name)

    if raw is None or raw.strip() == "":
        if required:
            raise ValueError(f"environment variable {name} is required but not set")
        return default

    raw = raw.strip()

    try:
        value = cast(raw)
    except (ValueError, TypeError) as exc:
        cast_name = getattr(cast, "__name__", repr(cast))
        raise ValueError(
            f"environment variable {name}={raw!r} is not a valid {cast_name}: {exc}"
        ) from exc

    if choices is not None:
        allowed = list(choices)
        if value not in allowed:
            raise ValueError(
                f"environment variable {name}={value!r} must be one of {allowed}"
            )

    if min_value is not None and value < min_value:
        raise ValueError(
            f"environment variable {name}={value!r} must be >= {min_value}"
        )

    if max_value is not None and value > max_value:
        raise ValueError(
            f"environment variable {name}={value!r} must be <= {max_value}"
        )

    if validator is not None and not validator(value):
        raise ValueError(f"environment variable {name}={value!r} failed validation")

    return value


def load_settings(
    spec: Mapping[str, Mapping[str, Any]],
    env: Optional[Mapping[str, str]] = None,
) -> dict:
    """
    Load many settings at once, collecting all errors before raising.

    `spec` maps setting name -> keyword arguments for get_env, e.g.:

        settings = load_settings({
            "PORT":      {"default": 8080, "cast": int, "min_value": 1, "max_value": 65535},
            "DEBUG":     {"default": False, "cast": parse_bool},
            "LOG_LEVEL": {"default": "INFO", "choices": ["DEBUG", "INFO", "WARNING", "ERROR"]},
            "HOSTS":     {"default": ["localhost"], "cast": parse_list},
            "SECRET":    {"required": True},
        })

    Raises:
        ValueError: A single error listing every invalid or missing setting.
    """
    result = {}
    errors = []
    for name, options in spec.items():
        try:
            result[name] = get_env(name, env=env, **options)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError("invalid configuration:\n  - " + "\n  - ".join(errors))
    return result
