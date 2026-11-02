import os


def _get_str(env, name, default=None, required=False, choices=None):
    value = env.get(name)
    if value is None or value.strip() == "":
        if required:
            raise ValueError(f"Missing required environment variable: {name}")
        return default
    value = value.strip()
    if choices is not None and value not in choices:
        raise ValueError(f"{name} must be one of {sorted(choices)}, got {value!r}")
    return value


def _get_int(env, name, default, minimum=None, maximum=None):
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}, got {value}")
    return value


def _get_float(env, name, default, minimum=None, maximum=None):
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}, got {value}")
    return value


def _get_bool(env, name, default):
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {raw!r}")


def _get_list(env, name, default, separator=","):
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return list(default)
    return [item.strip() for item in raw.split(separator) if item.strip()]


def load_config(env=None):
    """Load application config from environment variables.

    Applies defaults, validates types and ranges, and returns a dict.
    Raises ValueError listing all problems found.
    """
    env = os.environ if env is None else env
    config = {}
    errors = []

    loaders = {
        "app_env": lambda: _get_str(
            env, "APP_ENV", default="development",
            choices={"development", "staging", "production"},
        ),
        "debug": lambda: _get_bool(env, "DEBUG", default=False),
        "host": lambda: _get_str(env, "HOST", default="127.0.0.1"),
        "port": lambda: _get_int(env, "PORT", default=8000, minimum=1, maximum=65535),
        "workers": lambda: _get_int(env, "WORKERS", default=1, minimum=1, maximum=64),
        "timeout": lambda: _get_float(env, "TIMEOUT", default=30.0, minimum=0.1),
        "log_level": lambda: _get_str(
            env, "LOG_LEVEL", default="INFO",
            choices={"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
        ),
        "allowed_hosts": lambda: _get_list(env, "ALLOWED_HOSTS", default=["localhost"]),
        "database_url": lambda: _get_str(env, "DATABASE_URL", required=True),
    }

    for key, loader in loaders.items():
        try:
            config[key] = loader()
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        raise ValueError("Invalid configuration:\n- " + "\n- ".join(errors))

    if config["app_env"] == "production" and config["debug"]:
        raise ValueError("Invalid configuration: DEBUG must be false in production")

    return config
