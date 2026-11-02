import csv
import io
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = ("id", "name", "email", "age")


def validate_user_row(row):
    """Validate one user row (dict). Returns (cleaned_row, list_of_errors)."""
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
      - errors is a list of {"row": <1-based data row number, header excluded>,
        "line": <line number in the file>, "errors": [messages]}
    Duplicate ids and emails are reported as errors on the later row.
    Raises ValueError if the header is missing or lacks required columns.
    """
    if isinstance(source, str):
        source = io.StringIO(source)

    reader = csv.DictReader(source)
    if reader.fieldnames is None:
        raise ValueError("CSV is empty: no header row found")

    fields = [f.strip().lower() for f in reader.fieldnames if f is not None]
    missing = [c for c in REQUIRED_COLUMNS if c not in fields]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")
    reader.fieldnames = [
        f.strip().lower() if f is not None else f for f in reader.fieldnames
    ]

    valid_rows = []
    row_errors = []
    seen_ids = set()
    seen_emails = set()

    for index, row in enumerate(reader, start=1):
        cleaned, errors = validate_user_row(row)

        if None in row:
            errors.append("row: has more fields than the header")

        if not errors:
            if cleaned["id"] in seen_ids:
                errors.append(f"id: duplicate {cleaned['id']}")
            if cleaned["email"] in seen_emails:
                errors.append(f"email: duplicate {cleaned['email']!r}")

        if errors:
            row_errors.append(
                {"row": index, "line": reader.line_num, "errors": errors}
            )
        else:
            seen_ids.add(cleaned["id"])
            seen_emails.add(cleaned["email"])
            valid_rows.append(cleaned)

    return valid_rows, row_errors
