import os


class SettingsError(ValueError):
    pass


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _parse_bool(name, raw):
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise SettingsError(f"{name}: invalid boolean {raw!r}")


def _parse_int(name, raw):
    try:
        return int(raw.strip())
    except ValueError:
        raise SettingsError(f"{name}: invalid integer {raw!r}") from None


def _parse_float(name, raw):
    try:
        return float(raw.strip())
    except ValueError:
        raise SettingsError(f"{name}: invalid float {raw!r}") from None


def _parse_list(name, raw):
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_str(name, raw):
    return raw


_PARSERS = {
    str: _parse_str,
    int: _parse_int,
    float: _parse_float,
    bool: _parse_bool,
    list: _parse_list,
}

# name: (type, default, required, validator or None)
_SCHEMA = {
    "APP_NAME": (str, "myapp", False, lambda v: bool(v.strip())),
    "APP_ENV": (str, "development", False,
                lambda v: v in {"development", "staging", "production"}),
    "DEBUG": (bool, False, False, None),
    "HOST": (str, "127.0.0.1", False, lambda v: bool(v.strip())),
    "PORT": (int, 8000, False, lambda v: 1 <= v <= 65535),
    "WORKERS": (int, 4, False, lambda v: v >= 1),
    "REQUEST_TIMEOUT": (float, 30.0, False, lambda v: v > 0),
    "LOG_LEVEL": (str, "INFO", False,
                  lambda v: v.upper() in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}),
    "ALLOWED_HOSTS": (list, ["localhost"], False, None),
    "DATABASE_URL": (str, None, False, None),
    "SECRET_KEY": (str, None, False, None),
}


def load_settings(env=None, schema=None):
    """Load and validate settings from environment variables.

    Unset or empty variables fall back to their defaults. All problems are
    collected and reported together in a single SettingsError.
    Returns a dict of validated settings.
    """
    env = os.environ if env is None else env
    schema = _SCHEMA if schema is None else schema
    settings = {}
    errors = []

    for name, (typ, default, required, validator) in schema.items():
        raw = env.get(name)
        if raw is None or raw.strip() == "":
            if required:
                errors.append(f"{name}: required but not set")
                continue
            settings[name] = list(default) if isinstance(default, list) else default
            continue

        try:
            value = _PARSERS[typ](name, raw)
        except SettingsError as exc:
            errors.append(str(exc))
            continue

        if validator is not None and not validator(value):
            errors.append(f"{name}: invalid value {raw!r}")
            continue

        if name == "LOG_LEVEL":
            value = value.upper()
        settings[name] = value

    if settings.get("APP_ENV") == "production":
        if not settings.get("SECRET_KEY"):
            errors.append("SECRET_KEY: required when APP_ENV is 'production'")
        if settings.get("DEBUG"):
            errors.append("DEBUG: must be disabled when APP_ENV is 'production'")

    if errors:
        raise SettingsError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return settings
