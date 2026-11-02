import csv
import io
import re

REQUIRED_FIELDS = ("name", "email", "age")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


def validate_user_row(row):
    """Validate a single user row dict. Returns (cleaned_row, errors)."""
    errors = []
    cleaned = {}

    name = (row.get("name") or "").strip()
    if not name:
        errors.append("name is required")
    elif len(name) > 100:
        errors.append("name must be at most 100 characters")
    cleaned["name"] = name

    email = (row.get("email") or "").strip().lower()
    if not email:
        errors.append("email is required")
    elif not EMAIL_RE.match(email):
        errors.append(f"invalid email: {email!r}")
    cleaned["email"] = email

    age_raw = (row.get("age") or "").strip()
    if not age_raw:
        errors.append("age is required")
    else:
        try:
            age = int(age_raw)
            if not 0 <= age <= 120:
                errors.append(f"age out of range (0-120): {age}")
            cleaned["age"] = age
        except ValueError:
            errors.append(f"age must be an integer: {age_raw!r}")

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse and validate a CSV of users.

    `source` may be a CSV string or a file-like object. The CSV must have a
    header row containing name, email, and age columns.

    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned row dicts
      - errors is a list of {"row": <line number>, "errors": [messages]} dicts
        (line numbers count the header as line 1, so the first data row is 2)
    """
    if isinstance(source, str):
        source = io.StringIO(source)

    reader = csv.DictReader(source)
    valid_rows = []
    row_errors = []

    if reader.fieldnames is None:
        return valid_rows, [{"row": 1, "errors": ["CSV is empty or missing header"]}]

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = [f for f in REQUIRED_FIELDS if f not in headers]
    if missing:
        msg = f"missing required column(s): {', '.join(missing)}"
        return valid_rows, [{"row": 1, "errors": [msg]}]

    reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]
    seen_emails = {}

    for row in reader:
        line = reader.line_num
        if None in row:
            row_errors.append({"row": line, "errors": ["too many fields in row"]})
            continue

        cleaned, errors = validate_user_row(row)

        email = cleaned.get("email")
        if email and not errors:
            if email in seen_emails:
                errors.append(f"duplicate email (first seen on row {seen_emails[email]})")
            else:
                seen_emails[email] = line

        if errors:
            row_errors.append({"row": line, "errors": errors})
        else:
            valid_rows.append(cleaned)

    return valid_rows, row_errors
