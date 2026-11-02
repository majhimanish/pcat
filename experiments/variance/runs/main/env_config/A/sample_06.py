import os


class ConfigError(ValueError):
    pass


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}
_VALID_ENVIRONMENTS = {"development", "staging", "production", "test"}
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _parse_bool(name, raw):
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(f"{name} must be a boolean (true/false), got {raw!r}")


def _parse_int(name, raw, minimum=None, maximum=None):
    try:
        value = int(raw.strip())
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name} must be <= {maximum}, got {value}")
    return value


def _parse_float(name, raw, minimum=None):
    try:
        value = float(raw.strip())
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise ConfigError(f"{name} must be a finite number, got {raw!r}")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    return value


def _parse_list(raw):
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_settings(env=None, prefix=""):
    """Load and validate settings from environment variables.

    Args:
        env: Mapping to read from (defaults to os.environ).
        prefix: Optional prefix for variable names, e.g. "MYAPP_".

    Returns:
        A dict of validated settings.

    Raises:
        ConfigError: If any values are invalid or required values are missing.
        All problems are collected and reported together.
    """
    env = os.environ if env is None else env
    errors = []
    settings = {}

    def get(name):
        raw = env.get(prefix + name)
        if raw is None or raw.strip() == "":
            return None
        return raw

    def load(name, default, parser, required=False):
        raw = get(name)
        if raw is None:
            if required:
                errors.append(f"{prefix}{name} is required but not set")
                return
            settings[name.lower()] = default
            return
        try:
            settings[name.lower()] = parser(raw)
        except ConfigError as exc:
            errors.append(str(exc))

    full = lambda n: prefix + n

    load("ENVIRONMENT", "development", lambda r: _check_choice(
        full("ENVIRONMENT"), r.strip().lower(), _VALID_ENVIRONMENTS))
    load("DEBUG", False, lambda r: _parse_bool(full("DEBUG"), r))
    load("HOST", "127.0.0.1", lambda r: r.strip())
    load("PORT", 8000, lambda r: _parse_int(full("PORT"), r, 1, 65535))
    load("LOG_LEVEL", "INFO", lambda r: _check_choice(
        full("LOG_LEVEL"), r.strip().upper(), _VALID_LOG_LEVELS))
    load("WORKERS", 4, lambda r: _parse_int(full("WORKERS"), r, 1, 256))
    load("TIMEOUT_SECONDS", 30.0, lambda r: _parse_float(full("TIMEOUT_SECONDS"), r, 0.0))
    load("ALLOWED_HOSTS", ["localhost"], _parse_list)
    load("DATABASE_URL", "sqlite:///app.db", lambda r: _check_url(full("DATABASE_URL"), r.strip()))

    # Secret key is required in production, optional (insecure default) elsewhere.
    is_production = settings.get("environment") == "production"
    load("SECRET_KEY", None if is_production else "dev-insecure-key",
         lambda r: _check_min_length(full("SECRET_KEY"), r, 16),
         required=is_production)

    if settings.get("environment") == "production" and settings.get("debug") is True:
        errors.append(f"{full('DEBUG')} must not be enabled when {full('ENVIRONMENT')} is production")

    if errors:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return settings


def _check_choice(name, value, choices):
    if value not in choices:
        raise ConfigError(f"{name} must be one of {sorted(choices)}, got {value!r}")
    return value


def _check_url(name, value):
    if "://" not in value:
        raise ConfigError(f"{name} must be a URL like 'scheme://...', got {value!r}")
    return value


def _check_min_length(name, value, length):
    if len(value) < length:
        raise ConfigError(f"{name} must be at least {length} characters long")
    return value
