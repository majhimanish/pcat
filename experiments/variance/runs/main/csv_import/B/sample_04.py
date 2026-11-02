import csv
import io
import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REQUIRED_COLUMNS = ("id", "name", "email", "age")


def validate_user_row(row, line_number, seen_ids, seen_emails):
    """Validate a single user row. Returns (cleaned_record_or_None, list_of_problems)."""
    problems = []

    def problem(field, message):
        problems.append({"line": line_number, "field": field, "message": message, "row": dict(row)})

    # Extra values beyond the header land under the None key in DictReader.
    if None in row:
        problem(None, "row has more values than the header has columns")

    user_id = (row.get("id") or "").strip()
    name = (row.get("name") or "").strip()
    email = (row.get("email") or "").strip().lower()
    age_raw = (row.get("age") or "").strip()

    if not user_id:
        problem("id", "id is required")
    elif not user_id.isdigit():
        problem("id", f"id must be a positive integer, got {user_id!r}")
    elif user_id in seen_ids:
        problem("id", f"duplicate id {user_id} (first seen on line {seen_ids[user_id]})")

    if not name:
        problem("name", "name is required")
    elif len(name) > 100:
        problem("name", "name must be at most 100 characters")

    if not email:
        problem("email", "email is required")
    elif not EMAIL_RE.match(email):
        problem("email", f"invalid email {email!r}")
    elif email in seen_emails:
        problem("email", f"duplicate email {email} (first seen on line {seen_emails[email]})")

    age = None
    if not age_raw:
        problem("age", "age is required")
    else:
        try:
            age = int(age_raw)
            if not 0 <= age <= 120:
                problem("age", f"age must be between 0 and 120, got {age}")
        except ValueError:
            problem("age", f"age must be an integer, got {age_raw!r}")

    if problems:
        return None, problems

    seen_ids[user_id] = line_number
    seen_emails[email] = line_number
    return {"id": int(user_id), "name": name, "email": email, "age": age}, []


def validate_users_csv(source):
    """
    Validate a CSV of users row by row.

    `source` may be a file path, a CSV string, or an open text file-like object.
    Expected header: id, name, email, age (extra columns are ignored).

    Returns (valid_records, problems), where each problem is a dict with
    'line', 'field', 'message' and the original 'row'.
    """
    if hasattr(source, "read"):
        text = source.read()
    elif isinstance(source, str) and "\n" not in source and "," not in source:
        with open(source, newline="", encoding="utf-8-sig") as f:
            text = f.read()
    else:
        text = source

    valid, problems = [], []
    reader = csv.DictReader(io.StringIO(text, newline=""))

    if reader.fieldnames is None:
        return valid, [{"line": 1, "field": None, "message": "file is empty", "row": {}}]

    reader.fieldnames = [(h or "").strip().lower() for h in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        return valid, [{
            "line": 1,
            "field": None,
            "message": f"missing required column(s): {', '.join(missing)}",
            "row": {},
        }]

    seen_ids, seen_emails = {}, {}
    for row in reader:
        line_number = reader.line_num
        if not any((v or "").strip() for k, v in row.items() if k is not None):
            continue  # skip blank lines
        record, row_problems = validate_user_row(row, line_number, seen_ids, seen_emails)
        if record is not None:
            valid.append(record)
        problems.extend(row_problems)

    return valid, problems
