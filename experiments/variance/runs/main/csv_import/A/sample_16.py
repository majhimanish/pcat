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

    if cleaned["email"] and not EMAIL_RE.match(cleaned["email"]):
        errors.append(f"invalid email '{cleaned['email']}'")
    elif cleaned["email"]:
        cleaned["email"] = cleaned["email"].lower()

    if cleaned["age"]:
        try:
            age = int(cleaned["age"])
            if not 0 <= age <= 120:
                errors.append(f"age out of range (0-120): {age}")
            else:
                cleaned["age"] = age
        except ValueError:
            errors.append(f"age must be an integer, got '{cleaned['age']}'")

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse and validate a CSV of users.

    `source` may be a CSV string or a file-like object. The CSV must have a
    header row containing: id, name, email, age.

    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned dicts
      - errors is a list of {"row": <line number>, "errors": [messages]}
        (line numbers count the header as line 1)
    """
    if isinstance(source, str):
        source = io.StringIO(source)

    valid_rows = []
    row_errors = []

    reader = csv.DictReader(source)
    if reader.fieldnames is None:
        return [], [{"row": 0, "errors": ["empty input: no header row"]}]

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = [f for f in REQUIRED_FIELDS if f not in headers]
    if missing:
        return [], [{"row": 1, "errors": [f"missing header columns: {', '.join(missing)}"]}]

    seen_ids = set()
    for row in reader:
        line_no = reader.line_num
        normalized = {
            (k or "").strip().lower(): v for k, v in row.items() if k is not None
        }

        cleaned, errors = validate_user_row(normalized)

        if None in row:
            errors.append("row has more columns than header")

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
