import os

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(name, raw):
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(
        f"Invalid boolean for {name}: {raw!r} "
        f"(expected one of {sorted(_TRUE_VALUES | _FALSE_VALUES)})"
    )


def _parse_port(name, raw):
    try:
        port = int(raw.strip())
    except ValueError:
        raise ValueError(f"Invalid integer for {name}: {raw!r}") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535, got {port}")
    return port


def _parse_database_url(name, raw):
    url = raw.strip()
    if not url:
        raise ValueError(f"{name} must not be empty")
    scheme, sep, rest = url.partition("://")
    if not sep or not scheme or not rest:
        raise ValueError(f"Invalid database URL for {name}: expected 'scheme://...'")
    return url


def load_settings(env=None):
    """Load application settings from environment variables.

    Variables (defaults in parentheses):
        DATABASE_URL (sqlite:///app.db)
        PORT         (8000)
        DEBUG        (false)

    Missing variables fall back to defaults; invalid values raise ValueError.
    """
    if env is None:
        env = os.environ

    defaults = {
        "DATABASE_URL": "sqlite:///app.db",
        "PORT": "8000",
        "DEBUG": "false",
    }

    def get(name):
        raw = env.get(name)
        return defaults[name] if raw is None else raw

    return {
        "database_url": _parse_database_url("DATABASE_URL", get("DATABASE_URL")),
        "port": _parse_port("PORT", get("PORT")),
        "debug": _parse_bool("DEBUG", get("DEBUG")),
    }
