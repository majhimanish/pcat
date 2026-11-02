import csv
import io
import re

REQUIRED_FIELDS = ("id", "name", "email", "age")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_user_row(row):
    """Validate a single user row dict. Returns (cleaned_row, list_of_errors)."""
    errors = []
    cleaned = {}

    for field in REQUIRED_FIELDS:
        value = row.get(field)
        cleaned[field] = value.strip() if isinstance(value, str) else value
        if cleaned[field] in (None, ""):
            errors.append(f"missing required field '{field}'")

    if row.get(None):
        errors.append("row has more columns than the header")

    user_id = cleaned.get("id")
    if user_id not in (None, ""):
        if not user_id.isdigit() or int(user_id) <= 0:
            errors.append(f"invalid id '{user_id}': must be a positive integer")
        else:
            cleaned["id"] = int(user_id)

    email = cleaned.get("email")
    if email not in (None, "") and not EMAIL_PATTERN.match(email):
        errors.append(f"invalid email '{email}'")

    age = cleaned.get("age")
    if age not in (None, ""):
        try:
            age_value = int(age)
        except ValueError:
            errors.append(f"invalid age '{age}': must be an integer")
        else:
            if not 0 <= age_value <= 120:
                errors.append(f"invalid age {age_value}: must be between 0 and 120")
            else:
                cleaned["age"] = age_value

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse a CSV of users and validate each row.

    `source` may be a file path, a CSV string, or an open text file object.
    Expected header columns: id, name, email, age.

    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned dicts
      - errors is a list of {"line": int, "errors": [str], "row": dict}
        (line numbers are 1-based file lines, with the header on line 1)
    A file-level problem (e.g. missing header columns) is reported as an
    error entry with line 1 and an empty row.
    """
    if isinstance(source, str):
        if "\n" in source or "," in source:
            handle, should_close = io.StringIO(source), False
        else:
            handle, should_close = open(source, newline="", encoding="utf-8-sig"), True
    else:
        handle, should_close = source, False

    valid_rows = []
    row_errors = []

    try:
        reader = csv.DictReader(handle)
        header = [(name or "").strip().lower() for name in (reader.fieldnames or [])]
        missing = [f for f in REQUIRED_FIELDS if f not in header]
        if missing:
            row_errors.append({
                "line": 1,
                "errors": [f"missing required column(s): {', '.join(missing)}"],
                "row": {},
            })
            return valid_rows, row_errors

        reader.fieldnames = header

        for row in reader:
            line = reader.line_num
            cleaned, errors = validate_user_row(row)
            if errors:
                row_errors.append({"line": line, "errors": errors, "row": dict(row)})
            else:
                valid_rows.append(cleaned)
    finally:
        if should_close:
            handle.close()

    return valid_rows, row_errors
