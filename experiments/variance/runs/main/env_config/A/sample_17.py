import os
from typing import Any, Callable, Dict, List, Optional


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"cannot interpret {value!r} as a boolean")


def _parse_list(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _read_setting(
    name: str,
    default: Any,
    parser: Callable[[str], Any],
    required: bool = False,
) -> Any:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        if required:
            raise ValueError(f"missing required environment variable: {name}")
        return default
    try:
        return parser(raw)
    except ValueError as exc:
        raise ValueError(f"invalid value for {name}: {exc}") from exc


def load_settings(env_prefix: str = "") -> Dict[str, Any]:
    """Load and validate application settings from environment variables.

    Each variable is looked up as ``<env_prefix><NAME>``. Missing or blank
    variables fall back to defaults. Invalid values raise ValueError.
    """

    def var(name: str) -> str:
        return f"{env_prefix}{name}"

    settings: Dict[str, Any] = {
        "app_name": _read_setting(var("APP_NAME"), "myapp", str.strip),
        "environment": _read_setting(var("ENVIRONMENT"), "development", lambda v: v.strip().lower()),
        "debug": _read_setting(var("DEBUG"), False, _parse_bool),
        "host": _read_setting(var("HOST"), "127.0.0.1", str.strip),
        "port": _read_setting(var("PORT"), 8000, int),
        "workers": _read_setting(var("WORKERS"), 1, int),
        "timeout_seconds": _read_setting(var("TIMEOUT_SECONDS"), 30.0, float),
        "log_level": _read_setting(var("LOG_LEVEL"), "INFO", lambda v: v.strip().upper()),
        "allowed_hosts": _read_setting(var("ALLOWED_HOSTS"), ["localhost"], _parse_list),
        "database_url": _read_setting(var("DATABASE_URL"), "sqlite:///app.db", str.strip),
        "secret_key": _read_setting(var("SECRET_KEY"), None, str, required=False),
    }

    errors: List[str] = []

    if settings["environment"] not in ("development", "staging", "production", "test"):
        errors.append(
            "ENVIRONMENT must be one of development, staging, production, test"
        )
    if not (1 <= settings["port"] <= 65535):
        errors.append("PORT must be between 1 and 65535")
    if settings["workers"] < 1:
        errors.append("WORKERS must be at least 1")
    if settings["timeout_seconds"] <= 0:
        errors.append("TIMEOUT_SECONDS must be greater than 0")
    if settings["log_level"] not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        errors.append("LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")
    if not settings["app_name"]:
        errors.append("APP_NAME must not be empty")
    if settings["environment"] == "production":
        if settings["debug"]:
            errors.append("DEBUG must be false in production")
        if not settings["secret_key"]:
            errors.append("SECRET_KEY is required in production")

    if errors:
        raise ValueError("invalid settings: " + "; ".join(errors))

    return settings
