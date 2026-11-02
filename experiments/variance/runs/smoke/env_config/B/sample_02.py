import os


def _get_str(name, default=None, required=False):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        if required and default is None:
            raise ValueError(f"Missing required environment variable: {name}")
        return default
    return value.strip()


def _get_int(name, default, min_value=None, max_value=None):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = int(raw.strip())
        except ValueError:
            raise ValueError(f"{name} must be an integer, got {raw!r}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be <= {max_value}, got {value}")
    return value


def _get_float(name, default, min_value=None, max_value=None):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = float(raw.strip())
        except ValueError:
            raise ValueError(f"{name} must be a number, got {raw!r}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be <= {max_value}, got {value}")
    return value


def _get_bool(name, default):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {raw!r}")


def _get_choice(name, default, choices):
    value = _get_str(name, default)
    if value.lower() not in choices:
        raise ValueError(f"{name} must be one of {sorted(choices)}, got {value!r}")
    return value.lower()


def _get_list(name, default=None, sep=","):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return list(default or [])
    return [item.strip() for item in raw.split(sep) if item.strip()]


def load_config():
    """Load application config from environment variables.

    Returns a dict. Raises ValueError on invalid or missing required values.
    """
    config = {
        "env": _get_choice("APP_ENV", "development", {"development", "staging", "production"}),
        "debug": _get_bool("APP_DEBUG", False),
        "host": _get_str("APP_HOST", "127.0.0.1"),
        "port": _get_int("APP_PORT", 8000, min_value=1, max_value=65535),
        "workers": _get_int("APP_WORKERS", 1, min_value=1, max_value=64),
        "timeout": _get_float("APP_TIMEOUT", 30.0, min_value=0.0),
        "log_level": _get_choice(
            "APP_LOG_LEVEL", "info", {"debug", "info", "warning", "error", "critical"}
        ),
        "allowed_hosts": _get_list("APP_ALLOWED_HOSTS", ["localhost"]),
        "database_url": _get_str("DATABASE_URL", required=True),
        "secret_key": _get_str("APP_SECRET_KEY", required=True),
    }

    if config["env"] == "production":
        if config["debug"]:
            raise ValueError("APP_DEBUG must be false in production")
        if len(config["secret_key"]) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 characters in production")

    return config
