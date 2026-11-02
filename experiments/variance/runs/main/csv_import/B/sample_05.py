import csv
import io
import re
from typing import Any

REQUIRED_COLUMNS = ("name", "email")
OPTIONAL_COLUMNS = ("age", "role")
ALLOWED_ROLES = {"admin", "user", "viewer"}
DEFAULT_ROLE = "user"
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
MAX_NAME_LENGTH = 100
MIN_AGE = 0
MAX_AGE = 150


def validate_name(value: str) -> tuple[str | None, str | None]:
    """Return (cleaned_name, error)."""
    name = (value or "").strip()
    if not name:
        return None, "name is required"
    if len(name) > MAX_NAME_LENGTH:
        return None, f"name exceeds {MAX_NAME_LENGTH} characters"
    return name, None


def validate_email(value: str) -> tuple[str | None, str | None]:
    """Return (normalized_email, error)."""
    email = (value or "").strip().lower()
    if not email:
        return None, "email is required"
    if not EMAIL_RE.match(email):
        return None, f"invalid email format: {email!r}"
    return email, None


def validate_age(value: str) -> tuple[int | None, str | None]:
    """Return (age, error). Empty age is allowed and yields None."""
    raw = (value or "").strip()
    if not raw:
        return None, None
    try:
        age = int(raw)
    except ValueError:
        return None, f"age must be an integer: {raw!r}"
    if not MIN_AGE <= age <= MAX_AGE:
        return None, f"age must be between {MIN_AGE} and {MAX_AGE}: {age}"
    return age, None


def validate_role(value: str) -> tuple[str | None, str | None]:
    """Return (role, error). Empty role falls back to the default."""
    role = (value or "").strip().lower()
    if not role:
        return DEFAULT_ROLE, None
    if role not in ALLOWED_ROLES:
        return None, f"role must be one of {sorted(ALLOWED_ROLES)}: {role!r}"
    return role, None


def validate_row(row: dict[str, str]) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate one CSV row. Return (user_or_None, list_of_errors)."""
    errors: list[str] = []

    if None in row:
        errors.append("row has more fields than the header")

    name, err = validate_name(row.get("name"))
    if err:
        errors.append(err)

    email, err = validate_email(row.get("email"))
    if err:
        errors.append(err)

    age, err = validate_age(row.get("age"))
    if err:
        errors.append(err)

    role, err = validate_role(row.get("role"))
    if err:
        errors.append(err)

    if errors:
        return None, errors
    return {"name": name, "email": email, "age": age, "role": role}, []


def import_users_from_reader(handle) -> dict[str, Any]:
    """Import users from an open text file-like object containing CSV."""
    valid_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_emails: dict[str, int] = {}

    reader = csv.DictReader(handle)
    if reader.fieldnames is None:
        return {
            "valid": [],
            "errors": [{"row": 0, "errors": ["file is empty or has no header"], "data": {}}],
            "total": 0,
        }

    # Normalize header names so " Email " and "EMAIL" match.
    reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]

    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        return {
            "valid": [],
            "errors": [{
                "row": 0,
                "errors": [f"missing required column(s): {', '.join(missing)}"],
                "data": {},
            }],
            "total": 0,
        }

    total = 0
    for row in reader:
        total += 1
        line_number = reader.line_num  # physical line, accounts for multi-line fields

        # Skip fully blank rows without counting them as errors.
        if all((v or "").strip() == "" for k, v in row.items() if k is not None):
            total -= 1
            continue

        user, row_errors = validate_row(row)

        if user is not None:
            first_seen = seen_emails.get(user["email"])
            if first_seen is not None:
                row_errors.append(
                    f"duplicate email {user['email']!r} (first seen on line {first_seen})"
                )
                user = None
            else:
                seen_emails[user["email"]] = line_number

        if user is not None:
            valid_rows.append(user)
        else:
            errors.append({
                "row": line_number,
                "errors": row_errors,
                "data": {k: v for k, v in row.items() if k is not None},
            })

    return {"valid": valid_rows, "errors": errors, "total": total}


def import_users_from_string(csv_text: str) -> dict[str, Any]:
    """Import users from a CSV string."""
    return import_users_from_reader(io.StringIO(csv_text))


def import_users_from_file(path: str, encoding: str = "utf-8-sig") -> dict[str, Any]:
    """Import users from a CSV file path. utf-8-sig strips a leading BOM."""
    with open(path, newline="", encoding=encoding) as handle:
        return import_users_from_reader(handle)


def format_error_report(result: dict[str, Any]) -> str:
    """Render a human-readable per-row error report."""
    lines = [
        f"Processed {result['total']} row(s): "
        f"{len(result['valid'])} valid, {len(result['errors'])} invalid."
    ]
    for entry in result["errors"]:
        lines.append(f"  Line {entry['row']}:")
        for message in entry["errors"]:
            lines.append(f"    - {message}")
    return "\n".join(lines)
