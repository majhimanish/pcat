"""Load typed settings from environment variables; stop at the first problem.

Standard library only. Fields: DATABASE_URL, PORT, DEBUG, LOG_LEVEL.
"""

import os
from collections.abc import Mapping
from typing import Any

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"expected a boolean, got {raw!r}")


def load_settings(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return {"database_url", "port", "debug", "log_level"}; raise ValueError on the first error."""
    env = os.environ if env is None else env
    database_url = env.get("DATABASE_URL", "").strip()
    if "://" not in database_url:
        raise ValueError("DATABASE_URL is required and must look like scheme://...")  # value not echoed
    try:
        port = int(env.get("PORT", "8000"))
    except ValueError:
        raise ValueError(f"PORT must be an integer, got {env.get('PORT')!r}") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"PORT must be 1-65535, got {port}")
    debug = parse_bool(env.get("DEBUG", "false"))
    log_level = env.get("LOG_LEVEL", "INFO").strip().upper()
    if log_level not in LOG_LEVELS:
        raise ValueError(f"LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}")
    return {"database_url": database_url, "port": port, "debug": debug, "log_level": log_level}
