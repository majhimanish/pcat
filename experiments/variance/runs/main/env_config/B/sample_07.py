import os


def _get_env(name, default=None, required=False):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        if required:
            raise ValueError(f"Missing required environment variable: {name}")
        return default
    return value.strip()


def _parse_int(name, raw, min_value=None, max_value=None):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer, got {raw!r}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be <= {max_value}, got {value}")
    return value


def _parse_float(name, raw, min_value=None, max_value=None):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number, got {raw!r}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be <= {max_value}, got {value}")
    return value


def _parse_bool(name, raw):
    truthy = {"1", "true", "yes", "on"}
    falsy = {"0", "false", "no", "off"}
    lowered = str(raw).strip().lower()
    if lowered in truthy:
        return True
    if lowered in falsy:
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {raw!r}")


def _parse_choice(name, raw, choices):
    value = str(raw).lower()
    if value not in choices:
        raise ValueError(f"{name} must be one of {sorted(choices)}, got {raw!r}")
    return value


def _parse_list(raw):
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def load_config():
    """Load configuration from environment variables, applying defaults and
    validating values. Returns a dict. Raises ValueError listing all problems."""
    errors = []
    config = {}

    def collect(key, func):
        try:
            config[key] = func()
        except ValueError as exc:
            errors.append(str(exc))

    collect("app_env", lambda: _parse_choice(
        "APP_ENV", _get_env("APP_ENV", "development"),
        {"development", "staging", "production"}))
    collect("debug", lambda: _parse_bool("DEBUG", _get_env("DEBUG", "false")))
    collect("host", lambda: _get_env("HOST", "127.0.0.1"))
    collect("port", lambda: _parse_int(
        "PORT", _get_env("PORT", "8000"), min_value=1, max_value=65535))
    collect("workers", lambda: _parse_int(
        "WORKERS", _get_env("WORKERS", "4"), min_value=1, max_value=128))
    collect("timeout_seconds", lambda: _parse_float(
        "TIMEOUT_SECONDS", _get_env("TIMEOUT_SECONDS", "30"), min_value=0.1))
    collect("log_level", lambda: _parse_choice(
        "LOG_LEVEL", _get_env("LOG_LEVEL", "info"),
        {"debug", "info", "warning", "error", "critical"}))
    collect("allowed_hosts", lambda: _parse_list(
        _get_env("ALLOWED_HOSTS", "localhost,127.0.0.1")))
    collect("database_url", lambda: _get_env("DATABASE_URL", required=True))
    collect("secret_key", lambda: _get_env("SECRET_KEY", required=True))

    if not errors and config["app_env"] == "production":
        if config["debug"]:
            errors.append("DEBUG must be false when APP_ENV is production")
        if len(config["secret_key"]) < 32:
            errors.append("SECRET_KEY must be at least 32 characters in production")

    if errors:
        raise ValueError("Invalid configuration:\n- " + "\n- ".join(errors))

    return config
