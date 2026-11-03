import io
import time

import pytest

from csv_text_stream import import_users

CSV = """name,email,age
Ada,ADA@example.com,36
,bob@example.com,20
Cy,not-an-email,
Di,ada@example.com,40
Ed,ed@example.com,abc
Flo,flo@example.com,
Gus,gus@example.com,30,extra
"""


def test_valid_rows_and_per_row_errors():
    valid, errors = import_users(CSV)
    assert valid == [{"name": "Ada", "email": "ada@example.com", "age": 36},
                     {"name": "Flo", "email": "flo@example.com", "age": None}]
    assert errors == [
        {"row": 3, "errors": ["name is required"]},
        {"row": 4, "errors": ["email is invalid"]},
        {"row": 5, "errors": ["duplicate email"]},
        {"row": 6, "errors": ["age must be a whole number from 0 to 150"]},
        {"row": 8, "errors": ["too many fields"]},
    ]


def test_accepts_a_text_stream_and_bom_and_header_case():
    valid, errors = import_users(io.StringIO("\ufeffName,EMAIL\nZed,zed@example.org\n"))
    assert valid == [{"name": "Zed", "email": "zed@example.org", "age": None}] and errors == []


def test_missing_columns_and_empty_input():
    assert import_users("name,age\nA,1\n") == ([], [{"row": 1, "errors": ["missing columns: email"]}])
    assert import_users("") == ([], [{"row": 1, "errors": ["missing columns: name, email"]}])


def test_multiple_problems_in_one_row_and_age_bounds():
    valid, errors = import_users("name,email,age\n,bad,151\nOk,ok@x.io,0\n")
    assert errors == [{"row": 2, "errors": ["name is required", "email is invalid",
                                            "age must be a whole number from 0 to 150"]}]
    assert valid[0]["age"] == 0


def test_row_limit():
    rows = "".join(f"u{i},u{i}@example.com,1\n" for i in range(5))
    valid, errors = import_users("name,email,age\n" + rows, max_rows=3)
    assert len(valid) == 3 and errors == [{"row": 5, "errors": ["more than 3 rows; stopped"]}]


def test_values_are_not_echoed_and_hostile_email_is_fast():
    hostile = "a@" + "a" * 50000
    start = time.perf_counter()
    _, errors = import_users(f"name,email\nX,{hostile}\n")
    assert time.perf_counter() - start < 1.0
    assert errors == [{"row": 2, "errors": ["email is invalid"]}]
    assert "aaaa" not in str(errors)
