import pytest

from env_schema_loader import load_settings, parse_bool

SCHEMA = {"DATABASE_URL": (str, ...), "PORT": (int, 8000), "DEBUG": (parse_bool, False)}


def test_defaults_and_parsing():
    assert load_settings(SCHEMA, {"DATABASE_URL": "sqlite://"}) == {
        "database_url": "sqlite://", "port": 8000, "debug": False}
    assert load_settings(SCHEMA, {"DATABASE_URL": "x", "PORT": "1", "DEBUG": "true"})["debug"] is True


def test_reports_all_errors_including_missing_required():
    with pytest.raises(ValueError) as info:
        load_settings(SCHEMA, {"PORT": "abc", "DEBUG": "maybe"})
    message = str(info.value)
    assert "DATABASE_URL is required" in message and "PORT:" in message and "DEBUG:" in message


def test_secret_values_are_not_echoed():
    schema = {"API_TOKEN": (int, ...)}
    with pytest.raises(ValueError) as info:
        load_settings(schema, {"API_TOKEN": "tok-s3cret"}, secret_names=("API_TOKEN",))
    assert "s3cret" not in str(info.value) and "API_TOKEN: invalid value" in str(info.value)


def test_custom_parser_and_empty_schema():
    def port(raw):
        value = int(raw)
        if not 1 <= value <= 65535:
            raise ValueError("out of range")
        return value

    with pytest.raises(ValueError, match="out of range"):
        load_settings({"PORT": (port, 80)}, {"PORT": "0"})
    assert load_settings({}, {}) == {}


def test_parse_bool():
    assert [parse_bool(v) for v in ("1", "TRUE", " yes ", "On", "0", "off")] == [True] * 4 + [False] * 2
    with pytest.raises(ValueError):
        parse_bool("2")
