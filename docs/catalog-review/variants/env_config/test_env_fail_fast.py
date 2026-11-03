import pytest

from env_fail_fast import load_settings

GOOD = {"DATABASE_URL": "postgresql://app:s3cret@db/app"}


def test_defaults_and_values():
    assert load_settings(GOOD)["port"] == 8000
    env = {**GOOD, "PORT": "9000", "DEBUG": "on", "LOG_LEVEL": "error"}
    assert load_settings(env) == {"database_url": GOOD["DATABASE_URL"], "port": 9000,
                                  "debug": True, "log_level": "ERROR"}


def test_stops_at_first_error():
    with pytest.raises(ValueError) as info:
        load_settings({"DATABASE_URL": "nope", "PORT": "abc"})
    assert "DATABASE_URL" in str(info.value) and "PORT" not in str(info.value)


@pytest.mark.parametrize("env,msg", [({"PORT": "x"}, "integer"), ({"PORT": "0"}, "1-65535"),
                                     ({"DEBUG": "maybe"}, "boolean"), ({"LOG_LEVEL": "LOUD"}, "LOG_LEVEL")])
def test_each_invalid_value(env, msg):
    with pytest.raises(ValueError, match=msg):
        load_settings({**GOOD, **env})


def test_database_url_is_never_echoed():
    with pytest.raises(ValueError) as info:
        load_settings({"DATABASE_URL": "s3cret-password-without-scheme"})
    assert "s3cret" not in str(info.value)
