import csv
import io
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_FIELDS = ("id", "name", "email", "age")


def validate_user_row(row):
    """Validate a single user row (dict). Returns (cleaned_row, errors)."""
    errors = []
    cleaned = {}

    for field in REQUIRED_FIELDS:
        value = row.get(field)
        cleaned[field] = value.strip() if isinstance(value, str) else ""
        if not cleaned[field]:
            errors.append(f"missing required field '{field}'")

    if cleaned["id"] and not cleaned["id"].isdigit():
        errors.append(f"id must be a positive integer, got '{cleaned['id']}'")
    elif cleaned["id"]:
        cleaned["id"] = int(cleaned["id"])
        if cleaned["id"] <= 0:
            errors.append("id must be a positive integer")

    if cleaned["email"] and not EMAIL_RE.match(cleaned["email"]):
        errors.append(f"invalid email '{cleaned['email']}'")

    if cleaned["age"]:
        try:
            age = int(cleaned["age"])
            if not 0 <= age <= 150:
                errors.append(f"age out of range (0-150): {age}")
            else:
                cleaned["age"] = age
        except ValueError:
            errors.append(f"age must be an integer, got '{cleaned['age']}'")

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse and validate a CSV of users.

    `source` may be a CSV string or a file-like object. The header must contain
    id, name, email, age.

    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned row dicts
      - errors is a list of {"row": <line number>, "errors": [messages]} dicts
        (line numbers count the header as line 1)
    """
    valid_rows = []
    row_errors = []

    handle = io.StringIO(source) if isinstance(source, str) else source
    reader = csv.DictReader(handle)

    if reader.fieldnames is None:
        return [], [{"row": 0, "errors": ["empty CSV: no header found"]}]

    header = [(h or "").strip().lower() for h in reader.fieldnames]
    reader.fieldnames = header
    missing_cols = [f for f in REQUIRED_FIELDS if f not in header]
    if missing_cols:
        return [], [{"row": 1, "errors": [f"missing columns: {', '.join(missing_cols)}"]}]

    seen_ids = set()
    for row in reader:
        line_no = reader.line_num
        if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
            continue  # skip blank lines

        cleaned, errors = validate_user_row(row)

        if None in row:
            errors.append("row has more fields than the header")

        if not errors:
            if cleaned["id"] in seen_ids:
                errors.append(f"duplicate id {cleaned['id']}")
            else:
                seen_ids.add(cleaned["id"])

        if errors:
            row_errors.append({"row": line_no, "errors": errors})
        else:
            valid_rows.append(cleaned)

    return valid_rows, row_errors
