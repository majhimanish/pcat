import os


def _get_str(env, name, default, required=False, allowed=None):
    value = env.get(name)
    if value is None or value.strip() == "":
        if required:
            raise ValueError(f"Missing required environment variable: {name}")
        return default
    value = value.strip()
    if allowed is not None and value not in allowed:
        raise ValueError(
            f"{name} must be one of {sorted(allowed)}, got {value!r}"
        )
    return value


def _get_int(env, name, default, min_value=None, max_value=None):
    value = env.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value.strip())
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {value!r}") from None
    if min_value is not None and parsed < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {parsed}")
    if max_value is not None and parsed > max_value:
        raise ValueError(f"{name} must be <= {max_value}, got {parsed}")
    return parsed


def _get_float(env, name, default, min_value=None, max_value=None):
    value = env.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = float(value.strip())
    except ValueError:
        raise ValueError(f"{name} must be a number, got {value!r}") from None
    if min_value is not None and parsed < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {parsed}")
    if max_value is not None and parsed > max_value:
        raise ValueError(f"{name} must be <= {max_value}, got {parsed}")
    return parsed


def _get_bool(env, name, default):
    value = env.get(name)
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {value!r}")


def _get_list(env, name, default, separator=","):
    value = env.get(name)
    if value is None or value.strip() == "":
        return list(default)
    return [item.strip() for item in value.split(separator) if item.strip()]


def load_config(env=None, prefix="APP_"):
    """Load configuration from environment variables.

    Reads variables named PREFIX + KEY (default prefix "APP_"), applies
    defaults, validates values, and returns a plain dict. Raises ValueError
    listing all problems found.
    """
    env = os.environ if env is None else env
    errors = []
    config = {}

    specs = [
        ("env", lambda n: _get_str(
            env, n, "development",
            allowed={"development", "staging", "production"})),
        ("debug", lambda n: _get_bool(env, n, False)),
        ("host", lambda n: _get_str(env, n, "127.0.0.1")),
        ("port", lambda n: _get_int(env, n, 8000, min_value=1, max_value=65535)),
        ("workers", lambda n: _get_int(env, n, 1, min_value=1, max_value=64)),
        ("timeout", lambda n: _get_float(env, n, 30.0, min_value=0.0)),
        ("log_level", lambda n: _get_str(
            env, n, "INFO",
            allowed={"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})),
        ("allowed_hosts", lambda n: _get_list(env, n, ["localhost"])),
        ("database_url", lambda n: _get_str(env, n, None, required=True)),
    ]

    for key, getter in specs:
        var_name = f"{prefix}{key.upper()}"
        try:
            config[key] = getter(var_name)
        except ValueError as exc:
            errors.append(str(exc))

    if not errors and config["env"] == "production" and config["debug"]:
        errors.append("APP_DEBUG must be false when APP_ENV is 'production'")

    if errors:
        raise ValueError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return config
