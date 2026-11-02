import os
from typing import Any, Mapping, Optional


class ConfigError(ValueError):
    """Raised when one or more configuration values are invalid."""


_VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_VALID_ENVIRONMENTS = ("development", "staging", "production", "test")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ValueError(f"expected a boolean (true/false), got {raw!r}")


def _parse_int(raw: str, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"expected an integer, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ValueError(f"must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"must be <= {maximum}, got {value}")
    return value


def _parse_float(raw: str, minimum: Optional[float] = None) -> float:
    try:
        value = float(raw.strip())
    except ValueError:
        raise ValueError(f"expected a number, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ValueError(f"must be >= {minimum}, got {value}")
    return value


def _parse_choice(raw: str, choices: tuple, case: str = "lower") -> str:
    value = raw.strip()
    value = value.upper() if case == "upper" else value.lower()
    if value not in choices:
        raise ValueError(f"must be one of {', '.join(choices)}, got {raw!r}")
    return value


def _parse_nonempty(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("must not be empty")
    return value


def _parse_url(raw: str) -> str:
    value = raw.strip()
    if not value.startswith(("http://", "https://")):
        raise ValueError(f"must start with http:// or https://, got {raw!r}")
    return value


def _parse_list(raw: str) -> list:
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_config(env: Optional[Mapping[str, str]] = None, prefix: str = "APP_") -> dict:
    """
    Load configuration from environment variables, apply defaults, and validate.

    Each setting is read as ``<prefix><NAME>`` (default prefix ``APP_``).
    Required settings without a value, and any invalid values, are collected
    and reported together in a single ConfigError.

    Supported settings:
        APP_ENV            development|staging|production|test (default: development)
        APP_DEBUG          boolean (default: false; forced false in production)
        APP_HOST           non-empty string (default: 127.0.0.1)
        APP_PORT           integer 1-65535 (default: 8000)
        APP_LOG_LEVEL      DEBUG|INFO|WARNING|ERROR|CRITICAL (default: INFO)
        APP_DATABASE_URL   non-empty string (REQUIRED)
        APP_API_BASE_URL   http(s) URL (default: http://localhost:8080)
        APP_SECRET_KEY     string, min 16 chars (REQUIRED in production)
        APP_TIMEOUT_SECONDS float >= 0 (default: 30.0)
        APP_MAX_WORKERS    integer 1-256 (default: 4)
        APP_ALLOWED_HOSTS  comma-separated list (default: localhost)
    """
    source = os.environ if env is None else env
    errors = []
    config: dict[str, Any] = {}

    def get(name: str) -> Optional[str]:
        raw = source.get(f"{prefix}{name}")
        if raw is None or raw.strip() == "":
            return None
        return raw

    def read(name: str, parser, default: Any = None, required: bool = False) -> None:
        key = name.lower()
        raw = get(name)
        if raw is None:
            if required:
                errors.append(f"{prefix}{name}: required but not set")
            config[key] = default
            return
        try:
            config[key] = parser(raw)
        except ValueError as exc:
            errors.append(f"{prefix}{name}: {exc}")
            config[key] = default

    read("ENV", lambda r: _parse_choice(r, _VALID_ENVIRONMENTS), default="development")
    read("DEBUG", _parse_bool, default=False)
    read("HOST", _parse_nonempty, default="127.0.0.1")
    read("PORT", lambda r: _parse_int(r, 1, 65535), default=8000)
    read("LOG_LEVEL", lambda r: _parse_choice(r, _VALID_LOG_LEVELS, case="upper"), default="INFO")
    read("DATABASE_URL", _parse_nonempty, required=True)
    read("API_BASE_URL", _parse_url, default="http://localhost:8080")
    read("TIMEOUT_SECONDS", lambda r: _parse_float(r, 0.0), default=30.0)
    read("MAX_WORKERS", lambda r: _parse_int(r, 1, 256), default=4)
    read("ALLOWED_HOSTS", _parse_list, default=["localhost"])

    is_production = config["env"] == "production"
    read(
        "SECRET_KEY",
        lambda r: r.strip() if len(r.strip()) >= 16 else (_ for _ in ()).throw(
            ValueError("must be at least 16 characters")
        ),
        default=None,
        required=is_production,
    )

    # Cross-field validation
    if is_production and config["debug"]:
        errors.append(f"{prefix}DEBUG: must not be enabled when {prefix}ENV=production")
        config["debug"] = False

    if errors:
        raise ConfigError(
            "Invalid configuration:\n  - " + "\n  - ".join(errors)
        )

    return config
