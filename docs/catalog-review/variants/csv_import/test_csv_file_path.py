import pytest

from csv_file_path import import_users_file


def write(tmp_path, text, encoding="utf-8"):
    path = tmp_path / "users.csv"
    path.write_text(text, encoding=encoding)
    return path


def test_reads_file_with_bom_and_quoted_newlines(tmp_path):
    text = 'name,email,age\n"Ada\nLovelace",ada@example.com,36\nBob,bob@example.com,\n'
    valid, errors = import_users_file(write(tmp_path, text, encoding="utf-8-sig"))
    assert valid == [{"name": "Ada\nLovelace", "email": "ada@example.com", "age": 36},
                     {"name": "Bob", "email": "bob@example.com", "age": None}]
    assert errors == []


def test_per_row_errors_with_line_numbers(tmp_path):
    text = "name,email,age\nA,a@example.com,1\nB,A@EXAMPLE.COM,2\n,c@example.com,x\n"
    valid, errors = import_users_file(write(tmp_path, text))
    assert [u["name"] for u in valid] == ["A"]
    assert errors == [{"row": 3, "errors": ["duplicate email"]},
                      {"row": 4, "errors": ["name is required", "age must be a whole number from 0 to 150"]}]


def test_missing_columns_and_row_limit(tmp_path):
    assert import_users_file(write(tmp_path, "email\nx@y.z\n"))[1] == [
        {"row": 1, "errors": ["missing columns: name"]}]
    rows = "".join(f"u{i},u{i}@example.com,\n" for i in range(4))
    valid, errors = import_users_file(write(tmp_path, "name,email,age\n" + rows), max_rows=2)
    assert len(valid) == 2 and errors[0]["errors"] == ["more than 2 rows; stopped"]


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        import_users_file(tmp_path / "nope.csv")
