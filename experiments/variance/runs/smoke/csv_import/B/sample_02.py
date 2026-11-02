import csv
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_row(row):
    """Validate a single row dict. Return a list of error messages (empty if valid)."""
    errors = []

    name = (row.get("name") or "").strip()
    email = (row.get("email") or "").strip()
    age_raw = (row.get("age") or "").strip()

    if not name:
        errors.append("name is required")

    if not email:
        errors.append("email is required")
    elif not EMAIL_RE.match(email):
        errors.append(f"invalid email: {email!r}")

    age = None
    if not age_raw:
        errors.append("age is required")
    else:
        try:
            age = int(age_raw)
        except ValueError:
            errors.append(f"age is not an integer: {age_raw!r}")
        else:
            if age < 0 or age > 150:
                errors.append(f"age out of range (0-150): {age}")
                age = None

    return errors, {"name": name, "email": email, "age": age}


def parse_users_csv(path):
    """
    Parse a users CSV with columns: name, email, age.

    Returns (valid_rows, errors):
      valid_rows: list of dicts {"name", "email", "age"} (age as int)
      errors: list of dicts {"row": <row number>, "errors": [messages]}
    Row numbers are 1-based file line numbers; the header is row 1,
    so the first data row is row 2.
    """
    valid_rows = []
    errors = []

    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                return [], [{"row": 1, "errors": ["file is empty or missing header"]}]

            reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
            missing = {"name", "email", "age"} - set(reader.fieldnames)
            if missing:
                return [], [{
                    "row": 1,
                    "errors": [f"missing columns: {', '.join(sorted(missing))}"],
                }]

            for row in reader:
                row_num = reader.line_num
                if None in row:
                    errors.append({"row": row_num, "errors": ["too many fields"]})
                    continue
                if None in row.values():
                    errors.append({"row": row_num, "errors": ["too few fields"]})
                    continue

                row_errors, cleaned = validate_row(row)
                if row_errors:
                    errors.append({"row": row_num, "errors": row_errors})
                else:
                    valid_rows.append(cleaned)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        errors.append({"row": 0, "errors": [f"could not read file: {exc}"]})

    return valid_rows, errors
