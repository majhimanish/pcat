import csv
import io
import re
from datetime import datetime

REQUIRED_FIELDS = ("id", "name", "email", "age", "signup_date")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


def validate_user_row(row):
    """Validate a single user row (dict). Returns (cleaned_row, errors)."""
    errors = []
    cleaned = {}

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
            if not 0 <= age <= 120:
                errors.append(f"age must be between 0 and 120, got {age}")
            else:
                cleaned["age"] = age
        except ValueError:
            errors.append(f"age must be an integer, got {raw_age!r}")

    raw_date = (row.get("signup_date") or "").strip()
    if not raw_date:
        errors.append("signup_date is required")
    else:
        try:
            parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
            if parsed > datetime.now().date():
                errors.append("signup_date cannot be in the future")
            else:
                cleaned["signup_date"] = parsed.isoformat()
        except ValueError:
            errors.append(f"signup_date must be YYYY-MM-DD, got {raw_date!r}")

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse and validate a CSV of users.

    `source` may be a file path, an open text file object, or a CSV string
    (any string containing a newline is treated as CSV content).

    Returns (valid_rows, errors):
      valid_rows: list of cleaned dicts
      errors: list of {"line": <csv line number>, "row": <raw row>, "errors": [messages]}
    Duplicate ids and duplicate emails are reported as row errors.
    File-level problems (missing columns) are reported with line 1.
    """
    if isinstance(source, str):
        if "\n" in source or "\r" in source:
            handle, should_close = io.StringIO(source), False
        else:
            handle, should_close = open(source, newline="", encoding="utf-8-sig"), True
    else:
        handle, should_close = source, False

    valid_rows = []
    errors = []

    try:
        reader = csv.DictReader(handle)
        fieldnames = [(f or "").strip().lower() for f in (reader.fieldnames or [])]
        missing = [f for f in REQUIRED_FIELDS if f not in fieldnames]
        if missing:
            errors.append({
                "line": 1,
                "row": None,
                "errors": [f"missing required column(s): {', '.join(missing)}"],
            })
            return valid_rows, errors
        reader.fieldnames = fieldnames

        seen_ids = set()
        seen_emails = set()

        for row in reader:
            line = reader.line_num
            if None in row:
                errors.append({
                    "line": line,
                    "row": row,
                    "errors": ["row has more fields than the header"],
                })
                continue
            if not any((v or "").strip() for v in row.values()):
                continue  # skip blank lines

            cleaned, row_errors = validate_user_row(row)

            if not row_errors:
                if cleaned["id"] in seen_ids:
                    row_errors.append(f"duplicate id: {cleaned['id']}")
                if cleaned["email"] in seen_emails:
                    row_errors.append(f"duplicate email: {cleaned['email']}")

            if row_errors:
                errors.append({"line": line, "row": row, "errors": row_errors})
            else:
                seen_ids.add(cleaned["id"])
                seen_emails.add(cleaned["email"])
                valid_rows.append(cleaned)
    finally:
        if should_close:
            handle.close()

    return valid_rows, errors
