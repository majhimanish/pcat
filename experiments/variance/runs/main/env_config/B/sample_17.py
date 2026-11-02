import os


def _get_str(name, default, allowed=None):
    value = os.environ.get(name, default).strip()
    if not value:
        value = default
    if allowed is not None and value not in allowed:
        raise ValueError(
            f"{name} must be one of {sorted(allowed)}, got {value!r}"
        )
    return value


def _get_int(name, default, min_value=None, max_value=None):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
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
        return default
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


def _get_required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config(prefix="APP_", require_secret=False):
    """Load configuration from environment variables.

    Returns a dict. Raises ValueError on invalid or missing values.
    """
    def n(key):
        return f"{prefix}{key}"

    config = {
        "env": _get_str(n("ENV"), "development",
                        allowed={"development", "staging", "production"}),
        "host": _get_str(n("HOST"), "127.0.0.1"),
        "port": _get_int(n("PORT"), 8000, min_value=1, max_value=65535),
        "debug": _get_bool(n("DEBUG"), False),
        "log_level": _get_str(n("LOG_LEVEL"), "INFO",
                              allowed={"DEBUG", "INFO", "WARNING",
                                       "ERROR", "CRITICAL"}).upper()
        if os.environ.get(n("LOG_LEVEL"), "").strip().upper() in
        {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", ""}
        else _get_str(n("LOG_LEVEL"), "INFO", allowed={"INFO"}),
        "timeout": _get_float(n("TIMEOUT"), 30.0, min_value=0.0),
        "workers": _get_int(n("WORKERS"), 4, min_value=1, max_value=256),
        "database_url": _get_str(n("DATABASE_URL"), "sqlite:///app.db"),
    }

    if require_secret:
        config["secret_key"] = _get_required(n("SECRET_KEY"))
    else:
        config["secret_key"] = os.environ.get(n("SECRET_KEY"), "").strip() or None

    if config["env"] == "production":
        if config["debug"]:
            raise ValueError("Debug mode must be disabled in production")
        if not config["secret_key"]:
            raise ValueError(
                f"{n('SECRET_KEY')} is required in production"
            )

    return config
