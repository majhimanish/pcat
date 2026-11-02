import csv
import io
import re

REQUIRED_FIELDS = ("id", "name", "email", "age")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_user_row(row):
    """Validate a single user row dict. Returns (cleaned_row, errors)."""
    errors = []
    cleaned = {}

    for field in REQUIRED_FIELDS:
        value = (row.get(field) or "").strip()
        if not value:
            errors.append(f"missing required field '{field}'")
        cleaned[field] = value

    if cleaned["id"] and not cleaned["id"].isdigit():
        errors.append(f"id must be a positive integer, got '{cleaned['id']}'")
    elif cleaned["id"]:
        cleaned["id"] = int(cleaned["id"])

    if cleaned["email"] and not EMAIL_RE.match(cleaned["email"]):
        errors.append(f"invalid email '{cleaned['email']}'")

    if cleaned["age"]:
        try:
            age = int(cleaned["age"])
            if not 0 < age < 130:
                errors.append(f"age out of range: {age}")
            else:
                cleaned["age"] = age
        except ValueError:
            errors.append(f"age must be an integer, got '{cleaned['age']}'")

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse a CSV of users and validate each row.

    `source` may be a CSV string or a file-like object. The CSV must have a
    header row containing: id, name, email, age.

    Returns (valid_rows, errors):
      valid_rows: list of cleaned row dicts
      errors: list of {"row": <line number>, "errors": [messages]} dicts
    """
    if isinstance(source, str):
        source = io.StringIO(source)

    reader = csv.DictReader(source)
    valid_rows = []
    row_errors = []

    if reader.fieldnames is None:
        return valid_rows, [{"row": 1, "errors": ["empty file or missing header"]}]

    header = [h.strip().lower() for h in reader.fieldnames]
    missing = [f for f in REQUIRED_FIELDS if f not in header]
    if missing:
        return valid_rows, [
            {"row": 1, "errors": [f"missing header columns: {', '.join(missing)}"]}
        ]
    reader.fieldnames = header

    seen_ids = set()
    for row in reader:
        line = reader.line_num
        cleaned, errors = validate_user_row(row)

        if not errors:
            if cleaned["id"] in seen_ids:
                errors.append(f"duplicate id {cleaned['id']}")
            else:
                seen_ids.add(cleaned["id"])

        if errors:
            row_errors.append({"row": line, "errors": errors})
        else:
            valid_rows.append(cleaned)

    return valid_rows, row_errors
