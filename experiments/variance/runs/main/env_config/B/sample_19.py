import os
from typing import Any, Callable, Iterable, Optional

_MISSING = object()
_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}


def get_env(
    name: str,
    default: Any = _MISSING,
    cast: Optional[Callable[[str], Any]] = str,
    *,
    required: bool = False,
    choices: Optional[Iterable[Any]] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    validator: Optional[Callable[[Any], bool]] = None,
    strip: bool = True,
    environ: Optional[dict] = None,
) -> Any:
    """
    Read, parse and validate an environment variable.

    Args:
        name:       Environment variable name.
        default:    Value returned when the variable is unset or empty.
                    The default is returned as-is (not cast), but is still
                    validated against choices/range/validator.
        cast:       Callable converting the raw string to the target type.
                    Use `bool` (or None for str) for built-in handling of
                    booleans; `list` splits on commas. Any callable also works
                    (e.g. int, float, pathlib.Path).
        required:   If True and no value/default is available, raise ValueError.
        choices:    Allowed values (after casting).
        min_value:  Minimum allowed value (inclusive) for numeric results.
        max_value:  Maximum allowed value (inclusive) for numeric results.
        validator:  Extra predicate; must return True for the value to pass.
        strip:      Strip surrounding whitespace from the raw value.
        environ:    Mapping to read from (defaults to os.environ); handy for tests.

    Returns:
        The parsed and validated value, or the default.

    Raises:
        ValueError: If the variable is missing but required, can't be parsed,
                    or fails validation.
    """
    env = os.environ if environ is None else environ
    raw = env.get(name)
    if raw is not None and strip:
        raw = raw.strip()

    if raw is None or raw == "":
        if default is not _MISSING:
            value = default
        elif required:
            raise ValueError(f"Environment variable {name} is required but not set")
        else:
            return None
    else:
        try:
            if cast is None or cast is str:
                value = raw
            elif cast is bool:
                lowered = raw.lower()
                if lowered in _TRUE_VALUES:
                    value = True
                elif lowered in _FALSE_VALUES:
                    value = False
                else:
                    raise ValueError(f"expected a boolean, got {raw!r}")
            elif cast is list:
                value = [item.strip() for item in raw.split(",") if item.strip()]
            else:
                value = cast(raw)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Environment variable {name}={raw!r} could not be parsed: {exc}"
            ) from exc

    if choices is not None and value not in set(choices):
        raise ValueError(
            f"Environment variable {name}={value!r} must be one of {sorted(map(str, choices))}"
        )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if min_value is not None and value < min_value:
            raise ValueError(f"Environment variable {name}={value} must be >= {min_value}")
        if max_value is not None and value > max_value:
            raise ValueError(f"Environment variable {name}={value} must be <= {max_value}")
    if validator is not None and not validator(value):
        raise ValueError(f"Environment variable {name}={value!r} failed validation")

    return value
