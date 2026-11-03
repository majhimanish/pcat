import pytest

from env_collect_errors import load_settings

GOOD = {"DATABASE_URL": "postgresql://app:s3cret@db/app"}


def test_defaults():
    assert load_settings(GOOD) == {"database_url": GOOD["DATABASE_URL"], "port": 8000,
                                   "debug": False, "log_level": "INFO"}


def test_parses_values():
    env = {**GOOD, "PORT": "9000", "DEBUG": "Yes", "LOG_LEVEL": "warning"}
    assert load_settings(env) == {"database_url": GOOD["DATABASE_URL"], "port": 9000,
                                  "debug": True, "log_level": "WARNING"}


def test_reports_all_errors_at_once():
    with pytest.raises(ValueError) as info:
        load_settings({"DATABASE_URL": "nope", "PORT": "abc", "DEBUG": "maybe", "LOG_LEVEL": "LOUD"})
    message = str(info.value)
    for fragment in ("DATABASE_URL", "PORT must be an integer", "DEBUG", "LOG_LEVEL"):
        assert fragment in message
    assert message.count("\n- ") == 4


def test_port_range_and_missing_database_url():
    with pytest.raises(ValueError, match="1-65535"):
        load_settings({**GOOD, "PORT": "70000"})
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        load_settings({})


def test_database_url_is_never_echoed():
    with pytest.raises(ValueError) as info:
        load_settings({"DATABASE_URL": "s3cret-password-without-scheme"})
    assert "s3cret" not in str(info.value)


def test_reads_os_environ_by_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///x.db")
    monkeypatch.setenv("PORT", "1234")
    assert load_settings()["port"] == 1234
