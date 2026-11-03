import csv
import io
import re
from typing import Any

REQUIRED_COLUMNS = ("name", "email")
OPTIONAL_COLUMNS = ("age", "phone", "role")
ALLOWED_ROLES = {"admin", "user", "guest"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-().]{6,19}$")


def validate_user_row(row: dict, seen_emails: set) -> tuple[dict, list[str]]:
    """Validate one row. Returns (cleaned_row, list_of_problem_strings)."""
    problems = []
    cleaned = {k: (v or "").strip() for k, v in row.items() if k is not None}

    name = cleaned.get("name", "")
    if not name:
        problems.append("name is required")
    elif len(name) > 100:
        problems.append("name exceeds 100 characters")

    email = cleaned.get("email", "").lower()
    if not email:
        problems.append("email is required")
    elif not EMAIL_RE.match(email):
        problems.append(f"invalid email: {email!r}")
    elif email in seen_emails:
        problems.append(f"duplicate email: {email!r}")
    cleaned["email"] = email

    age = cleaned.get("age", "")
    if age:
        try:
            age_val = int(age)
            if not 0 < age_val < 130:
                problems.append(f"age out of range: {age_val}")
            else:
                cleaned["age"] = age_val
        except ValueError:
            problems.append(f"age is not an integer: {age!r}")
    else:
        cleaned["age"] = None

    phone = cleaned.get("phone", "")
    if phone and not PHONE_RE.match(phone):
        problems.append(f"invalid phone: {phone!r}")

    role = cleaned.get("role", "").lower()
    if role:
        if role not in ALLOWED_ROLES:
            problems.append(f"invalid role: {role!r} (allowed: {sorted(ALLOWED_ROLES)})")
        cleaned["role"] = role
    else:
        cleaned["role"] = "user"

    return cleaned, problems


def import_users_csv(text: str) -> tuple[list[dict], dict[int, dict[str, Any]]]:
    """
    Parse and validate users from CSV text.

    Returns (valid_users, errors). `errors` is keyed by 1-based line number
    (the line on which the row ends in the CSV text):
        {line: {"row": <raw row dict or None>, "errors": [messages]}}
    File-level problems (empty input, missing columns) are reported under
    key 0 (empty/no header) or key 1 (missing required columns) with row None.
    """
    good_rows: list[dict] = []
    errors: dict[int, dict[str, Any]] = {}
    seen_emails: set = set()

    def add_error(line: int, row: Any, messages: list[str]) -> None:
        entry = errors.setdefault(line, {"row": row, "errors": []})
        entry["errors"].extend(messages)

    if text is None:
        text = ""
    if text.startswith("\ufeff"):
        text = text[1:]

    reader = csv.DictReader(io.StringIO(text, newline=""))

    try:
        fieldnames = reader.fieldnames
    except csv.Error as exc:
        return [], {0: {"row": None, "errors": [f"CSV parse error: {exc}"]}}

    if fieldnames is None:
        return [], {0: {"row": None, "errors": ["input is empty or has no header"]}}

    reader.fieldnames = [(h or "").strip().lower() for h in fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        return [], {1: {
            "row": None,
            "errors": [f"missing required column(s): {', '.join(missing)}"],
        }}

    try:
        for row in reader:
            line = reader.line_num
            row_problems = []

            if None in row:
                row_problems.append("row has more fields than the header")
            if any(v is None for k, v in row.items() if k is not None):
                row_problems.append("row has fewer fields than the header")

            if not row_problems and all(
                not (v or "").strip() for k, v in row.items() if k is not None
            ):
                continue  # skip fully blank lines

            cleaned, problems = validate_user_row(row, seen_emails)
            problems = row_problems + problems

            if problems:
                add_error(line, {k: v for k, v in row.items()}, problems)
            else:
                seen_emails.add(cleaned["email"])
                good_rows.append(cleaned)
    except csv.Error as exc:
        add_error(reader.line_num, None, [f"CSV parse error: {exc}"])

    return good_rows, errors
