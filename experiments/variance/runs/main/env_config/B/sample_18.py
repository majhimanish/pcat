import os

DEFAULT_DATABASE_URL = "sqlite:///app.db"
DEFAULT_PORT = 8000
DEFAULT_DEBUG = False

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_port(raw):
    try:
        port = int(raw.strip())
    except ValueError:
        raise ValueError(f"Invalid PORT {raw!r}: must be an integer") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"Invalid PORT {port}: must be between 1 and 65535")
    return port


def _parse_bool(name, raw):
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(
        f"Invalid {name} {raw!r}: expected one of "
        f"{sorted(_TRUE_VALUES | _FALSE_VALUES)}"
    )


def _parse_database_url(raw):
    url = raw.strip()
    if not url:
        raise ValueError("Invalid DATABASE_URL: must not be empty")
    scheme, sep, rest = url.partition("://")
    if not sep or not scheme or not rest:
        raise ValueError(
            f"Invalid DATABASE_URL {url!r}: expected format 'scheme://...'"
        )
    return url


def load_settings(env=None):
    """Load settings from the environment (or the given mapping).

    Missing variables fall back to defaults; invalid values raise ValueError.
    """
    if env is None:
        env = os.environ

    raw_url = env.get("DATABASE_URL")
    raw_port = env.get("PORT")
    raw_debug = env.get("DEBUG")

    return {
        "database_url": (
            DEFAULT_DATABASE_URL if raw_url is None else _parse_database_url(raw_url)
        ),
        "port": DEFAULT_PORT if raw_port is None else _parse_port(raw_port),
        "debug": (
            DEFAULT_DEBUG if raw_debug is None else _parse_bool("DEBUG", raw_debug)
        ),
    }
