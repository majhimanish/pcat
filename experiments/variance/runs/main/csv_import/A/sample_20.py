import csv
import io
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = ("id", "name", "email", "age")


def validate_user_row(row):
    """Validate a single user dict. Return (cleaned_row, list_of_error_strings)."""
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

    `source` may be a CSV string or a file-like object (opened in text mode).
    The CSV must have a header row containing: id, name, email, age.

    Returns (valid_rows, errors):
      valid_rows: list of cleaned dicts with typed values
      errors: list of {"row": <line number in file>, "errors": [str, ...]}
              Row-level problems use the 1-based line number (header = line 1).
              File-level problems (e.g. missing columns) use row 0.
    """
    if isinstance(source, str):
        source = io.StringIO(source)

    valid_rows = []
    row_errors = []

    reader = csv.DictReader(source)
    header = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        return [], [{"row": 0, "errors": [f"missing required columns: {', '.join(missing)}"]}]

    reader.fieldnames = header

    seen_ids = set()
    seen_emails = set()

    for row in reader:
        line_no = reader.line_num
        errors = []

        if None in row:
            errors.append("row has more fields than the header")

        cleaned, field_errors = validate_user_row(row)
        errors.extend(field_errors)

        if "id" in cleaned:
            if cleaned["id"] in seen_ids:
                errors.append(f"id: duplicate {cleaned['id']}")
            else:
                seen_ids.add(cleaned["id"])
        if "email" in cleaned:
            if cleaned["email"] in seen_emails:
                errors.append(f"email: duplicate {cleaned['email']!r}")
            else:
                seen_emails.add(cleaned["email"])

        if errors:
            row_errors.append({"row": line_no, "errors": errors})
        else:
            valid_rows.append(cleaned)

    return valid_rows, row_errors
