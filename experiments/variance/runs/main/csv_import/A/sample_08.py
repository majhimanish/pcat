import csv
import io
import re
from typing import Any

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
REQUIRED_COLUMNS = ("id", "name", "email", "age")
MIN_AGE = 0
MAX_AGE = 150


def validate_user_row(row: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Validate a single CSV row. Returns (cleaned_row, list_of_error_messages)."""
    errors: list[str] = []
    cleaned: dict[str, Any] = {}

    raw_id = (row.get("id") or "").strip()
    if not raw_id:
        errors.append("id: missing")
    elif not raw_id.isdigit() or int(raw_id) <= 0:
        errors.append(f"id: must be a positive integer, got {raw_id!r}")
    else:
        cleaned["id"] = int(raw_id)

    name = (row.get("name") or "").strip()
    if not name:
        errors.append("name: missing")
    elif len(name) > 100:
        errors.append("name: longer than 100 characters")
    else:
        cleaned["name"] = name

    email = (row.get("email") or "").strip()
    if not email:
        errors.append("email: missing")
    elif not EMAIL_RE.match(email):
        errors.append(f"email: invalid format {email!r}")
    else:
        cleaned["email"] = email.lower()

    raw_age = (row.get("age") or "").strip()
    if not raw_age:
        errors.append("age: missing")
    else:
        try:
            age = int(raw_age)
        except ValueError:
            errors.append(f"age: not an integer, got {raw_age!r}")
        else:
            if not MIN_AGE <= age <= MAX_AGE:
                errors.append(f"age: must be between {MIN_AGE} and {MAX_AGE}, got {age}")
            else:
                cleaned["age"] = age

    return cleaned, errors


def parse_users_csv(csv_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Parse a CSV string of users and validate each row.

    Returns (valid_rows, errors) where each error is
    {"row": <1-based data row number>, "line": <file line number>, "errors": [messages]}.
    Header-level problems are reported with row 0.
    Duplicate ids and duplicate emails are flagged on the later occurrence.
    """
    valid_rows: list[dict[str, Any]] = []
    row_errors: list[dict[str, Any]] = []

    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    if reader.fieldnames is None:
        return [], [{"row": 0, "line": 1, "errors": ["file is empty or has no header"]}]

    reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        return [], [{"row": 0, "line": 1, "errors": [f"header: missing columns {missing}"]}]

    seen_ids: set[int] = set()
    seen_emails: set[str] = set()

    for row_num, row in enumerate(reader, start=1):
        line = reader.line_num
        if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
            continue  # skip blank lines

        cleaned, errors = validate_user_row(row)

        if None in row:
            errors.append("row: has more fields than header")

        if "id" in cleaned and cleaned["id"] in seen_ids:
            errors.append(f"id: duplicate {cleaned['id']}")
        if "email" in cleaned and cleaned["email"] in seen_emails:
            errors.append(f"email: duplicate {cleaned['email']!r}")

        if errors:
            row_errors.append({"row": row_num, "line": line, "errors": errors})
        else:
            seen_ids.add(cleaned["id"])
            seen_emails.add(cleaned["email"])
            valid_rows.append(cleaned)

    return valid_rows, row_errors


def parse_users_csv_file(path: str, encoding: str = "utf-8-sig") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read a CSV file from disk and parse it with parse_users_csv."""
    with open(path, newline="", encoding=encoding) as f:
        return parse_users_csv(f.read())
