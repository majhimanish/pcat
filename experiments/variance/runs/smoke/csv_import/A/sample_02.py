import csv
import io
import re
from datetime import datetime

REQUIRED_COLUMNS = ("id", "name", "email", "age", "signup_date")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")
MIN_AGE = 0
MAX_AGE = 150


def validate_row(row):
    """Validate a single user row (dict of str -> str).

    Returns a tuple (cleaned_row, errors). cleaned_row is None if errors exist.
    """
    errors = []
    cleaned = {}

    raw_id = (row.get("id") or "").strip()
    if not raw_id:
        errors.append("id: missing")
    elif not raw_id.isdigit() or int(raw_id) <= 0:
        errors.append(f"id: must be a positive integer, got {raw_id!r}")
    else:
        cleaned["id"] = int(raw_id)

    name = (row.get("name") or "").strip()
    if not name:
        errors.append("name: missing")
    elif len(name) > 100:
        errors.append("name: longer than 100 characters")
    else:
        cleaned["name"] = name

    email = (row.get("email") or "").strip()
    if not email:
        errors.append("email: missing")
    elif not EMAIL_RE.match(email):
        errors.append(f"email: invalid format {email!r}")
    else:
        cleaned["email"] = email.lower()

    raw_age = (row.get("age") or "").strip()
    if not raw_age:
        errors.append("age: missing")
    else:
        try:
            age = int(raw_age)
        except ValueError:
            errors.append(f"age: must be an integer, got {raw_age!r}")
        else:
            if not MIN_AGE <= age <= MAX_AGE:
                errors.append(f"age: {age} out of range [{MIN_AGE}, {MAX_AGE}]")
            else:
                cleaned["age"] = age

    raw_date = (row.get("signup_date") or "").strip()
    if not raw_date:
        errors.append("signup_date: missing")
    else:
        try:
            parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            errors.append(f"signup_date: expected YYYY-MM-DD, got {raw_date!r}")
        else:
            if parsed > datetime.now().date():
                errors.append(f"signup_date: {raw_date} is in the future")
            else:
                cleaned["signup_date"] = parsed.isoformat()

    return (None if errors else cleaned), errors


def parse_users_csv(source):
    """Parse and validate a users CSV.

    `source` may be a file path, or a string of CSV text (detected by newline).
    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned row dicts
      - errors is a list of {"line": int, "errors": [str], "row": dict}
        (line is the 1-based line number in the file, header = line 1)
    Duplicate ids and duplicate emails are reported as errors on the later row.
    Structural problems (missing columns/empty file) are reported with line 1.
    """
    if "\n" in source or "\r" in source:
        handle = io.StringIO(source, newline="")
        close = False
    else:
        handle = open(source, newline="", encoding="utf-8-sig")
        close = True

    valid_rows = []
    row_errors = []

    try:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            return [], [{"line": 1, "errors": ["file is empty or has no header"], "row": {}}]

        header = [h.strip().lower() for h in reader.fieldnames]
        reader.fieldnames = header
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            return [], [{
                "line": 1,
                "errors": [f"header: missing required columns {missing}"],
                "row": {},
            }]

        seen_ids = {}
        seen_emails = {}

        for row in reader:
            line = reader.line_num
            # Skip fully blank lines
            if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
                continue

            cleaned, errors = validate_row(row)

            if None in row:
                errors.append("row: has more fields than the header")

            if cleaned is not None and not errors:
                if cleaned["id"] in seen_ids:
                    errors.append(
                        f"id: duplicate of line {seen_ids[cleaned['id']]}"
                    )
                if cleaned["email"] in seen_emails:
                    errors.append(
                        f"email: duplicate of line {seen_emails[cleaned['email']]}"
                    )

            if errors:
                safe_row = {k: v for k, v in row.items() if k is not None}
                row_errors.append({"line": line, "errors": errors, "row": safe_row})
            else:
                seen_ids[cleaned["id"]] = line
                seen_emails[cleaned["email"]] = line
                valid_rows.append(cleaned)
    finally:
        if close:
            handle.close()

    return valid_rows, row_errors
