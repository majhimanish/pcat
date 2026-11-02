import os


def _parse_bool(name, raw):
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {raw!r}")


def load_settings(env=None):
    """Load and validate application settings from environment variables.

    Args:
        env: Optional mapping to read from (defaults to os.environ).

    Returns:
        dict of validated settings.

    Raises:
        ValueError: if any variable is missing (when required) or invalid.
    """
    env = os.environ if env is None else env

    # (env var, type, default, required)
    spec = [
        ("APP_NAME", str, "myapp", False),
        ("APP_ENV", str, "development", False),
        ("DEBUG", bool, False, False),
        ("HOST", str, "127.0.0.1", False),
        ("PORT", int, 8000, False),
        ("WORKERS", int, 1, False),
        ("TIMEOUT_SECONDS", float, 30.0, False),
        ("LOG_LEVEL", str, "INFO", False),
        ("DATABASE_URL", str, None, False),
    ]

    settings = {}
    errors = []

    for name, typ, default, required in spec:
        raw = env.get(name)
        if raw is None or raw.strip() == "":
            if required:
                errors.append(f"{name} is required")
                continue
            settings[name.lower()] = default
            continue

        try:
            if typ is bool:
                settings[name.lower()] = _parse_bool(name, raw)
            elif typ is str:
                settings[name.lower()] = raw.strip()
            else:
                settings[name.lower()] = typ(raw.strip())
        except ValueError as exc:
            if typ is bool:
                errors.append(str(exc))
            else:
                errors.append(f"{name} must be of type {typ.__name__}, got {raw!r}")

    if errors:
        raise ValueError("Invalid configuration: " + "; ".join(errors))

    # Cross-field / range validation
    if not 1 <= settings["port"] <= 65535:
        errors.append("PORT must be between 1 and 65535")
    if settings["workers"] < 1:
        errors.append("WORKERS must be >= 1")
    if settings["timeout_seconds"] <= 0:
        errors.append("TIMEOUT_SECONDS must be > 0")

    settings["app_env"] = settings["app_env"].lower()
    if settings["app_env"] not in ("development", "staging", "production"):
        errors.append("APP_ENV must be one of development, staging, production")

    settings["log_level"] = settings["log_level"].upper()
    if settings["log_level"] not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        errors.append("LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")

    if settings["app_env"] == "production" and settings["debug"]:
        errors.append("DEBUG must not be enabled in production")
    if settings["app_env"] == "production" and not settings["database_url"]:
        errors.append("DATABASE_URL is required in production")

    if errors:
        raise ValueError("Invalid configuration: " + "; ".join(errors))

    return settings
