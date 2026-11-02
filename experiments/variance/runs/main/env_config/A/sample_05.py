import os
from typing import Any, Dict, List, Optional


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_ENVIRONMENTS = {"development", "staging", "production", "test"}


def _parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(f"{name}: invalid boolean value {raw!r}")


def _parse_int(name: str, raw: str, minimum: Optional[int], maximum: Optional[int]) -> int:
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"{name}: invalid integer value {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ValueError(f"{name}: {value} is below the minimum of {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name}: {value} is above the maximum of {maximum}")
    return value


def _parse_float(name: str, raw: str, minimum: Optional[float], maximum: Optional[float]) -> float:
    try:
        value = float(raw.strip())
    except ValueError:
        raise ValueError(f"{name}: invalid float value {raw!r}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{name}: value must be finite, got {raw!r}")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name}: {value} is below the minimum of {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name}: {value} is above the maximum of {maximum}")
    return value


def _parse_choice(name: str, raw: str, choices: set, case_insensitive: bool) -> str:
    value = raw.strip()
    if case_insensitive:
        value = value.lower()
        normalized = {c.lower(): c for c in choices}
        if value in normalized:
            return normalized[value]
    elif value in choices:
        return value
    raise ValueError(f"{name}: {raw!r} is not one of {sorted(choices)}")


def _parse_list(raw: str, separator: str = ",") -> List[str]:
    return [item.strip() for item in raw.split(separator) if item.strip()]


def load_settings(env: Optional[Dict[str, str]] = None, prefix: str = "") -> Dict[str, Any]:
    """Load and validate application settings from environment variables.

    Each setting falls back to a default when unset or empty. All validation
    problems are collected and raised together in a single ValueError.

    Args:
        env: Mapping to read from (defaults to os.environ). Useful for testing.
        prefix: Optional prefix applied to every variable name (e.g. "MYAPP_").

    Returns:
        A dict of validated settings.

    Raises:
        ValueError: If one or more settings are missing (when required) or invalid.
    """
    source = os.environ if env is None else env

    # (key, parser kind, default, extra options). default=None with required=True
    # means the variable must be provided.
    spec = [
        ("ENVIRONMENT", "choice", "development",
         {"choices": _ENVIRONMENTS, "case_insensitive": True}),
        ("DEBUG", "bool", False, {}),
        ("HOST", "str", "127.0.0.1", {}),
        ("PORT", "int", 8000, {"minimum": 1, "maximum": 65535}),
        ("WORKERS", "int", 1, {"minimum": 1, "maximum": 256}),
        ("LOG_LEVEL", "choice", "INFO",
         {"choices": _LOG_LEVELS, "case_insensitive": True}),
        ("REQUEST_TIMEOUT", "float", 30.0, {"minimum": 0.0, "maximum": 3600.0}),
        ("ALLOWED_HOSTS", "list", ["localhost"], {}),
        ("DATABASE_URL", "str", "sqlite:///app.db", {}),
        ("SECRET_KEY", "str", None, {"required_in": {"production", "staging"}, "min_length": 16}),
    ]

    settings: Dict[str, Any] = {}
    errors: List[str] = []

    def lookup(key: str) -> Optional[str]:
        raw = source.get(f"{prefix}{key}")
        if raw is None or raw.strip() == "":
            return None
        return raw

    for key, kind, default, opts in spec:
        name = f"{prefix}{key}"
        raw = lookup(key)

        if raw is None:
            settings[key] = default
            continue

        try:
            if kind == "bool":
                settings[key] = _parse_bool(name, raw)
            elif kind == "int":
                settings[key] = _parse_int(name, raw, opts.get("minimum"), opts.get("maximum"))
            elif kind == "float":
                settings[key] = _parse_float(name, raw, opts.get("minimum"), opts.get("maximum"))
            elif kind == "choice":
                settings[key] = _parse_choice(
                    name, raw, opts["choices"], opts.get("case_insensitive", False)
                )
            elif kind == "list":
                settings[key] = _parse_list(raw)
            else:
                value = raw.strip()
                min_length = opts.get("min_length")
                if min_length is not None and len(value) < min_length:
                    raise ValueError(f"{name}: must be at least {min_length} characters long")
                settings[key] = value
        except ValueError as exc:
            errors.append(str(exc))

    # Cross-field validation: some settings are required only in certain environments.
    environment = settings.get("ENVIRONMENT")
    for key, _kind, _default, opts in spec:
        required_in = opts.get("required_in")
        if required_in and settings.get(key) is None and environment in required_in:
            errors.append(
                f"{prefix}{key}: is required when {prefix}ENVIRONMENT is {environment!r}"
            )

    if settings.get("ENVIRONMENT") == "production" and settings.get("DEBUG"):
        errors.append(f"{prefix}DEBUG: must not be enabled in production")

    if errors:
        raise ValueError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return settings
