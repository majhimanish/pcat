import csv
import re
from typing import Any

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = ("id", "name", "email", "age")
VALID_ROLES = {"admin", "user", "guest"}


def validate_user_row(row: dict[str, str]) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate a single user row. Returns (cleaned_row_or_None, errors)."""
    errors: list[str] = []
    cleaned: dict[str, Any] = {}

    raw_id = (row.get("id") or "").strip()
    if not raw_id:
        errors.append("id is required")
    elif not raw_id.isdigit() or int(raw_id) <= 0:
        errors.append(f"id must be a positive integer, got {raw_id!r}")
    else:
        cleaned["id"] = int(raw_id)

    name = (row.get("name") or "").strip()
    if not name:
        errors.append("name is required")
    elif len(name) > 100:
        errors.append("name must be at most 100 characters")
    else:
        cleaned["name"] = name

    email = (row.get("email") or "").strip().lower()
    if not email:
        errors.append("email is required")
    elif not EMAIL_RE.match(email):
        errors.append(f"email is invalid: {email!r}")
    else:
        cleaned["email"] = email

    raw_age = (row.get("age") or "").strip()
    if not raw_age:
        errors.append("age is required")
    else:
        try:
            age = int(raw_age)
        except ValueError:
            errors.append(f"age must be an integer, got {raw_age!r}")
        else:
            if not 0 <= age <= 120:
                errors.append(f"age must be between 0 and 120, got {age}")
            else:
                cleaned["age"] = age

    role = (row.get("role") or "user").strip().lower()
    if role not in VALID_ROLES:
        errors.append(f"role must be one of {sorted(VALID_ROLES)}, got {role!r}")
    else:
        cleaned["role"] = role

    return (None if errors else cleaned), errors


def parse_users_csv(path: str, encoding: str = "utf-8-sig") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Parse a CSV file of users and validate each row.

    Returns (valid_rows, errors), where errors is a list of
    {"line": <file line number>, "errors": [<messages>], "row": <raw row>}.
    Header-level problems are reported with line 1. Duplicate ids and
    duplicate emails are flagged on the later occurrence.
    """
    valid_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    seen_emails: set[str] = set()

    try:
        with open(path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                return [], [{"line": 1, "errors": ["file is empty or has no header"], "row": {}}]

            headers = {h.strip().lower() for h in reader.fieldnames if h}
            missing = [c for c in REQUIRED_COLUMNS if c not in headers]
            if missing:
                return [], [{
                    "line": 1,
                    "errors": [f"missing required columns: {missing}"],
                    "row": {},
                }]

            reader.fieldnames = [h.strip().lower() if h else h for h in reader.fieldnames]

            for row in reader:
                line = reader.line_num
                # Skip fully blank rows
                if not any((v or "").strip() for v in row.values() if isinstance(v, str) or v is None):
                    continue

                cleaned, errors = validate_user_row(row)

                if row.get(None):
                    errors.append("row has more fields than the header")

                if cleaned is not None:
                    if cleaned["id"] in seen_ids:
                        errors.append(f"duplicate id: {cleaned['id']}")
                    if cleaned["email"] in seen_emails:
                        errors.append(f"duplicate email: {cleaned['email']}")

                if errors:
                    error_rows.append({"line": line, "errors": errors, "row": row})
                else:
                    seen_ids.add(cleaned["id"])
                    seen_emails.add(cleaned["email"])
                    valid_rows.append(cleaned)
    except FileNotFoundError:
        return [], [{"line": 0, "errors": [f"file not found: {path}"], "row": {}}]
    except (UnicodeDecodeError, csv.Error) as exc:
        return valid_rows, error_rows + [{"line": 0, "errors": [f"could not read file: {exc}"], "row": {}}]

    return valid_rows, error_rows
