import csv
import io
import re
from datetime import datetime

REQUIRED_FIELDS = ["id", "name", "email", "age", "signup_date"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_user_row(row):
    """Validate a single user row dict. Returns (cleaned_row, errors)."""
    errors = []
    cleaned = {}

    # id: positive integer
    raw_id = (row.get("id") or "").strip()
    if not raw_id:
        errors.append("id is required")
    elif not raw_id.isdigit() or int(raw_id) <= 0:
        errors.append(f"id must be a positive integer, got {raw_id!r}")
    else:
        cleaned["id"] = int(raw_id)

    # name: non-empty, reasonable length
    name = (row.get("name") or "").strip()
    if not name:
        errors.append("name is required")
    elif len(name) > 100:
        errors.append("name must be at most 100 characters")
    else:
        cleaned["name"] = name

    # email: basic format check
    email = (row.get("email") or "").strip().lower()
    if not email:
        errors.append("email is required")
    elif not EMAIL_RE.match(email):
        errors.append(f"email is invalid: {email!r}")
    else:
        cleaned["email"] = email

    # age: integer between 0 and 150
    raw_age = (row.get("age") or "").strip()
    if not raw_age:
        errors.append("age is required")
    else:
        try:
            age = int(raw_age)
            if 0 <= age <= 150:
                cleaned["age"] = age
            else:
                errors.append(f"age must be between 0 and 150, got {age}")
        except ValueError:
            errors.append(f"age must be an integer, got {raw_age!r}")

    # signup_date: ISO format, not in the future
    raw_date = (row.get("signup_date") or "").strip()
    if not raw_date:
        errors.append("signup_date is required")
    else:
        try:
            parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
            if parsed > datetime.now().date():
                errors.append(f"signup_date is in the future: {raw_date}")
            else:
                cleaned["signup_date"] = parsed.isoformat()
        except ValueError:
            errors.append(f"signup_date must be YYYY-MM-DD, got {raw_date!r}")

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse and validate a CSV of users.

    `source` may be a CSV string or a file path.

    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned row dicts
      - errors is a list of {"row": <line number>, "errors": [messages]} dicts
        (line numbers count the header as line 1)
    A header-level problem is reported as a single error with row 0.
    """
    if "\n" in source or "," in source:
        stream = io.StringIO(source, newline="")
    else:
        stream = open(source, newline="", encoding="utf-8-sig")

    valid_rows = []
    row_errors = []
    seen_ids = set()
    seen_emails = set()

    try:
        reader = csv.DictReader(stream)
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]

        missing = [f for f in REQUIRED_FIELDS if f not in headers]
        if missing:
            return [], [{"row": 0, "errors": [f"missing columns: {', '.join(missing)}"]}]

        reader.fieldnames = headers

        for row in reader:
            line_no = reader.line_num
            if None in row:
                row_errors.append({"row": line_no, "errors": ["too many fields in row"]})
                continue
            if all(v is None or not str(v).strip() for v in row.values()):
                continue  # skip blank lines

            cleaned, errors = validate_user_row(row)

            # duplicate checks (only against previously accepted rows)
            if not errors:
                if cleaned["id"] in seen_ids:
                    errors.append(f"duplicate id: {cleaned['id']}")
                if cleaned["email"] in seen_emails:
                    errors.append(f"duplicate email: {cleaned['email']}")

            if errors:
                row_errors.append({"row": line_no, "errors": errors})
            else:
                seen_ids.add(cleaned["id"])
                seen_emails.add(cleaned["email"])
                valid_rows.append(cleaned)
    finally:
        stream.close()

    return valid_rows, row_errors
