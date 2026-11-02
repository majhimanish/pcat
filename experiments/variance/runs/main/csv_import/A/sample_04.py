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
        value = (row.get(field) or "").strip()
        if not value:
            errors.append(f"missing required field '{field}'")
        cleaned[field] = value

    if cleaned["id"]:
        if not cleaned["id"].isdigit() or int(cleaned["id"]) <= 0:
            errors.append(f"invalid id '{cleaned['id']}': must be a positive integer")
        else:
            cleaned["id"] = int(cleaned["id"])

    if cleaned["email"] and not EMAIL_RE.match(cleaned["email"]):
        errors.append(f"invalid email '{cleaned['email']}'")
    else:
        cleaned["email"] = cleaned["email"].lower()

    if cleaned["age"]:
        try:
            age = int(cleaned["age"])
            if not 0 <= age <= 120:
                errors.append(f"age {age} out of range (0-120)")
            else:
                cleaned["age"] = age
        except ValueError:
            errors.append(f"invalid age '{cleaned['age']}': must be an integer")

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse a CSV of users and validate each row.

    `source` may be a file path, a CSV string, or a file-like object.
    Expected columns: id, name, email, age.

    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned row dicts
      - errors is a list of {"row": <line number>, "errors": [messages]}
        (line numbers count the header as line 1)
    """
    if hasattr(source, "read"):
        stream, should_close = source, False
    elif isinstance(source, str) and "\n" in source:
        stream, should_close = io.StringIO(source), False
    else:
        stream, should_close = open(source, newline="", encoding="utf-8"), True

    valid_rows = []
    row_errors = []

    try:
        reader = csv.DictReader(stream)
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]
        missing = [f for f in REQUIRED_FIELDS if f not in headers]
        if missing:
            return [], [{"row": 1, "errors": [f"missing columns: {', '.join(missing)}"]}]
        reader.fieldnames = headers

        seen_ids = set()
        seen_emails = set()

        for row in reader:
            line_no = reader.line_num
            cleaned, errors = validate_user_row(row)

            if None in row:
                errors.append("row has more fields than header")

            if not errors:
                if cleaned["id"] in seen_ids:
                    errors.append(f"duplicate id {cleaned['id']}")
                if cleaned["email"] in seen_emails:
                    errors.append(f"duplicate email '{cleaned['email']}'")

            if errors:
                row_errors.append({"row": line_no, "errors": errors})
            else:
                seen_ids.add(cleaned["id"])
                seen_emails.add(cleaned["email"])
                valid_rows.append(cleaned)
    finally:
        if should_close:
            stream.close()

    return valid_rows, row_errors
