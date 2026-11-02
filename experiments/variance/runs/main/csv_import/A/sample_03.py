import csv
import io
import re

REQUIRED_FIELDS = ("id", "name", "email", "age")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_user_row(row):
    """Validate a single user row dict. Returns (cleaned_row, errors)."""
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
        except ValueError:
            errors.append(f"age must be an integer, got {raw_age!r}")
        else:
            if not 0 <= age <= 150:
                errors.append(f"age must be between 0 and 150, got {age}")
            else:
                cleaned["age"] = age

    return cleaned, errors


def parse_users_csv(source):
    """Parse and validate a CSV of users.

    `source` may be a CSV string or a file-like object. The CSV must have a
    header row containing: id, name, email, age.

    Returns (valid_rows, errors), where:
      - valid_rows is a list of cleaned row dicts
      - errors is a list of {"row": <1-based data row number>,
        "line": <line number in file>, "errors": [messages]} dicts
        Header-level problems are reported with row=0.
    """
    stream = io.StringIO(source, newline="") if isinstance(source, str) else source
    reader = csv.DictReader(stream)

    valid_rows = []
    row_errors = []

    if reader.fieldnames is None:
        return valid_rows, [{"row": 0, "line": 1, "errors": ["CSV is empty or has no header"]}]

    header = [(h or "").strip().lower() for h in reader.fieldnames]
    reader.fieldnames = header
    missing = [f for f in REQUIRED_FIELDS if f not in header]
    if missing:
        msg = f"missing required column(s): {', '.join(missing)}"
        return valid_rows, [{"row": 0, "line": 1, "errors": [msg]}]

    seen_ids = set()
    seen_emails = set()

    for index, row in enumerate(reader, start=1):
        errors = []

        if None in row:
            errors.append("row has more fields than the header")
        if any(v is None for k, v in row.items() if k is not None):
            errors.append("row has fewer fields than the header")

        cleaned, field_errors = validate_user_row(
            {k: v for k, v in row.items() if k is not None}
        )
        errors.extend(field_errors)

        if "id" in cleaned and cleaned["id"] in seen_ids:
            errors.append(f"duplicate id: {cleaned['id']}")
        if "email" in cleaned and cleaned["email"] in seen_emails:
            errors.append(f"duplicate email: {cleaned['email']}")

        if errors:
            row_errors.append({"row": index, "line": reader.line_num, "errors": errors})
        else:
            seen_ids.add(cleaned["id"])
            seen_emails.add(cleaned["email"])
            valid_rows.append(cleaned)

    return valid_rows, row_errors
