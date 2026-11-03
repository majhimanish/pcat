"""Load typed settings from environment variables; report every problem at once.

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
    """Return the settings dict; raise ValueError listing every problem."""
    env = os.environ if env is None else env
    errors: list[str] = []
    settings: dict[str, Any] = {"database_url": env.get("DATABASE_URL", "").strip()}
    if "://" not in settings["database_url"]:
        # The value is never echoed: it usually contains a password.
        errors.append("DATABASE_URL is required and must look like scheme://...")
    try:
        settings["port"] = int(env.get("PORT", "8000"))
        if not 1 <= settings["port"] <= 65535:
            errors.append(f"PORT must be 1-65535, got {settings['port']}")
    except ValueError:
        errors.append(f"PORT must be an integer, got {env.get('PORT')!r}")
    try:
        settings["debug"] = parse_bool(env.get("DEBUG", "false"))
    except ValueError as exc:
        errors.append(f"DEBUG: {exc}")
    settings["log_level"] = env.get("LOG_LEVEL", "INFO").strip().upper()
    if settings["log_level"] not in LOG_LEVELS:
        errors.append(f"LOG_LEVEL must be one of {', '.join(LOG_LEVELS)}")
    if errors:
        raise ValueError("invalid configuration:\n- " + "\n- ".join(errors))
    return settings
