import csv
import io
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = ("id", "name", "email", "age")


def validate_user_row(row):
    """Validate one user row (dict of str -> str). Returns (cleaned_row, errors)."""
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

    email = (row.get("email") or "").strip().lower()
    if not email:
        errors.append("email: missing")
    elif not EMAIL_RE.match(email):
        errors.append(f"email: invalid format {email!r}")
    else:
        cleaned["email"] = email

    raw_age = (row.get("age") or "").strip()
    if not raw_age:
        errors.append("age: missing")
    else:
        try:
            age = int(raw_age)
        except ValueError:
            errors.append(f"age: not an integer, got {raw_age!r}")
        else:
            if not 0 <= age <= 150:
                errors.append(f"age: out of range (0-150), got {age}")
            else:
                cleaned["age"] = age

    return cleaned, errors


def parse_users_csv(source):
    """
    Parse a CSV of users, validate each row, and collect results.

    `source` may be a CSV string or a file-like object. The CSV must have a
    header row containing: id, name, email, age.

    Returns (valid_rows, errors):
      - valid_rows: list of cleaned dicts with typed values
      - errors: list of {"line": int, "row": dict, "errors": [str, ...]},
        where "line" is the 1-based line number in the file (header = 1).
        File-level problems (missing columns) are reported with line 1.
    """
    if isinstance(source, str):
        source = io.StringIO(source, newline="")

    reader = csv.DictReader(source)
    valid_rows = []
    row_errors = []

    fieldnames = [(f or "").strip().lower() for f in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        row_errors.append({
            "line": 1,
            "row": {},
            "errors": [f"header: missing required column(s): {', '.join(missing)}"],
        })
        return valid_rows, row_errors
    reader.fieldnames = fieldnames

    seen_ids = set()
    seen_emails = set()

    for row in reader:
        line = reader.line_num
        # Extra fields beyond the header are collected under key None.
        extra = row.pop(None, None)
        problems = []
        if extra:
            problems.append("row: more fields than header columns")
        if any(v is None for v in row.values()):
            problems.append("row: fewer fields than header columns")

        cleaned, errs = validate_user_row(row)
        problems.extend(errs)

        if "id" in cleaned:
            if cleaned["id"] in seen_ids:
                problems.append(f"id: duplicate {cleaned['id']}")
            else:
                seen_ids.add(cleaned["id"])
        if "email" in cleaned:
            if cleaned["email"] in seen_emails:
                problems.append(f"email: duplicate {cleaned['email']!r}")
            else:
                seen_emails.add(cleaned["email"])

        if problems:
            row_errors.append({"line": line, "row": dict(row), "errors": problems})
        else:
            valid_rows.append(cleaned)

    return valid_rows, row_errors
