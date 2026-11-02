import csv
import re
from typing import Any

REQUIRED_COLUMNS = ("name", "email")
OPTIONAL_COLUMNS = ("age", "phone", "role")
VALID_ROLES = {"admin", "user", "viewer"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-().]{6,19}$")


def validate_user_row(row: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """Validate and normalize a single row. Returns (clean_user, problems)."""
    problems: list[str] = []
    clean: dict[str, Any] = {}

    name = (row.get("name") or "").strip()
    if not name:
        problems.append("name is required")
    elif len(name) > 100:
        problems.append("name must be at most 100 characters")
    else:
        clean["name"] = name

    email = (row.get("email") or "").strip().lower()
    if not email:
        problems.append("email is required")
    elif len(email) > 254 or not EMAIL_RE.match(email):
        problems.append(f"invalid email: {email!r}")
    else:
        clean["email"] = email

    age_raw = (row.get("age") or "").strip()
    if age_raw:
        try:
            age = int(age_raw)
            if not 0 < age < 150:
                problems.append(f"age out of range: {age}")
            else:
                clean["age"] = age
        except ValueError:
            problems.append(f"age must be an integer: {age_raw!r}")

    phone = (row.get("phone") or "").strip()
    if phone:
        if PHONE_RE.match(phone):
            clean["phone"] = phone
        else:
            problems.append(f"invalid phone: {phone!r}")

    role = (row.get("role") or "").strip().lower()
    if role:
        if role in VALID_ROLES:
            clean["role"] = role
        else:
            problems.append(
                f"invalid role: {role!r} (expected one of {sorted(VALID_ROLES)})"
            )

    return clean, problems


def import_users_from_csv(path: str, encoding: str = "utf-8-sig") -> dict[str, Any]:
    """
    Parse a CSV of users, validating every row.

    Returns {"valid": [user dicts], "errors": [{"line": int, "row": dict, "errors": [str]}]}.
    Line numbers refer to the physical line in the file (header is line 1).
    Duplicate emails (case-insensitive) after the first occurrence are rejected.
    Raises FileNotFoundError / ValueError for unreadable files or missing required columns.
    """
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_emails: dict[str, int] = {}

    with open(path, newline="", encoding=encoding) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or has no header row")

        reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV is missing required column(s): {', '.join(missing)}")

        for row in reader:
            line = reader.line_num

            # Skip fully blank rows
            if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
                continue

            row_problems: list[str] = []

            # Ragged rows: extra fields land under key None, missing ones are None
            if None in row:
                row_problems.append("row has more fields than the header")
            if any(row.get(c) is None for c in REQUIRED_COLUMNS):
                row_problems.append("row has fewer fields than the header")

            clean, problems = validate_user_row(
                {k: v for k, v in row.items() if k is not None}
            )
            row_problems.extend(problems)

            if not row_problems and clean["email"] in seen_emails:
                row_problems.append(
                    f"duplicate email {clean['email']!r} (first seen on line {seen_emails[clean['email']]})"
                )

            if row_problems:
                raw = {k: v for k, v in row.items() if k is not None}
                errors.append({"line": line, "row": raw, "errors": row_problems})
            else:
                seen_emails[clean["email"]] = line
                valid.append(clean)

    return {"valid": valid, "errors": errors}
