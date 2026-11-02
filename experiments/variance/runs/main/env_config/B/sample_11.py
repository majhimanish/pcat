import os


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_ENVIRONMENTS = {"development", "staging", "production", "test"}


def _parse_bool(name, raw):
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(
        f"{name} must be a boolean (one of "
        f"{sorted(_TRUE_VALUES | _FALSE_VALUES)}), got {raw!r}"
    )


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
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be a finite number, got {raw!r}")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _parse_choice(name, raw, choices, normalize):
    value = normalize(raw.strip())
    if value not in choices:
        raise ValueError(f"{name} must be one of {sorted(choices)}, got {raw!r}")
    return value


def _parse_list(raw):
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_config(env=None):
    """Load, default, and validate app configuration from environment variables.

    Args:
        env: Optional mapping to read from (defaults to os.environ).

    Returns:
        A dict of validated configuration values.

    Raises:
        ValueError: If any variables are missing or invalid. All problems are
            reported together in a single error message.
    """
    env = os.environ if env is None else env
    errors = []
    config = {}

    def get(name, default=None, required=False):
        raw = env.get(name)
        if raw is None or raw.strip() == "":
            if required:
                errors.append(f"{name} is required but not set")
                return None
            return default
        return raw

    def parse(name, parser, default=None, required=False, **kwargs):
        raw = get(name, required=required)
        if raw is None:
            return default
        try:
            return parser(name, raw, **kwargs)
        except ValueError as exc:
            errors.append(str(exc))
            return default

    # Required values
    config["DATABASE_URL"] = get("DATABASE_URL", required=True)
    config["SECRET_KEY"] = get("SECRET_KEY", required=True)

    # Optional values with defaults
    config["APP_ENV"] = parse(
        "APP_ENV", _parse_choice, default="development",
        choices=_ENVIRONMENTS, normalize=str.lower,
    )
    config["LOG_LEVEL"] = parse(
        "LOG_LEVEL", _parse_choice, default="INFO",
        choices=_LOG_LEVELS, normalize=str.upper,
    )
    config["HOST"] = get("HOST", default="127.0.0.1")
    config["PORT"] = parse("PORT", _parse_int, default=8000, minimum=1, maximum=65535)
    config["DEBUG"] = parse("DEBUG", _parse_bool, default=False)
    config["WORKERS"] = parse("WORKERS", _parse_int, default=1, minimum=1, maximum=256)
    config["REQUEST_TIMEOUT"] = parse(
        "REQUEST_TIMEOUT", _parse_float, default=30.0, minimum=0.0
    )
    config["ALLOWED_HOSTS"] = _parse_list(get("ALLOWED_HOSTS", default="localhost"))

    # Cross-field validation
    if config["APP_ENV"] == "production":
        if config["DEBUG"]:
            errors.append("DEBUG must not be enabled when APP_ENV is 'production'")
        secret = config["SECRET_KEY"]
        if secret is not None and len(secret) < 32:
            errors.append("SECRET_KEY must be at least 32 characters in production")

    if errors:
        raise ValueError(
            "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return config
