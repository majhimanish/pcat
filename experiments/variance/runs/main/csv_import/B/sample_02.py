import csv
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_FIELDS = ("name", "email", "age")
MIN_AGE = 0
MAX_AGE = 150


def validate_row(row):
    """Validate a single row dict. Return (cleaned_row, list_of_error_messages)."""
    errors = []

    name = (row.get("name") or "").strip()
    email = (row.get("email") or "").strip()
    age_raw = (row.get("age") or "").strip()

    if not name:
        errors.append("name is missing")

    if not email:
        errors.append("email is missing")
    elif not EMAIL_RE.match(email):
        errors.append(f"invalid email: {email!r}")

    age = None
    if not age_raw:
        errors.append("age is missing")
    else:
        try:
            age = int(age_raw)
        except ValueError:
            errors.append(f"age is not an integer: {age_raw!r}")
        else:
            if not MIN_AGE <= age <= MAX_AGE:
                errors.append(f"age out of range ({MIN_AGE}-{MAX_AGE}): {age}")

    cleaned = {"name": name, "email": email, "age": age}
    return cleaned, errors


def parse_users_csv(path):
    """
    Parse a users CSV with columns name, email, age.

    Returns (valid_rows, errors):
      valid_rows: list of dicts {"name", "email", "age"} with age as int
      errors: list of dicts {"row": <row number>, "errors": [messages]}
    Row numbers are 1-based file line numbers; the header is row 1,
    so the first data row is row 2.
    """
    valid_rows = []
    errors = []

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            return valid_rows, [{"row": 1, "errors": ["file is empty or has no header"]}]

        headers = {h.strip().lower() for h in reader.fieldnames if h}
        missing = [c for c in REQUIRED_FIELDS if c not in headers]
        if missing:
            return valid_rows, [
                {"row": 1, "errors": [f"missing required column(s): {', '.join(missing)}"]}
            ]

        for row in reader:
            row_num = reader.line_num
            normalized = {
                (k or "").strip().lower(): v
                for k, v in row.items()
                if k is not None
            }

            if row.get(None):
                errors.append({"row": row_num, "errors": ["too many columns"]})
                continue

            cleaned, row_errors = validate_row(normalized)
            if row_errors:
                errors.append({"row": row_num, "errors": row_errors})
            else:
                valid_rows.append(cleaned)

    return valid_rows, errors
