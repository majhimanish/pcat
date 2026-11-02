import csv
import re
from typing import Any

REQUIRED_COLUMNS = ("name", "email")
OPTIONAL_COLUMNS = ("age", "phone", "role")
ALLOWED_ROLES = {"admin", "user", "editor", "viewer"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9\s\-().]{7,20}$")


def validate_user_row(row: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Validate and normalize one row. Returns (cleaned_row, problems)."""
    problems: list[str] = []
    cleaned: dict[str, Any] = {}

    name = (row.get("name") or "").strip()
    if not name:
        problems.append("name is required")
    elif len(name) > 100:
        problems.append("name must be at most 100 characters")
    cleaned["name"] = name

    email = (row.get("email") or "").strip().lower()
    if not email:
        problems.append("email is required")
    elif not EMAIL_RE.match(email):
        problems.append(f"invalid email: {email!r}")
    cleaned["email"] = email

    age_raw = (row.get("age") or "").strip()
    if age_raw:
        try:
            age = int(age_raw)
            if not 0 < age < 150:
                problems.append(f"age out of range: {age}")
            cleaned["age"] = age
        except ValueError:
            problems.append(f"age must be an integer: {age_raw!r}")
    else:
        cleaned["age"] = None

    phone = (row.get("phone") or "").strip()
    if phone and not PHONE_RE.match(phone):
        problems.append(f"invalid phone: {phone!r}")
    cleaned["phone"] = phone or None

    role = (row.get("role") or "").strip().lower()
    if role and role not in ALLOWED_ROLES:
        problems.append(f"invalid role: {role!r} (allowed: {', '.join(sorted(ALLOWED_ROLES))})")
    cleaned["role"] = role or "user"

    return cleaned, problems


def import_users_from_csv(path: str, encoding: str = "utf-8-sig") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Parse a CSV of users and validate every row.

    Returns (valid_rows, errors), where each error is a dict:
        {"line": <CSV line number>, "row": <raw row>, "errors": [<messages>]}
    File-level problems (missing header/columns) are reported with line 1 and row None.
    Duplicate emails (case-insensitive) after the first occurrence are rejected.
    """
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_emails: dict[str, int] = {}

    try:
        with open(path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return [], [{"line": 1, "row": None, "errors": ["file is empty or has no header"]}]

            reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]
            missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
            if missing:
                return [], [{
                    "line": 1,
                    "row": None,
                    "errors": [f"missing required column(s): {', '.join(missing)}"],
                }]

            for row in reader:
                line = reader.line_num
                row_errors: list[str] = []

                # Extra cells beyond the header land under key None; missing cells are None.
                if None in row:
                    row_errors.append("row has more fields than the header")
                if any(v is None for k, v in row.items() if k is not None):
                    row_errors.append("row has fewer fields than the header")

                # Skip fully blank lines silently.
                if not any((v or "").strip() for k, v in row.items() if k is not None and isinstance(v, str)):
                    if not row_errors or all(v is None for k, v in row.items() if k is not None):
                        continue

                safe_row = {k: v for k, v in row.items() if k is not None}
                cleaned, problems = validate_user_row(safe_row)
                row_errors.extend(problems)

                email = cleaned["email"]
                if email and not any("email" in p for p in problems):
                    if email in seen_emails:
                        row_errors.append(f"duplicate email (first seen on line {seen_emails[email]})")
                    else:
                        seen_emails[email] = line

                if row_errors:
                    errors.append({"line": line, "row": dict(row), "errors": row_errors})
                else:
                    valid.append(cleaned)

    except FileNotFoundError:
        return [], [{"line": 0, "row": None, "errors": [f"file not found: {path}"]}]
    except UnicodeDecodeError as exc:
        return valid, errors + [{"line": 0, "row": None, "errors": [f"encoding error: {exc}"]}]
    except csv.Error as exc:
        return valid, errors + [{"line": 0, "row": None, "errors": [f"CSV parse error: {exc}"]}]

    return valid, errors
