import csv
import re
from typing import Any

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = ("name", "email")
ALLOWED_ROLES = {"user", "admin", "editor", "viewer"}


def validate_user_row(row: dict, line_number: int, seen_emails: set) -> tuple:
    """Validate a single row. Returns (cleaned_row_or_None, list_of_error_messages)."""
    errors = []

    name = (row.get("name") or "").strip()
    email = (row.get("email") or "").strip().lower()
    role = (row.get("role") or "").strip().lower() or "user"
    age_raw = (row.get("age") or "").strip()

    if not name:
        errors.append("name is required")
    elif len(name) > 100:
        errors.append("name exceeds 100 characters")

    if not email:
        errors.append("email is required")
    elif not EMAIL_RE.match(email):
        errors.append(f"invalid email format: {email!r}")
    elif email in seen_emails:
        errors.append(f"duplicate email: {email!r}")

    if role not in ALLOWED_ROLES:
        errors.append(f"invalid role: {role!r} (allowed: {', '.join(sorted(ALLOWED_ROLES))})")

    age = None
    if age_raw:
        try:
            age = int(age_raw)
            if not 0 < age < 150:
                errors.append(f"age out of range: {age}")
        except ValueError:
            errors.append(f"age is not an integer: {age_raw!r}")

    if errors:
        return None, errors

    seen_emails.add(email)
    return {"name": name, "email": email, "role": role, "age": age}, []


def import_users_from_csv(path: str, encoding: str = "utf-8-sig") -> tuple:
    """
    Parse a CSV file of users and validate every row.

    Expected header columns: name, email (required); role, age (optional).
    Header names are matched case-insensitively and ignoring surrounding whitespace.

    Returns:
        (good_rows, errors)
        good_rows: list of cleaned dicts with keys name, email, role, age.
        errors: list of dicts {"line": int, "row": dict, "errors": [str, ...]}.
                File-level problems (missing file, missing columns) are reported
                with line 0 or 1 and an empty row.
    """
    good_rows: list = []
    errors: list = []
    seen_emails: set = set()

    try:
        with open(path, newline="", encoding=encoding) as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                errors.append({"line": 1, "row": {}, "errors": ["file is empty or has no header"]})
                return good_rows, errors

            reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]
            missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
            if missing:
                errors.append({
                    "line": 1,
                    "row": {},
                    "errors": [f"missing required column(s): {', '.join(missing)}"],
                })
                return good_rows, errors

            try:
                for row in reader:
                    line = reader.line_num
                    if None in row:
                        errors.append({
                            "line": line,
                            "row": {k: v for k, v in row.items() if k is not None},
                            "errors": ["row has more fields than the header"],
                        })
                        continue
                    if any(v is None for v in row.values()):
                        errors.append({"line": line, "row": dict(row),
                                       "errors": ["row has fewer fields than the header"]})
                        continue
                    if not any((v or "").strip() for v in row.values()):
                        continue  # skip fully blank rows

                    cleaned, row_errors = validate_user_row(row, line, seen_emails)
                    if row_errors:
                        errors.append({"line": line, "row": dict(row), "errors": row_errors})
                    else:
                        good_rows.append(cleaned)
            except csv.Error as exc:
                errors.append({"line": reader.line_num, "row": {},
                               "errors": [f"CSV parse error: {exc}"]})
    except FileNotFoundError:
        errors.append({"line": 0, "row": {}, "errors": [f"file not found: {path}"]})
    except UnicodeDecodeError as exc:
        errors.append({"line": 0, "row": {}, "errors": [f"cannot decode file as {encoding}: {exc}"]})
    except OSError as exc:
        errors.append({"line": 0, "row": {}, "errors": [f"cannot read file: {exc}"]})

    return good_rows, errors
