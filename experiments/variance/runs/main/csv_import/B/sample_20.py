import csv
import io
import re

REQUIRED_FIELDS = ("name", "email")
OPTIONAL_FIELDS = ("age", "role")
ALLOWED_ROLES = {"user", "admin", "editor", "viewer"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


def validate_user_row(row, seen_emails):
    """Validate one normalized row. Returns (cleaned_user_or_None, list_of_error_strings)."""
    errors = []

    name = row.get("name", "")
    email = row.get("email", "")
    age_raw = row.get("age", "")
    role = row.get("role", "")

    if not name:
        errors.append("name: required")
    elif len(name) > 100:
        errors.append("name: must be at most 100 characters")

    email_key = email.lower()
    if not email:
        errors.append("email: required")
    elif not EMAIL_RE.match(email):
        errors.append(f"email: invalid format '{email}'")
    elif email_key in seen_emails:
        errors.append(f"email: duplicate of row {seen_emails[email_key]}")

    age = None
    if age_raw:
        try:
            age = int(age_raw)
            if not 0 < age < 150:
                errors.append(f"age: out of range '{age_raw}'")
        except ValueError:
            errors.append(f"age: not an integer '{age_raw}'")

    if role:
        role = role.lower()
        if role not in ALLOWED_ROLES:
            errors.append(f"role: must be one of {sorted(ALLOWED_ROLES)}, got '{role}'")
    else:
        role = "user"

    if errors:
        return None, errors
    return {"name": name, "email": email_key, "age": age, "role": role}, []


def import_users_from_reader(reader):
    """Process a csv.DictReader. Returns (valid_users, error_report)."""
    valid_users = []
    error_report = []
    seen_emails = {}  # lowercase email -> row number of first valid occurrence

    if reader.fieldnames is None:
        return valid_users, [{"row": 0, "errors": ["file is empty or has no header"], "data": {}}]

    headers = [(h or "").strip().lower() for h in reader.fieldnames]
    reader.fieldnames = headers
    missing = [f for f in REQUIRED_FIELDS if f not in headers]
    if missing:
        return valid_users, [{
            "row": 1,
            "errors": [f"missing required column(s): {', '.join(missing)}"],
            "data": {},
        }]

    # Row numbers are file line numbers: header is row 1, first data row is 2.
    for row_num, raw in enumerate(reader, start=2):
        try:
            extra = raw.pop(None, None)  # cells beyond the header width
            row = {k: (v or "").strip() for k, v in raw.items() if k is not None}
            if all(v == "" for v in row.values()) and not extra:
                continue  # skip fully blank lines

            errors = []
            if extra:
                errors.append("row has more columns than header")

            user, row_errors = validate_user_row(row, seen_emails)
            errors.extend(row_errors)

            if errors:
                error_report.append({"row": row_num, "errors": errors, "data": row})
            else:
                seen_emails[user["email"]] = row_num
                valid_users.append(user)
        except Exception as exc:  # never let one bad row abort the import
            error_report.append({"row": row_num, "errors": [f"unexpected error: {exc}"], "data": {}})

    return valid_users, error_report


def import_users_from_csv_text(text):
    """Import users from CSV text. Returns (valid_users, error_report)."""
    if text.startswith("\ufeff"):
        text = text[1:]
    return import_users_from_reader(csv.DictReader(io.StringIO(text, newline="")))


def import_users_from_csv_file(path, encoding="utf-8-sig"):
    """Import users from a CSV file path. Returns (valid_users, error_report)."""
    with open(path, newline="", encoding=encoding) as f:
        return import_users_from_reader(csv.DictReader(f))


def format_error_report(error_report):
    """Render the error report as human-readable lines."""
    lines = []
    for entry in error_report:
        lines.append(f"Row {entry['row']}: " + "; ".join(entry["errors"]))
    return "\n".join(lines)
