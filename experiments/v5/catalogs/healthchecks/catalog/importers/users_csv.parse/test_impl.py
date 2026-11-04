import io
import time

import pytest

from impl import import_users

HEADER = "name,email,age\n"


# Normal cases ---------------------------------------------------------------
def test_valid_rows_are_normalised():
    valid, errors = import_users(HEADER + " Ada , ADA@Example.COM , 36\nBob,bob@example.com,\n")
    assert errors == []
    assert valid == [{"name": "Ada", "email": "ada@example.com", "age": 36},
                     {"name": "Bob", "email": "bob@example.com", "age": None}]


def test_accepts_text_streams_crlf_quotes_and_bom():
    text = "﻿Name,EMAIL,Age\r\n\"Lovelace, Ada\",ada@example.com,36\r\n\"Multi\nLine\",m@example.com,1\r\n"
    valid, errors = import_users(io.StringIO(text, newline=""))
    assert errors == [] and [u["name"] for u in valid] == ["Lovelace, Ada", "Multi\nLine"]


def test_age_column_is_optional():
    assert import_users("email,name\nz@example.org,Zed\n") == (
        [{"name": "Zed", "email": "z@example.org", "age": None}], [])


# Per-row errors -------------------------------------------------------------------
def test_each_problem_reported_with_its_line_number():
    text = HEADER + "Ada,ada@example.com,36\n,bob@example.com,20\nCy,not-an-email,\nDi,ADA@example.com,40\nEd,ed@example.com,abc\nFlo,flo@example.com,151\nGus,gus@example.com,30,extra\n"
    valid, errors = import_users(text)
    assert [u["name"] for u in valid] == ["Ada"]
    assert errors == [
        {"row": 3, "errors": ["name is required"]},
        {"row": 4, "errors": ["email is invalid"]},
        {"row": 5, "errors": ["duplicate email"]},
        {"row": 6, "errors": ["age must be a whole number from 0 to 150"]},
        {"row": 7, "errors": ["age must be a whole number from 0 to 150"]},
        {"row": 8, "errors": ["too many fields"]},
    ]


@pytest.mark.parametrize("email", ["a@b", "@example.com", "a@@example.com", "a@exa mple.com",
                                   "a@.", "a@..", "a b@example.com", "a@example.com@x.io"])
def test_invalid_emails(email):
    assert import_users(f"name,email\nX,{email}\n")[1] == [{"row": 2, "errors": ["email is invalid"]}]


def test_rows_with_several_problems_list_them_all():
    _, errors = import_users(HEADER + ",bad,-1\n")
    assert errors == [{"row": 2, "errors": ["name is required", "email is invalid",
                                            "age must be a whole number from 0 to 150"]}]


# Structural failures --------------------------------------------------------------
def test_missing_columns_or_empty_input():
    assert import_users("name,age\nA,1\n") == ([], [{"row": 1, "errors": ["missing columns: email"]}])
    assert import_users("") == ([], [{"row": 1, "errors": ["missing columns: name, email"]}])
    assert import_users(HEADER) == ([], [])


# Security / resource limits -------------------------------------------------------------
def test_row_limit_stops_processing():
    rows = "".join(f"u{i},u{i}@example.com,1\n" for i in range(10))
    valid, errors = import_users(HEADER + rows, max_rows=4)
    assert len(valid) == 4 and errors == [{"row": 6, "errors": ["more than 4 rows; stopped"]}]


def test_hostile_email_is_rejected_quickly():
    hostile = "a@" + "a." * 60000 + "@"  # quadratic for the common email regex
    start = time.perf_counter()
    assert import_users(f"name,email\nX,{hostile}\n")[1][0]["errors"] == ["email is invalid"]
    assert time.perf_counter() - start < 0.5


def test_field_values_are_never_echoed():
    _, errors = import_users(HEADER + "Secret Name,secret-value-not-an-email,secret-age\n")
    assert "secret" not in str(errors).lower()
