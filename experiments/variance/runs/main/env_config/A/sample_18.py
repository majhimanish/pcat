import os
from typing import Any, Dict, Optional


class ConfigError(ValueError):
    """Raised when one or more settings fail validation."""


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}


def parse_bool(value: str) -> bool:
    """Parse a string into a boolean, raising ValueError if unrecognized."""
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"not a valid boolean: {value!r}")


def load_settings(env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Load and validate application settings from environment variables.

    Supported variables (defaults in parentheses):
      APP_ENV        one of development|staging|production (development)
      APP_HOST       hostname or IP to bind to (127.0.0.1)
      APP_PORT       integer in 1..65535 (8000)
      APP_DEBUG      boolean (false in non-production, forced false in production)
      APP_TIMEOUT    positive float, seconds (30.0)
      APP_WORKERS    integer >= 1 (4)
      APP_LOG_LEVEL  DEBUG|INFO|WARNING|ERROR|CRITICAL (INFO)
      DATABASE_URL   required in production; defaults to sqlite:///app.db otherwise
      SECRET_KEY     required in production; min 16 chars when provided

    Args:
        env: Optional mapping to read from instead of os.environ (useful for tests).

    Returns:
        A dict of validated, correctly-typed settings.

    Raises:
        ConfigError: listing every invalid or missing setting.
    """
    source = os.environ if env is None else env
    errors = []
    settings: Dict[str, Any] = {}

    def get(name: str) -> Optional[str]:
        raw = source.get(name)
        if raw is None:
            return None
        raw = raw.strip()
        return raw if raw != "" else None

    # APP_ENV
    app_env = (get("APP_ENV") or "development").lower()
    allowed_envs = {"development", "staging", "production"}
    if app_env not in allowed_envs:
        errors.append(f"APP_ENV must be one of {sorted(allowed_envs)}, got {app_env!r}")
        app_env = "development"
    settings["env"] = app_env
    is_prod = app_env == "production"

    # APP_HOST
    settings["host"] = get("APP_HOST") or "127.0.0.1"

    # APP_PORT
    raw_port = get("APP_PORT")
    port = 8000
    if raw_port is not None:
        try:
            port = int(raw_port)
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            errors.append(f"APP_PORT must be an integer in 1..65535, got {raw_port!r}")
            port = 8000
    settings["port"] = port

    # APP_DEBUG
    raw_debug = get("APP_DEBUG")
    debug = False
    if raw_debug is not None:
        try:
            debug = parse_bool(raw_debug)
        except ValueError:
            errors.append(f"APP_DEBUG must be a boolean, got {raw_debug!r}")
    if is_prod and debug:
        errors.append("APP_DEBUG must not be enabled in production")
        debug = False
    settings["debug"] = debug

    # APP_TIMEOUT
    raw_timeout = get("APP_TIMEOUT")
    timeout = 30.0
    if raw_timeout is not None:
        try:
            timeout = float(raw_timeout)
            if not timeout > 0 or timeout == float("inf"):
                raise ValueError
        except ValueError:
            errors.append(f"APP_TIMEOUT must be a positive finite number, got {raw_timeout!r}")
            timeout = 30.0
    settings["timeout"] = timeout

    # APP_WORKERS
    raw_workers = get("APP_WORKERS")
    workers = 4
    if raw_workers is not None:
        try:
            workers = int(raw_workers)
            if workers < 1:
                raise ValueError
        except ValueError:
            errors.append(f"APP_WORKERS must be an integer >= 1, got {raw_workers!r}")
            workers = 4
    settings["workers"] = workers

    # APP_LOG_LEVEL
    log_level = (get("APP_LOG_LEVEL") or "INFO").upper()
    allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level not in allowed_levels:
        errors.append(f"APP_LOG_LEVEL must be one of {sorted(allowed_levels)}, got {log_level!r}")
        log_level = "INFO"
    settings["log_level"] = log_level

    # DATABASE_URL
    database_url = get("DATABASE_URL")
    if database_url is None:
        if is_prod:
            errors.append("DATABASE_URL is required in production")
        database_url = "sqlite:///app.db"
    elif "://" not in database_url:
        errors.append("DATABASE_URL must be a URL such as 'postgresql://user:pass@host/db'")
    settings["database_url"] = database_url

    # SECRET_KEY
    secret_key = get("SECRET_KEY")
    if secret_key is None:
        if is_prod:
            errors.append("SECRET_KEY is required in production")
    elif len(secret_key) < 16:
        errors.append("SECRET_KEY must be at least 16 characters")
    settings["secret_key"] = secret_key

    if errors:
        raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return settings
