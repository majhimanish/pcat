import csv
import io
import re

REQUIRED_COLUMNS = ("id", "name", "email", "age")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_user_row(row):
    """Validate one user row (dict of str -> str). Returns (cleaned_row, errors)."""
    errors = []
    cleaned = {}

    raw_id = (row.get("id") or "").strip()
    if not raw_id:
        errors.append("id is required")
    elif not raw_id.isdigit() or int(raw_id) <= 0:
        errors.append(f"id must be a positive integer, got {raw_id!r}")
    else:
        cleaned["id"] = int(raw_id)

    name = (row.get("name") or "").strip()
    if not name:
        errors.append("name is required")
    elif len(name) > 100:
        errors.append("name must be at most 100 characters")
    else:
        cleaned["name"] = name

    email = (row.get("email") or "").strip().lower()
    if not email:
        errors.append("email is required")
    elif not EMAIL_PATTERN.match(email):
        errors.append(f"email is invalid: {email!r}")
    else:
        cleaned["email"] = email

    raw_age = (row.get("age") or "").strip()
    if not raw_age:
        errors.append("age is required")
    else:
        try:
            age = int(raw_age)
        except ValueError:
            errors.append(f"age must be an integer, got {raw_age!r}")
        else:
            if not 0 <= age <= 150:
                errors.append(f"age must be between 0 and 150, got {age}")
            else:
                cleaned["age"] = age

    return cleaned, errors


def parse_users_csv(csv_text):
    """Parse CSV text of users.

    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned dicts
      - errors is a list of {"line": int, "errors": [str], "row": dict} entries,
        where "line" is the line number in the source text (header is line 1).
    """
    valid_rows = []
    row_errors = []

    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        return [], [{"line": 1, "errors": ["CSV is empty or has no header"], "row": {}}]

    header = [h.strip().lower() for h in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        return [], [{
            "line": 1,
            "errors": [f"missing required column(s): {', '.join(missing)}"],
            "row": {},
        }]
    reader.fieldnames = header

    seen_ids = set()
    seen_emails = set()

    for row in reader:
        line = reader.line_num
        if None in row:
            row_errors.append({
                "line": line,
                "errors": ["row has more fields than the header"],
                "row": {k: v for k, v in row.items() if k is not None},
            })
            continue

        cleaned, errors = validate_user_row(row)

        if "id" in cleaned and cleaned["id"] in seen_ids:
            errors.append(f"duplicate id: {cleaned['id']}")
        if "email" in cleaned and cleaned["email"] in seen_emails:
            errors.append(f"duplicate email: {cleaned['email']}")

        if errors:
            row_errors.append({"line": line, "errors": errors, "row": dict(row)})
        else:
            seen_ids.add(cleaned["id"])
            seen_emails.add(cleaned["email"])
            valid_rows.append(cleaned)

    return valid_rows, row_errors
