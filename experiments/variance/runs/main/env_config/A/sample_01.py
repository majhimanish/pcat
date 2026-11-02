import os


def _parse_bool(name, raw):
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {raw!r}")


def _parse_int(name, raw, minimum=None, maximum=None):
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}, got {value}")
    return value


def _parse_float(name, raw, minimum=None):
    try:
        value = float(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _parse_choice(name, raw, choices):
    value = raw.strip().lower()
    if value not in choices:
        raise ValueError(f"{name} must be one of {sorted(choices)}, got {raw!r}")
    return value


def load_settings(env=None):
    """Load and validate application settings from environment variables.

    Reads from os.environ unless a mapping is supplied via `env`.
    Missing or empty variables fall back to defaults. Invalid values
    raise ValueError with all problems reported together.

    Variables (default):
        APP_HOST        (127.0.0.1)  non-empty string
        APP_PORT        (8000)       integer, 1-65535
        APP_DEBUG       (false)      boolean
        APP_LOG_LEVEL   (info)       debug|info|warning|error|critical
        APP_TIMEOUT     (30.0)       float seconds, >= 0
        APP_MAX_WORKERS (4)          integer, >= 1
        APP_ALLOWED_HOSTS (localhost) comma-separated list
        APP_SECRET_KEY  (required when APP_DEBUG is false)
    """
    env = os.environ if env is None else env
    errors = []
    settings = {}

    def get(name, default, parser):
        raw = env.get(name)
        if raw is None or raw.strip() == "":
            settings[name] = default
            return
        try:
            settings[name] = parser(raw)
        except ValueError as exc:
            errors.append(str(exc))

    get("APP_HOST", "127.0.0.1", lambda r: r.strip())
    get("APP_PORT", 8000, lambda r: _parse_int("APP_PORT", r, 1, 65535))
    get("APP_DEBUG", False, lambda r: _parse_bool("APP_DEBUG", r))
    get(
        "APP_LOG_LEVEL",
        "info",
        lambda r: _parse_choice(
            "APP_LOG_LEVEL", r, {"debug", "info", "warning", "error", "critical"}
        ),
    )
    get("APP_TIMEOUT", 30.0, lambda r: _parse_float("APP_TIMEOUT", r, 0.0))
    get("APP_MAX_WORKERS", 4, lambda r: _parse_int("APP_MAX_WORKERS", r, 1))
    get(
        "APP_ALLOWED_HOSTS",
        ["localhost"],
        lambda r: [h.strip() for h in r.split(",") if h.strip()],
    )

    secret = (env.get("APP_SECRET_KEY") or "").strip()
    if not secret and not settings.get("APP_DEBUG", False):
        errors.append("APP_SECRET_KEY is required when APP_DEBUG is false")
    settings["APP_SECRET_KEY"] = secret or None

    if errors:
        raise ValueError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return settings
