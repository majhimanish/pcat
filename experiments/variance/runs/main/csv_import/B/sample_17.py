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

    if errors:
        return None, errors
    return {"name": name, "email": email, "age": age}, []


def parse_users_csv(path, encoding="utf-8-sig"):
    """
    Parse a users CSV with columns: name, email, age.

    Returns (valid_rows, errors):
      valid_rows: list of {"name": str, "email": str, "age": int}
      errors: list of {"row": int, "errors": [str, ...]}
    Row numbers are 1-based file line numbers (header is row 1,
    first data row is row 2).
    """
    valid_rows = []
    errors = []

    with open(path, newline="", encoding=encoding) as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            return [], [{"row": 1, "errors": ["file is empty or has no header"]}]

        header = [h.strip().lower() for h in reader.fieldnames]
        missing = [c for c in REQUIRED_FIELDS if c not in header]
        if missing:
            return [], [{"row": 1, "errors": [f"missing header column(s): {', '.join(missing)}"]}]

        reader.fieldnames = header

        for row in reader:
            row_number = reader.line_num  # physical line number in the file

            if None in row:
                errors.append({"row": row_number, "errors": ["too many columns"]})
                continue
            if all(v is None or not str(v).strip() for v in row.values()):
                continue  # skip blank lines
            if any(v is None for v in row.values()):
                errors.append({"row": row_number, "errors": ["too few columns"]})
                continue

            cleaned, row_errors = validate_row(row)
            if row_errors:
                errors.append({"row": row_number, "errors": row_errors})
            else:
                valid_rows.append(cleaned)

    return valid_rows, errors
