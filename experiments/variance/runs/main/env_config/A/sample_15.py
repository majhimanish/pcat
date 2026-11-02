import os
from typing import Any


def _parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"{name} must be a boolean (true/false), got {raw!r}")


def _parse_int(name: str, raw: str) -> int:
    try:
        return int(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None


def _parse_float(name: str, raw: str) -> float:
    try:
        return float(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None


def load_settings(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Load and validate application settings from environment variables.

    Reads from `env` if provided, otherwise from os.environ. Missing or empty
    variables fall back to defaults. Raises ValueError listing every invalid
    setting.
    """
    source = os.environ if env is None else env
    errors: list[str] = []
    settings: dict[str, Any] = {}

    # (name, default, parser)
    spec = [
        ("APP_ENV", "development", str),
        ("APP_HOST", "127.0.0.1", str),
        ("APP_PORT", 8000, _parse_int),
        ("APP_DEBUG", False, _parse_bool),
        ("APP_TIMEOUT", 30.0, _parse_float),
        ("APP_WORKERS", 1, _parse_int),
        ("APP_LOG_LEVEL", "INFO", str),
        ("DATABASE_URL", "sqlite:///app.db", str),
    ]

    for name, default, parser in spec:
        raw = source.get(name)
        if raw is None or raw.strip() == "":
            settings[name] = default
            continue
        try:
            settings[name] = raw.strip() if parser is str else parser(name, raw)
        except ValueError as exc:
            errors.append(str(exc))

    # Semantic validation (only on values that parsed successfully)
    allowed_envs = {"development", "staging", "production", "test"}
    if "APP_ENV" in settings and settings["APP_ENV"] not in allowed_envs:
        errors.append(
            f"APP_ENV must be one of {sorted(allowed_envs)}, got {settings['APP_ENV']!r}"
        )

    port = settings.get("APP_PORT")
    if isinstance(port, int) and not 1 <= port <= 65535:
        errors.append(f"APP_PORT must be between 1 and 65535, got {port}")

    timeout = settings.get("APP_TIMEOUT")
    if isinstance(timeout, float) and timeout <= 0:
        errors.append(f"APP_TIMEOUT must be positive, got {timeout}")

    workers = settings.get("APP_WORKERS")
    if isinstance(workers, int) and workers < 1:
        errors.append(f"APP_WORKERS must be at least 1, got {workers}")

    if "APP_LOG_LEVEL" in settings:
        level = settings["APP_LOG_LEVEL"].upper()
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed_levels:
            errors.append(
                f"APP_LOG_LEVEL must be one of {sorted(allowed_levels)}, got {level!r}"
            )
        else:
            settings["APP_LOG_LEVEL"] = level

    if settings.get("APP_ENV") == "production" and settings.get("APP_DEBUG") is True:
        errors.append("APP_DEBUG must not be enabled when APP_ENV is 'production'")

    if errors:
        raise ValueError("Invalid configuration:\n  - " + "\n  - ".join(errors))

    return settings
