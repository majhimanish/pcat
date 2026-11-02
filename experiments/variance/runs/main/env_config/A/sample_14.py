import os


def _parse_bool(name, raw):
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be a boolean (true/false/1/0/yes/no/on/off), got {raw!r}")


def _parse_int(name, raw):
    try:
        return int(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None


def _parse_str(name, raw):
    return raw.strip()


def load_settings(environ=None):
    """Load and validate application settings from environment variables.

    Reads from `environ` (defaults to os.environ). Missing or empty variables
    fall back to defaults; required variables without a default raise an error.
    All validation problems are collected and reported together in a single
    ValueError.

    Recognized variables:
        APP_ENV        str   one of: development, staging, production (default: development)
        APP_HOST       str   non-empty host/interface (default: 127.0.0.1)
        APP_PORT       int   1-65535 (default: 8000)
        APP_DEBUG      bool  (default: False; must be False in production)
        APP_WORKERS    int   1-64 (default: 1)
        APP_LOG_LEVEL  str   DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
        APP_TIMEOUT    int   seconds, > 0 (default: 30)
        APP_SECRET_KEY str   required when APP_ENV is production; min 16 chars

    Returns:
        dict of validated settings.

    Raises:
        ValueError: if one or more settings are invalid.
    """
    env = os.environ if environ is None else environ

    # name: (parser, default, validator, error message)
    spec = {
        "APP_ENV": (
            _parse_str, "development",
            lambda v: v in ("development", "staging", "production"),
            "must be one of: development, staging, production",
        ),
        "APP_HOST": (
            _parse_str, "127.0.0.1",
            lambda v: len(v) > 0,
            "must not be empty",
        ),
        "APP_PORT": (
            _parse_int, 8000,
            lambda v: 1 <= v <= 65535,
            "must be between 1 and 65535",
        ),
        "APP_DEBUG": (
            _parse_bool, False,
            lambda v: True,
            "",
        ),
        "APP_WORKERS": (
            _parse_int, 1,
            lambda v: 1 <= v <= 64,
            "must be between 1 and 64",
        ),
        "APP_LOG_LEVEL": (
            lambda n, r: r.strip().upper(), "INFO",
            lambda v: v in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
            "must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        ),
        "APP_TIMEOUT": (
            _parse_int, 30,
            lambda v: v > 0,
            "must be greater than 0",
        ),
    }

    settings = {}
    errors = []

    for name, (parser, default, validator, message) in spec.items():
        raw = env.get(name)
        if raw is None or raw.strip() == "":
            settings[name] = default
            continue
        try:
            value = parser(name, raw)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not validator(value):
            errors.append(f"{name} {message}, got {raw!r}")
            continue
        settings[name] = value

    # Cross-field validation
    if settings.get("APP_ENV") == "production":
        if settings.get("APP_DEBUG"):
            errors.append("APP_DEBUG must be false when APP_ENV is production")
        secret = env.get("APP_SECRET_KEY", "").strip()
        if len(secret) < 16:
            errors.append("APP_SECRET_KEY is required in production and must be at least 16 characters")
        settings["APP_SECRET_KEY"] = secret
    else:
        settings["APP_SECRET_KEY"] = env.get("APP_SECRET_KEY", "").strip() or None

    if errors:
        raise ValueError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return settings
