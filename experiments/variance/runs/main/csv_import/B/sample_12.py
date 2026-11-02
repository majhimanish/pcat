import csv
import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = ("name", "email", "age")
MIN_AGE = 0
MAX_AGE = 150


def validate_row(row):
    """Validate a single row dict. Returns (cleaned_row, list_of_error_messages)."""
    errors = []

    name = (row.get("name") or "").strip()
    email = (row.get("email") or "").strip()
    age_raw = (row.get("age") or "").strip()

    if not name:
        errors.append("name is missing")

    if not email:
        errors.append("email is missing")
    elif not EMAIL_PATTERN.match(email):
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

    Returns (valid_rows, errors) where:
      - valid_rows is a list of dicts: {"name": str, "email": str, "age": int}
      - errors is a list of dicts: {"row": int, "errors": [str, ...]}
    Row numbers are 1-based file line numbers; the header is row 1,
    so the first data row is row 2.
    """
    valid_rows = []
    errors = []

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            return valid_rows, [{"row": 1, "errors": ["file is empty or has no header"]}]

        reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            return valid_rows, [
                {"row": 1, "errors": [f"missing required columns: {', '.join(missing)}"]}
            ]

        for row in reader:
            row_number = reader.line_num

            if None in row:
                errors.append(
                    {"row": row_number, "errors": ["too many fields in row"]}
                )
                continue

            if all((v or "").strip() == "" for v in row.values()):
                continue  # skip blank lines

            cleaned, row_errors = validate_row(row)
            if row_errors:
                errors.append({"row": row_number, "errors": row_errors})
            else:
                valid_rows.append(cleaned)

    return valid_rows, errors
