import os


def _parse_bool(name, raw):
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {raw!r}")


def _parse_int(name, raw, min_value=None, max_value=None):
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be <= {max_value}, got {value}")
    return value


def _parse_float(name, raw, min_value=None, max_value=None):
    try:
        value = float(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be <= {max_value}, got {value}")
    return value


def _parse_choice(name, raw, choices):
    value = raw.strip().lower()
    if value not in choices:
        raise ValueError(f"{name} must be one of {sorted(choices)}, got {raw!r}")
    return value


def _parse_list(raw):
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_settings(env=None, prefix="APP_"):
    """Load and validate settings from environment variables.

    Reads variables named ``<prefix><KEY>`` (e.g. APP_PORT), falling back to
    defaults when unset or empty. Collects all validation problems and raises
    a single ValueError listing every one of them.

    Args:
        env: Mapping to read from (defaults to os.environ).
        prefix: Prefix applied to every variable name.

    Returns:
        dict of validated settings.
    """
    env = os.environ if env is None else env

    def get(key):
        raw = env.get(prefix + key)
        if raw is None or raw.strip() == "":
            return None
        return raw

    # (key, default, parser)
    spec = [
        ("HOST", "127.0.0.1", lambda n, r: r.strip()),
        ("PORT", 8000, lambda n, r: _parse_int(n, r, 1, 65535)),
        ("DEBUG", False, _parse_bool),
        ("LOG_LEVEL", "info",
         lambda n, r: _parse_choice(
             n, r, {"debug", "info", "warning", "error", "critical"})),
        ("TIMEOUT_SECONDS", 30.0, lambda n, r: _parse_float(n, r, 0.0)),
        ("MAX_WORKERS", 4, lambda n, r: _parse_int(n, r, 1, 256)),
        ("ALLOWED_HOSTS", ["localhost"], lambda n, r: _parse_list(r)),
        ("DATABASE_URL", "sqlite:///app.db", lambda n, r: r.strip()),
    ]

    settings = {}
    errors = []

    for key, default, parser in spec:
        name = prefix + key
        raw = get(key)
        if raw is None:
            settings[key.lower()] = list(default) if isinstance(default, list) else default
            continue
        try:
            settings[key.lower()] = parser(name, raw)
        except ValueError as exc:
            errors.append(str(exc))

    # Cross-field validation
    if not errors:
        if not settings["allowed_hosts"]:
            errors.append(f"{prefix}ALLOWED_HOSTS must contain at least one host")
        if "://" not in settings["database_url"]:
            errors.append(
                f"{prefix}DATABASE_URL must be a URL like 'scheme://...', "
                f"got {settings['database_url']!r}"
            )

    if errors:
        raise ValueError(
            "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return settings
