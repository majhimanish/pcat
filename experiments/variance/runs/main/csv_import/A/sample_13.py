import csv
import io
import re

REQUIRED_COLUMNS = ("id", "name", "email", "age")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$")


def validate_user_row(row):
    """Validate a single user row (dict). Returns (cleaned_row, errors)."""
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
            if not 0 <= age <= 150:
                errors.append(f"age must be between 0 and 150, got {age}")
            else:
                cleaned["age"] = age

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse and validate a CSV of users.

    `source` may be a file path, a CSV string, or an open text file object.
    Returns (valid_rows, errors) where:
      - valid_rows is a list of cleaned dicts
      - errors is a list of {"line": int, "errors": [str], "row": dict}
        (line is the 1-based line number in the file, header = line 1;
        a line of 0 denotes a file-level problem such as missing columns)
    """
    if isinstance(source, str):
        if "\n" in source or "," in source:
            handle = io.StringIO(source)
        else:
            handle = open(source, newline="", encoding="utf-8-sig")
    else:
        handle = source

    valid_rows = []
    row_errors = []
    seen_ids = {}
    seen_emails = {}

    try:
        reader = csv.DictReader(handle)
        headers = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_COLUMNS if c not in headers]
        if missing:
            row_errors.append({
                "line": 0,
                "errors": [f"missing required columns: {', '.join(missing)}"],
                "row": {},
            })
            return valid_rows, row_errors
        reader.fieldnames = headers

        for row in reader:
            line = reader.line_num
            if None in row:
                row_errors.append({
                    "line": line,
                    "errors": ["row has more fields than the header"],
                    "row": {k: v for k, v in row.items() if k is not None},
                })
                continue
            if all(v is None or not str(v).strip() for v in row.values()):
                continue  # skip blank lines

            cleaned, errors = validate_user_row(row)

            if "id" in cleaned and cleaned["id"] in seen_ids:
                errors.append(f"duplicate id {cleaned['id']} (first seen on line {seen_ids[cleaned['id']]})")
            if "email" in cleaned and cleaned["email"] in seen_emails:
                errors.append(f"duplicate email {cleaned['email']!r} (first seen on line {seen_emails[cleaned['email']]})")

            if errors:
                row_errors.append({"line": line, "errors": errors, "row": row})
            else:
                seen_ids[cleaned["id"]] = line
                seen_emails[cleaned["email"]] = line
                valid_rows.append(cleaned)
    finally:
        if handle is not source:
            handle.close()

    return valid_rows, row_errors
