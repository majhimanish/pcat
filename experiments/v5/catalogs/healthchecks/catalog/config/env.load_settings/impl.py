"""Load settings described by a caller-supplied schema; report every problem at once.

Standard library only. schema = {"PORT": (int, 8000), "DATABASE_URL": (str, ...), ...}
maps each variable to (parser, default); a default of ... makes it required.
"""

import os
from collections.abc import Callable, Mapping
from typing import Any


def parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"expected a boolean, got {raw!r}")


def load_settings(schema: Mapping[str, tuple[Callable[[str], Any], Any]],
                  env: Mapping[str, str] | None = None,
                  secret_names: tuple[str, ...] = ()) -> dict[str, Any]:
    """Return {lower-cased name: parsed value}; raise ValueError listing all errors.

    Values of variables in `secret_names` are never included in error messages.
    """
    env = os.environ if env is None else env
    settings: dict[str, Any] = {}
    errors: list[str] = []
    for name, (parser, default) in schema.items():
        raw = env.get(name)
        if raw is None:
            if default is ...:
                errors.append(f"{name} is required")
            else:
                settings[name.lower()] = default
            continue
        try:
            settings[name.lower()] = parser(raw)
        except (ValueError, TypeError) as exc:
            errors.append(f"{name}: invalid value" if name in secret_names else f"{name}: {exc}")
    if errors:
        raise ValueError("invalid configuration:\n- " + "\n- ".join(errors))
    return settings
