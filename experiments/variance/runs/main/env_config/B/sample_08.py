import os


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

DEFAULT_DATABASE_URL = "sqlite:///app.db"
DEFAULT_PORT = 8000
DEFAULT_DEBUG = False


def _get_env(env, name):
    """Return the stripped value of an environment variable, or None if unset/blank."""
    value = env.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _parse_port(raw):
    try:
        port = int(raw)
    except ValueError:
        raise ValueError(f"Invalid PORT {raw!r}: must be an integer") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"Invalid PORT {port}: must be between 1 and 65535")
    return port


def _parse_bool(name, raw):
    lowered = raw.lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise ValueError(
        f"Invalid {name} {raw!r}: expected one of "
        f"{sorted(_TRUE_VALUES | _FALSE_VALUES)}"
    )


def _validate_database_url(url):
    scheme, sep, rest = url.partition("://")
    if not sep or not scheme or not rest:
        raise ValueError(
            "Invalid DATABASE_URL: expected format 'scheme://...' "
            "(e.g. 'postgresql://user:pass@host:5432/db')"
        )
    return url


def load_settings(env=None):
    """Load application settings from environment variables.

    Variables:
        DATABASE_URL  Database connection URL (default: sqlite:///app.db)
        PORT          TCP port, 1-65535 (default: 8000)
        DEBUG         Boolean flag: 1/0, true/false, yes/no, on/off (default: false)

    Missing or blank variables fall back to defaults; present but invalid
    values raise ValueError.
    """
    if env is None:
        env = os.environ

    raw_url = _get_env(env, "DATABASE_URL")
    raw_port = _get_env(env, "PORT")
    raw_debug = _get_env(env, "DEBUG")

    database_url = (
        DEFAULT_DATABASE_URL if raw_url is None else _validate_database_url(raw_url)
    )
    port = DEFAULT_PORT if raw_port is None else _parse_port(raw_port)
    debug = DEFAULT_DEBUG if raw_debug is None else _parse_bool("DEBUG", raw_debug)

    return {
        "database_url": database_url,
        "port": port,
        "debug": debug,
    }
