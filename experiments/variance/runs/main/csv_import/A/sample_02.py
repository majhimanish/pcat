import csv
import io
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = ("id", "name", "email", "age")


def validate_user_row(row, min_age=0, max_age=150):
    """Validate a single user row dict. Returns (cleaned_row, errors)."""
    errors = []
    cleaned = {}

    raw_id = (row.get("id") or "").strip()
    if not raw_id:
        errors.append("id is required")
    elif not raw_id.isdigit():
        errors.append(f"id must be a non-negative integer, got {raw_id!r}")
    else:
        cleaned["id"] = int(raw_id)

    name = (row.get("name") or "").strip()
    if not name:
        errors.append("name is required")
    else:
        cleaned["name"] = name

    email = (row.get("email") or "").strip().lower()
    if not email:
        errors.append("email is required")
    elif not EMAIL_RE.match(email):
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
            if not (min_age <= age <= max_age):
                errors.append(f"age must be between {min_age} and {max_age}, got {age}")
            else:
                cleaned["age"] = age

    return cleaned, errors


def parse_users_csv(source, min_age=0, max_age=150):
    """
    Parse and validate a CSV of users.

    `source` may be a file path, a CSV string, or a file-like object.
    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned row dicts
      - errors is a list of {"line": int, "row": dict, "errors": [str, ...]}
        (line numbers refer to the CSV file, with the header on line 1)
    Duplicate ids and duplicate emails are reported as errors on later rows.
    """
    if hasattr(source, "read"):
        text = source.read()
    elif isinstance(source, str) and "\n" not in source and "," not in source:
        with open(source, newline="", encoding="utf-8-sig") as f:
            text = f.read()
    else:
        text = source
    if text.startswith("\ufeff"):
        text = text[1:]

    reader = csv.DictReader(io.StringIO(text, newline=""))
    valid_rows, row_errors = [], []

    fieldnames = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        return [], [{
            "line": 1,
            "row": {},
            "errors": [f"missing required column(s): {', '.join(missing)}"],
        }]
    reader.fieldnames = fieldnames

    seen_ids, seen_emails = set(), set()

    for row in reader:
        line = reader.line_num
        extra = row.pop(None, None)  # values beyond the header columns
        row = {k: v for k, v in row.items() if k is not None}

        cleaned, errors = validate_user_row(row, min_age, max_age)

        if extra:
            errors.append("row has more fields than the header")
        if "id" in cleaned and cleaned["id"] in seen_ids:
            errors.append(f"duplicate id: {cleaned['id']}")
        if "email" in cleaned and cleaned["email"] in seen_emails:
            errors.append(f"duplicate email: {cleaned['email']}")

        if errors:
            row_errors.append({"line": line, "row": row, "errors": errors})
        else:
            seen_ids.add(cleaned["id"])
            seen_emails.add(cleaned["email"])
            valid_rows.append(cleaned)

    return valid_rows, row_errors
