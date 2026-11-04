import pytest

from impl import load_settings, parse_bool


def port(raw):
    value = int(raw)
    if not 1 <= value <= 65535:
        raise ValueError("must be 1-65535")
    return value


SCHEMA = {
    "DATABASE_URL": (str, ...),
    "PORT": (port, 8000),
    "DEBUG": (parse_bool, False),
    "WORKERS": (int, None),
}


# Normal cases ---------------------------------------------------------------
def test_defaults_applied_for_missing_values():
    assert load_settings(SCHEMA, {"DATABASE_URL": "sqlite://"}) == {
        "database_url": "sqlite://", "port": 8000, "debug": False, "workers": None}


def test_values_parsed():
    env = {"DATABASE_URL": "postgresql://db/app", "PORT": "9000", "DEBUG": "yes", "WORKERS": "4"}
    assert load_settings(SCHEMA, env) == {
        "database_url": "postgresql://db/app", "port": 9000, "debug": True, "workers": 4}


def test_reads_os_environ_by_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///x.db")
    monkeypatch.setenv("PORT", "1234")
    assert load_settings(SCHEMA)["port"] == 1234


def test_extra_environment_variables_are_ignored():
    assert set(load_settings(SCHEMA, {"DATABASE_URL": "x", "HOME": "/root"})) == {
        "database_url", "port", "debug", "workers"}


# Edge cases -----------------------------------------------------------------------
def test_empty_schema_and_empty_string_value():
    assert load_settings({}, {"ANY": "1"}) == {}
    assert load_settings({"NAME": (str, "default")}, {"NAME": ""}) == {"name": ""}


def test_parse_bool_accepts_common_spellings():
    assert [parse_bool(v) for v in ("1", "TRUE", " yes ", "On")] == [True] * 4
    assert [parse_bool(v) for v in ("0", "False", "no", " OFF")] == [False] * 4
    for bad in ("2", "", "y", "enabled"):
        with pytest.raises(ValueError):
            parse_bool(bad)


# Failure cases ------------------------------------------------------------------------
def test_reports_every_problem_at_once():
    with pytest.raises(ValueError) as info:
        load_settings(SCHEMA, {"PORT": "99999", "DEBUG": "maybe", "WORKERS": "four"})
    message = str(info.value)
    assert message.startswith("invalid configuration:")
    for fragment in ("DATABASE_URL is required", "PORT: must be 1-65535", "DEBUG:", "WORKERS:"):
        assert fragment in message
    assert message.count("\n- ") == 4


def test_parser_type_errors_are_reported_not_raised():
    def strict(raw):
        raise TypeError("not supported")

    with pytest.raises(ValueError, match="X: not supported"):
        load_settings({"X": (strict, 1)}, {"X": "a"})


# Security ---------------------------------------------------------------------------
def test_secret_values_never_appear_in_errors():
    schema = {"API_TOKEN": (int, ...), "DB_PASSWORD": (port, ...)}
    with pytest.raises(ValueError) as info:
        load_settings(schema, {"API_TOKEN": "tok-s3cret", "DB_PASSWORD": "hunter2"},
                      secret_names=("API_TOKEN", "DB_PASSWORD"))
    message = str(info.value)
    assert "s3cret" not in message and "hunter2" not in message
    assert "API_TOKEN: invalid value" in message and "DB_PASSWORD: invalid value" in message


def test_non_secret_errors_keep_the_parser_message():
    with pytest.raises(ValueError, match="invalid literal for int"):
        load_settings({"N": (int, 0)}, {"N": "x"})
