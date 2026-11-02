import csv
import io
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = ("id", "name", "email", "age")


def validate_user_row(row):
    """Validate a single user row (dict). Returns (cleaned_row, errors)."""
    errors = []
    cleaned = {}

    raw_id = (row.get("id") or "").strip()
    if not raw_id:
        errors.append("id: missing")
    elif not raw_id.isdigit() or int(raw_id) <= 0:
        errors.append(f"id: must be a positive integer, got {raw_id!r}")
    else:
        cleaned["id"] = int(raw_id)

    name = (row.get("name") or "").strip()
    if not name:
        errors.append("name: missing")
    elif len(name) > 100:
        errors.append("name: longer than 100 characters")
    else:
        cleaned["name"] = name

    email = (row.get("email") or "").strip().lower()
    if not email:
        errors.append("email: missing")
    elif not EMAIL_RE.match(email):
        errors.append(f"email: invalid format {email!r}")
    else:
        cleaned["email"] = email

    raw_age = (row.get("age") or "").strip()
    if not raw_age:
        errors.append("age: missing")
    else:
        try:
            age = int(raw_age)
        except ValueError:
            errors.append(f"age: not an integer, got {raw_age!r}")
        else:
            if not 0 <= age <= 150:
                errors.append(f"age: out of range (0-150), got {age}")
            else:
                cleaned["age"] = age

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse and validate a CSV of users.

    `source` may be a CSV string or a file-like object. The CSV must have a
    header row containing: id, name, email, age.

    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned dicts
      - errors is a list of {"row": <line number>, "errors": [messages]} dicts
        (line numbers count the header as line 1). Duplicate ids and emails
        are reported as errors on the later occurrence.
    """
    if isinstance(source, str):
        source = io.StringIO(source)

    reader = csv.DictReader(source)
    valid_rows = []
    row_errors = []

    if reader.fieldnames is None:
        return [], [{"row": 0, "errors": ["file is empty or has no header"]}]

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        return [], [{"row": 1, "errors": [f"missing required columns: {', '.join(missing)}"]}]

    reader.fieldnames = [h.strip().lower() if h else h for h in reader.fieldnames]

    seen_ids = set()
    seen_emails = set()

    for row in reader:
        line_no = reader.line_num
        if None in row:
            row_errors.append({"row": line_no, "errors": ["too many fields in row"]})
            continue

        cleaned, errors = validate_user_row(row)

        if not errors:
            if cleaned["id"] in seen_ids:
                errors.append(f"id: duplicate {cleaned['id']}")
            if cleaned["email"] in seen_emails:
                errors.append(f"email: duplicate {cleaned['email']!r}")

        if errors:
            row_errors.append({"row": line_no, "errors": errors})
        else:
            seen_ids.add(cleaned["id"])
            seen_emails.add(cleaned["email"])
            valid_rows.append(cleaned)

    return valid_rows, row_errors
